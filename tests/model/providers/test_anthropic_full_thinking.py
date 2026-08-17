"""Tests for routing of thinking blocks under the dev full-thinking beta.

With the `dev-full-thinking-2025-05-14` beta header the Anthropic API returns
the full raw chain of thought (not a summary), so it must land in
`ContentReasoning.reasoning` rather than `ContentReasoning.summary`.
"""

from anthropic.types import ThinkingBlock

from inspect_ai._util.content import ContentReasoning
from inspect_ai.model._providers.anthropic import (
    DEV_FULL_THINKING_BETA,
    AnthropicAPI,
    content_and_tool_calls_from_assistant_content_blocks,
    init_sample_anthropic_assistant_internal,
    message_block_params,
)

THINKING = "Let me think about this problem step by step..."
SIGNATURE = "EropAkQBDMftjJ4rz1kJ8x2VtQ=="


def thinking_block() -> ThinkingBlock:
    return ThinkingBlock(type="thinking", thinking=THINKING, signature=SIGNATURE)


def test_anthropic_thinking_is_summary_by_default() -> None:
    init_sample_anthropic_assistant_internal()
    content, _ = content_and_tool_calls_from_assistant_content_blocks(
        [thinking_block()], []
    )
    assert len(content) == 1
    reasoning = content[0]
    assert isinstance(reasoning, ContentReasoning)
    assert reasoning.summary == THINKING
    assert reasoning.reasoning == SIGNATURE
    assert reasoning.redacted


def test_anthropic_full_thinking_routes_to_reasoning() -> None:
    init_sample_anthropic_assistant_internal()
    content, _ = content_and_tool_calls_from_assistant_content_blocks(
        [thinking_block()], [], full_thinking=True
    )
    assert len(content) == 1
    reasoning = content[0]
    assert isinstance(reasoning, ContentReasoning)
    assert reasoning.reasoning == THINKING
    assert reasoning.signature == SIGNATURE
    assert reasoning.summary is None
    assert not reasoning.redacted


async def test_anthropic_full_thinking_replays_from_internal() -> None:
    init_sample_anthropic_assistant_internal()
    content, _ = content_and_tool_calls_from_assistant_content_blocks(
        [thinking_block()], [], full_thinking=True
    )
    reasoning = content[0]
    assert isinstance(reasoning, ContentReasoning)
    blocks = await message_block_params(reasoning)
    assert blocks == [
        {"type": "thinking", "thinking": THINKING, "signature": SIGNATURE}
    ]


async def test_anthropic_full_thinking_replays_without_internal() -> None:
    # simulate reasoning restored from a log (no cached thinking blocks)
    init_sample_anthropic_assistant_internal()
    reasoning = ContentReasoning(reasoning=THINKING, signature=SIGNATURE)
    blocks = await message_block_params(reasoning)
    assert blocks == [
        {"type": "thinking", "thinking": THINKING, "signature": SIGNATURE}
    ]


async def test_anthropic_summary_thinking_replays_without_internal() -> None:
    init_sample_anthropic_assistant_internal()
    reasoning = ContentReasoning(summary=THINKING, reasoning=SIGNATURE, redacted=True)
    blocks = await message_block_params(reasoning)
    assert blocks == [
        {"type": "thinking", "thinking": THINKING, "signature": SIGNATURE}
    ]


def test_anthropic_full_thinking_request_detection() -> None:
    api = AnthropicAPI(model_name="claude-sonnet-4-6", api_key="fake-api-key")
    assert not api.is_full_thinking_request({})
    assert not api.is_full_thinking_request(
        {"extra_headers": {"anthropic-beta": "interleaved-thinking-2025-05-14"}}
    )
    assert api.is_full_thinking_request(
        {
            "extra_headers": {
                "anthropic-beta": f"interleaved-thinking-2025-05-14,{DEV_FULL_THINKING_BETA}"
            }
        }
    )


def test_anthropic_full_thinking_via_betas_model_arg() -> None:
    from inspect_ai.model._generate_config import GenerateConfig

    api = AnthropicAPI(
        model_name="claude-sonnet-4-6",
        api_key="fake-api-key",
        betas=[DEV_FULL_THINKING_BETA],
    )
    _, _, headers, betas = api.completion_config(GenerateConfig(max_tokens=1024))
    assert DEV_FULL_THINKING_BETA in betas


def test_anthropic_beta_headers_merged_into_betas() -> None:
    from inspect_ai.model._generate_config import GenerateConfig

    api = AnthropicAPI(model_name="claude-sonnet-4-6", api_key="fake-api-key")
    config = GenerateConfig(
        max_tokens=1024, extra_headers={"anthropic-beta": DEV_FULL_THINKING_BETA}
    )
    _, _, headers, betas = api.completion_config(config)
    assert DEV_FULL_THINKING_BETA in betas
    # merged into betas so it is not clobbered by the combined beta header
    assert "anthropic-beta" not in headers
