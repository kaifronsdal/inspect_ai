"""
Monte Carlo simulation of dynamic connection limit strategies for LLM API rate limiting.

Models the inspect_ai connection/retry system realistically:
- Token bucket rate limiter (Anthropic-style)
- Semaphore held during backoff (matches actual codebase behavior)
- Exponential backoff: initial=3s, max=1800s, jitter=±3s (exact tenacity config)
- Variable request token sizes
- Shared account with time-varying external competitor load

Strategies compared:
1. Fixed (current behavior): fixed max_connections, exponential backoff, no header parsing
2. Retry-After: fixed connections but use Retry-After header instead of exponential backoff
3. AIMD: additive increase / multiplicative decrease on connection count
4. AIMD + Retry-After: AIMD with Retry-After header parsing
5. Oracle: knows the true available rate, sets connections perfectly

Tests multiple regimes where rate limits actually bind:
- Scenario A: Tier 1 (50 RPM) — low limit, typical connections
- Scenario B: Tier 2 high concurrency — user sets max_connections=50
- Scenario C: Fast model (Haiku) — short latency, more requests/sec
"""

from __future__ import annotations

import dataclasses
import math
import random
import statistics
from collections import defaultdict
from typing import Literal

# ─────────────────────────────────────────────────────────
# Scenario configurations
# ─────────────────────────────────────────────────────────


@dataclasses.dataclass
class ScenarioConfig:
    """Parameters for a simulation scenario."""

    name: str

    # Rate limits (token bucket capacity = per-minute limit)
    account_rpm: int
    account_itpm: int
    account_otpm: int

    # Connection config
    max_connections: int

    # Request characteristics
    input_tokens_mean: float
    input_tokens_std: float
    output_tokens_mean: float
    output_tokens_std: float

    # Latency model
    ttft_mean: float
    ttft_std: float
    output_speed: float  # tokens/second


# ── Scenarios: use large max_connections (the whole point is to find optimal c) ──
#
# Users want to set max_connections very high to maximize throughput.
# The question is: what happens when max_connections >> optimal, and can
# dynamic adjustment find the right level?
#
# "Ideal c" = RPM/60 * avg_latency (Little's Law)
#   Sonnet: avg_latency ≈ 1.5 + 300/60 = 6.5s → ideal c = RPM/60 * 6.5
#   Haiku:  avg_latency ≈ 0.6 + 150/120 = 1.85s → ideal c = RPM/60 * 1.85

# Scenario A: Tier 1 Sonnet, high connections
# 50 RPM → ideal c ≈ 0.83 * 6.5 ≈ 5.4
# With 100 connections → ~18× overprovisioned!
TIER1_SONNET = ScenarioConfig(
    name="Tier1 Sonnet (50 RPM, 100 conns)",
    account_rpm=50,
    account_itpm=30_000,
    account_otpm=8_000,
    max_connections=100,
    input_tokens_mean=500,
    input_tokens_std=200,
    output_tokens_mean=300,
    output_tokens_std=150,
    ttft_mean=1.5,
    ttft_std=0.5,
    output_speed=60.0,
)

# Scenario B: Tier 2 Sonnet, high connections
# 1000 RPM → ideal c ≈ 16.7 * 6.5 ≈ 108
# With 200 connections → ~2× overprovisioned
TIER2_SONNET = ScenarioConfig(
    name="Tier2 Sonnet (1000 RPM, 200 conns)",
    account_rpm=1000,
    account_itpm=450_000,
    account_otpm=90_000,
    max_connections=200,
    input_tokens_mean=500,
    input_tokens_std=200,
    output_tokens_mean=300,
    output_tokens_std=150,
    ttft_mean=1.5,
    ttft_std=0.5,
    output_speed=60.0,
)

# Scenario C: Tier 2 Haiku, high connections
# 1000 RPM → ideal c ≈ 16.7 * 1.85 ≈ 31
# With 200 connections → ~6× overprovisioned
TIER2_HAIKU = ScenarioConfig(
    name="Tier2 Haiku (1000 RPM, 200 conns)",
    account_rpm=1000,
    account_itpm=450_000,
    account_otpm=90_000,
    max_connections=200,
    input_tokens_mean=400,
    input_tokens_std=150,
    output_tokens_mean=150,
    output_tokens_std=80,
    ttft_mean=0.6,
    ttft_std=0.2,
    output_speed=120.0,
)

# Scenario D: Tier 1 Haiku, high connections — severely constrained
# 50 RPM → ideal c ≈ 0.83 * 1.85 ≈ 1.5
# With 100 connections → ~67× overprovisioned!
TIER1_HAIKU = ScenarioConfig(
    name="Tier1 Haiku (50 RPM, 100 conns)",
    account_rpm=50,
    account_itpm=50_000,
    account_otpm=10_000,
    max_connections=100,
    input_tokens_mean=400,
    input_tokens_std=150,
    output_tokens_mean=150,
    output_tokens_std=80,
    ttft_mean=0.6,
    ttft_std=0.2,
    output_speed=120.0,
)

# ─────────────────────────────────────────────────────────
# Backoff parameters (exact match to codebase)
# ─────────────────────────────────────────────────────────
BACKOFF_INITIAL = 3.0  # seconds
BACKOFF_MAX = 30 * 60  # 1800 seconds
BACKOFF_JITTER = 3.0  # ±3 seconds
BACKOFF_BASE = 2.0  # exponential base


def compute_backoff(attempt: int) -> float:
    """Tenacity-style exponential backoff with jitter.

    wait_exponential_jitter(initial=3, max=1800, jitter=3)
    Formula: min(initial * 2^attempt, max) + uniform(-jitter, jitter)
    """
    wait = min(BACKOFF_INITIAL * (BACKOFF_BASE**attempt), BACKOFF_MAX)
    wait += random.uniform(-BACKOFF_JITTER, BACKOFF_JITTER)
    return max(0.1, wait)  # floor at 0.1s


# ─────────────────────────────────────────────────────────
# Token Bucket Rate Limiter (Anthropic-style)
# ─────────────────────────────────────────────────────────


class TokenBucket:
    """Token bucket rate limiter.

    Anthropic docs: "Token bucket algorithm — capacity is continuously
    replenished up to maximum, not reset at fixed intervals."

    We model three independent buckets: RPM, ITPM, OTPM.
    """

    def __init__(self, capacity: float, refill_per_second: float) -> None:
        self.capacity = capacity
        self.tokens = capacity  # start full
        self.refill_per_second = refill_per_second
        self.last_refill_time = 0.0

    def refill(self, current_time: float) -> None:
        elapsed = current_time - self.last_refill_time
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
        self.last_refill_time = current_time

    def try_consume(self, amount: float, current_time: float) -> bool:
        self.refill(current_time)
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False

    def time_until_available(self, amount: float, current_time: float) -> float:
        """How long until `amount` tokens are available (for Retry-After)."""
        self.refill(current_time)
        if self.tokens >= amount:
            return 0.0
        deficit = amount - self.tokens
        return deficit / self.refill_per_second


class RateLimiter:
    """Combined RPM + ITPM + OTPM rate limiter for a shared account."""

    def __init__(self, cfg: ScenarioConfig) -> None:
        # Token buckets: capacity = per-minute limit, refill = limit/60 per second
        self.rpm_bucket = TokenBucket(cfg.account_rpm, cfg.account_rpm / 60.0)
        self.itpm_bucket = TokenBucket(cfg.account_itpm, cfg.account_itpm / 60.0)
        self.otpm_bucket = TokenBucket(cfg.account_otpm, cfg.account_otpm / 60.0)

    def try_request(
        self, input_tokens: float, current_time: float
    ) -> tuple[bool, float]:
        """Try to admit a request.

        Returns (success, retry_after_seconds).
        For RPM: consume 1 token.
        For ITPM: consume input_tokens at admission time.
        OTPM is checked in real-time during generation, but for simulation
        simplicity we check it at admission using expected output tokens.
        """
        # Check RPM first (often the binding constraint)
        self.rpm_bucket.refill(current_time)
        self.itpm_bucket.refill(current_time)
        self.otpm_bucket.refill(current_time)

        rpm_ok = self.rpm_bucket.tokens >= 1.0
        itpm_ok = self.itpm_bucket.tokens >= input_tokens

        if not rpm_ok or not itpm_ok:
            # Compute retry-after as max of the wait times
            retry_after = max(
                self.rpm_bucket.time_until_available(1.0, current_time),
                self.itpm_bucket.time_until_available(input_tokens, current_time),
            )
            return False, max(0.1, retry_after)

        # Consume tokens
        self.rpm_bucket.tokens -= 1.0
        self.itpm_bucket.tokens -= input_tokens
        return True, 0.0

    def consume_output_tokens(self, output_tokens: float, current_time: float) -> None:
        """Called when a request completes to consume OTPM budget."""
        self.otpm_bucket.refill(current_time)
        self.otpm_bucket.tokens -= output_tokens  # can go negative (over-budget)

    def consume_external_load(
        self, requests: float, input_tokens: float, output_tokens: float,
        current_time: float,
    ) -> None:
        """Simulate an external competitor consuming budget."""
        self.rpm_bucket.refill(current_time)
        self.itpm_bucket.refill(current_time)
        self.otpm_bucket.refill(current_time)
        self.rpm_bucket.tokens = max(0, self.rpm_bucket.tokens - requests)
        self.itpm_bucket.tokens = max(0, self.itpm_bucket.tokens - input_tokens)
        self.otpm_bucket.tokens = max(0, self.otpm_bucket.tokens - output_tokens)


# ─────────────────────────────────────────────────────────
# External competitor load profiles
# ─────────────────────────────────────────────────────────


def no_competitor(t: float) -> float:
    """No external load."""
    return 0.0


def steady_competitor(t: float) -> float:
    """Constant 40% of budget consumed by others."""
    return 0.4


def bursty_competitor(t: float) -> float:
    """Alternates: 0% for 60s, then 70% for 60s, repeating."""
    cycle = t % 120.0
    return 0.0 if cycle < 60.0 else 0.7


def ramp_competitor(t: float) -> float:
    """Linearly ramps from 0% to 60% over the simulation."""
    return min(0.6, t / 300.0 * 0.6)


# ─────────────────────────────────────────────────────────
# Request generation
# ─────────────────────────────────────────────────────────


def sample_request(cfg: ScenarioConfig) -> tuple[float, float, float]:
    """Sample (input_tokens, output_tokens, latency) for a request."""
    input_tok = max(50, random.gauss(cfg.input_tokens_mean, cfg.input_tokens_std))
    output_tok = max(20, random.gauss(cfg.output_tokens_mean, cfg.output_tokens_std))
    ttft = max(0.2, random.gauss(cfg.ttft_mean, cfg.ttft_std))
    generation_time = output_tok / cfg.output_speed
    latency = ttft + generation_time
    return input_tok, output_tok, latency


# ─────────────────────────────────────────────────────────
# Connection slot state
# ─────────────────────────────────────────────────────────


@dataclasses.dataclass
class ConnectionSlot:
    """A single connection slot (semaphore permit holder)."""

    busy_until: float = 0.0  # when this slot becomes free
    consecutive_failures: int = 0  # for exponential backoff
    state: Literal["idle", "in_flight", "backoff"] = "idle"

    # Track what's happening for stats
    current_request_input_tokens: float = 0.0
    current_request_output_tokens: float = 0.0


# ─────────────────────────────────────────────────────────
# Simulation engine
# ─────────────────────────────────────────────────────────


@dataclasses.dataclass
class SimResult:
    """Results from a single simulation run."""

    strategy: str
    competitor: str
    total_successful_requests: int
    total_failed_requests: int  # 429s encountered
    total_output_tokens: float
    total_input_tokens: float
    throughput_requests_per_min: float  # successful requests / elapsed minutes
    throughput_output_tokens_per_min: float
    avg_request_latency: float  # average time from slot acquiring request to completion
    p99_request_latency: float
    max_backoff_reached: float
    avg_effective_connections: float  # average non-backoff connections
    time_at_zero_effective: float  # seconds where all connections in backoff
    connection_trace: list[tuple[float, int]]  # (time, active_connections) for plotting


def simulate(
    strategy: str,
    cfg: ScenarioConfig,
    competitor_profile: callable,
    competitor_name: str,
    duration: float = 300.0,  # 5 minutes
    dt: float = 0.05,  # time step: 50ms
) -> SimResult:
    """Run one simulation with given strategy and competitor profile.

    Time advances in fixed steps of `dt` seconds. At each step:
    1. Apply external competitor load
    2. For each idle connection slot, attempt to send a request
    3. For each in-flight slot, check if request completed
    4. For each backoff slot, check if backoff expired
    5. Update dynamic connection limit (if applicable)
    """
    max_connections_config = cfg.max_connections
    rate_limiter = RateLimiter(cfg)

    # Strategy state
    current_max_connections = max_connections_config
    if strategy == "oracle":
        current_max_connections = max_connections_config  # will be set dynamically
    elif strategy in ("aimd", "aimd_retry_after"):
        current_max_connections = 2  # start low, ramp up

    slots: list[ConnectionSlot] = [
        ConnectionSlot() for _ in range(max_connections_config)
    ]

    # Stats tracking
    successful_requests = 0
    failed_requests = 0
    total_output_tokens = 0.0
    total_input_tokens = 0.0
    request_latencies: list[float] = []
    max_backoff = 0.0
    effective_conn_samples: list[int] = []
    time_at_zero = 0.0
    connection_trace: list[tuple[float, int]] = []

    # AIMD state (with TCP-style slow start)
    aimd_alpha = 2.0  # additive increase per window in steady state
    aimd_beta = 0.5  # multiplicative decrease factor
    aimd_window_successes = 0
    aimd_window_failures = 0
    aimd_window_start = 0.0
    aimd_window_duration = 3.0  # evaluate every 3 seconds
    aimd_cooldown_until = 0.0  # don't increase during cooldown after decrease
    aimd_min_connections = 1
    aimd_max_connections = max_connections_config
    aimd_phase = "slow_start"  # "slow_start" or "steady"
    aimd_ssthresh = max_connections_config  # slow start threshold

    t = 0.0
    last_competitor_update = 0.0
    competitor_update_interval = 1.0  # apply competitor load every 1s

    while t < duration:
        # ── 1. Apply external competitor load ──
        if t - last_competitor_update >= competitor_update_interval:
            load_fraction = competitor_profile(t)
            if load_fraction > 0:
                # Competitor consumes this fraction of the per-second refill
                ext_rpm = load_fraction * (cfg.account_rpm / 60.0) * competitor_update_interval
                ext_itpm = load_fraction * (cfg.account_itpm / 60.0) * competitor_update_interval
                ext_otpm = load_fraction * (cfg.account_otpm / 60.0) * competitor_update_interval
                rate_limiter.consume_external_load(ext_rpm, ext_itpm, ext_otpm, t)
            last_competitor_update = t

        # ── 2. Oracle: set connections to true available capacity ──
        if strategy == "oracle":
            available_fraction = 1.0 - competitor_profile(t)
            available_rpm = available_fraction * cfg.account_rpm / 60.0  # req/sec
            avg_latency = cfg.ttft_mean + cfg.output_tokens_mean / cfg.output_speed
            ideal_c = available_rpm * avg_latency
            current_max_connections = max(1, min(max_connections_config, round(ideal_c)))

        # ── 3. Count effective (non-backoff) connections ──
        active_count = sum(
            1
            for i, s in enumerate(slots)
            if i < current_max_connections and s.state != "backoff"
        )
        effective_conn_samples.append(active_count)
        if active_count == 0:
            time_at_zero += dt

        # Record trace every second
        if len(connection_trace) == 0 or t - connection_trace[-1][0] >= 1.0:
            connection_trace.append((t, current_max_connections))

        # ── 4. Process each slot ──
        for i, slot in enumerate(slots):
            # Skip slots beyond current dynamic limit
            if i >= current_max_connections:
                slot.state = "idle"
                slot.busy_until = 0.0
                slot.consecutive_failures = 0
                continue

            if slot.state == "in_flight":
                # Check if request completed
                if t >= slot.busy_until:
                    successful_requests += 1
                    total_output_tokens += slot.current_request_output_tokens
                    total_input_tokens += slot.current_request_input_tokens
                    req_latency = cfg.ttft_mean + slot.current_request_output_tokens / cfg.output_speed
                    request_latencies.append(req_latency)

                    # Consume output tokens from rate limiter
                    rate_limiter.consume_output_tokens(
                        slot.current_request_output_tokens, t
                    )

                    slot.state = "idle"
                    slot.consecutive_failures = 0

                    # AIMD: track success
                    if strategy in ("aimd", "aimd_retry_after"):
                        aimd_window_successes += 1

            elif slot.state == "backoff":
                # Check if backoff expired
                if t >= slot.busy_until:
                    slot.state = "idle"
                    # Don't reset consecutive_failures — they reset on success

            # If idle, try to send a new request
            if slot.state == "idle":
                input_tok, output_tok, latency = sample_request(cfg)

                success, retry_after = rate_limiter.try_request(input_tok, t)

                if success:
                    slot.state = "in_flight"
                    slot.busy_until = t + latency
                    slot.current_request_input_tokens = input_tok
                    slot.current_request_output_tokens = output_tok
                    slot.consecutive_failures = 0
                else:
                    # 429! Decide how to handle based on strategy
                    failed_requests += 1

                    if strategy in ("retry_after", "aimd_retry_after"):
                        # Use the retry-after value from the rate limiter
                        wait = retry_after + random.uniform(0, 0.5)  # small jitter
                    else:
                        # Current codebase behavior: exponential backoff
                        wait = compute_backoff(slot.consecutive_failures)

                    max_backoff = max(max_backoff, wait)
                    slot.state = "backoff"
                    slot.busy_until = t + wait
                    slot.consecutive_failures += 1

                    # AIMD: track failure
                    if strategy in ("aimd", "aimd_retry_after"):
                        aimd_window_failures += 1

        # ── 5. AIMD window evaluation (with TCP-style slow start) ──
        if strategy in ("aimd", "aimd_retry_after"):
            if t - aimd_window_start >= aimd_window_duration:
                total_in_window = aimd_window_successes + aimd_window_failures
                if total_in_window > 0:
                    failure_rate = aimd_window_failures / total_in_window

                    if failure_rate > 0.05:
                        # Congestion detected: multiplicative decrease
                        aimd_ssthresh = max(
                            aimd_min_connections,
                            int(current_max_connections * aimd_beta),
                        )
                        current_max_connections = aimd_ssthresh
                        aimd_phase = "steady"
                        aimd_cooldown_until = t + 5.0
                    elif t > aimd_cooldown_until:
                        if aimd_phase == "slow_start":
                            # Exponential growth: double connections
                            current_max_connections = min(
                                aimd_max_connections,
                                min(current_max_connections * 2, aimd_ssthresh),
                            )
                            # If we hit ssthresh, switch to steady
                            if current_max_connections >= aimd_ssthresh:
                                aimd_phase = "steady"
                        else:
                            # Steady state: additive increase
                            current_max_connections = min(
                                aimd_max_connections,
                                current_max_connections + int(aimd_alpha),
                            )

                # Reset window
                aimd_window_successes = 0
                aimd_window_failures = 0
                aimd_window_start = t

        t += dt

    # ── Compute final stats ──
    elapsed_minutes = duration / 60.0

    return SimResult(
        strategy=strategy,
        competitor=competitor_name,
        total_successful_requests=successful_requests,
        total_failed_requests=failed_requests,
        total_output_tokens=total_output_tokens,
        total_input_tokens=total_input_tokens,
        throughput_requests_per_min=successful_requests / elapsed_minutes,
        throughput_output_tokens_per_min=total_output_tokens / elapsed_minutes,
        avg_request_latency=(
            statistics.mean(request_latencies) if request_latencies else 0
        ),
        p99_request_latency=(
            sorted(request_latencies)[int(len(request_latencies) * 0.99)]
            if request_latencies
            else 0
        ),
        max_backoff_reached=max_backoff,
        avg_effective_connections=(
            statistics.mean(effective_conn_samples) if effective_conn_samples else 0
        ),
        time_at_zero_effective=time_at_zero,
        connection_trace=connection_trace,
    )


# ─────────────────────────────────────────────────────────
# Run all scenarios
# ─────────────────────────────────────────────────────────

STRATEGIES = [
    ("fixed", "Fixed (current)"),
    ("retry_after", "Fixed+RetryAfter"),
    ("aimd", "AIMD"),
    ("aimd_retry_after", "AIMD+RetryAfter"),
    ("oracle", "Oracle"),
]

COMPETITORS = [
    (no_competitor, "No competitor"),
    (steady_competitor, "Steady 40%"),
    (bursty_competitor, "Bursty 0%/70%"),
]

SCENARIOS = [TIER1_SONNET, TIER2_SONNET, TIER2_HAIKU, TIER1_HAIKU]

SIMULATION_DURATION = 300.0  # 5 minutes
NUM_TRIALS = 3  # Monte Carlo trials per scenario


def run_scenario(cfg: ScenarioConfig) -> None:
    """Run all strategy × competitor combinations for one scenario."""
    # Compute ideal connections for reference
    avg_latency = cfg.ttft_mean + cfg.output_tokens_mean / cfg.output_speed
    ideal_c = (cfg.account_rpm / 60.0) * avg_latency

    print(f"\n{'#'*80}")
    print(f"  SCENARIO: {cfg.name}")
    print(f"  Rate limit: {cfg.account_rpm} RPM | {cfg.account_itpm} ITPM | {cfg.account_otpm} OTPM")
    print(f"  Max connections configured: {cfg.max_connections}")
    print(f"  Avg request latency: {avg_latency:.1f}s")
    print(f"  Ideal connections (Little's Law): {ideal_c:.1f}")
    print(f"  Overprovision ratio: {cfg.max_connections / ideal_c:.1f}×")
    print(f"{'#'*80}")

    for competitor_fn, competitor_name in COMPETITORS:
        print(f"\n  {'─'*60}")
        print(f"  Competitor: {competitor_name}")
        print(f"  {'─'*60}")

        print(f"\n  {'Strategy':<22} {'Succ':>6} {'429s':>6} {'Req/m':>7} "
              f"{'MaxBO':>7} {'AvgEff':>7} {'T@0':>6}")
        print(f"  {'-'*62}")

        for strategy_key, strategy_label in STRATEGIES:
            trial_results: list[SimResult] = []
            for trial in range(NUM_TRIALS):
                random.seed(42 + trial)
                result = simulate(
                    strategy=strategy_key,
                    cfg=cfg,
                    competitor_profile=competitor_fn,
                    competitor_name=competitor_name,
                    duration=SIMULATION_DURATION,
                )
                trial_results.append(result)

            # Average across trials
            avg = lambda fn: statistics.mean(fn(r) for r in trial_results)
            succ = avg(lambda r: r.total_successful_requests)
            f429 = avg(lambda r: r.total_failed_requests)
            rpm = avg(lambda r: r.throughput_requests_per_min)
            mbo = avg(lambda r: r.max_backoff_reached)
            eff = avg(lambda r: r.avg_effective_connections)
            t0 = avg(lambda r: r.time_at_zero_effective)

            print(f"  {strategy_label:<22} {succ:>6.0f} {f429:>6.0f} {rpm:>7.1f} "
                  f"{mbo:>6.0f}s {eff:>7.1f} {t0:>5.0f}s")


if __name__ == "__main__":
    for scenario in SCENARIOS:
        run_scenario(scenario)
