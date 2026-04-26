# Inspect Viewer Bug Reproductions

Minimal `.eval` log files that demonstrate viewer bugs from the [code review findings](../SUMMARY.md). Each log embeds a description of the bug in the sample input — open it in the viewer and the first thing you see explains what to look for.

Each repro shows an **INFO: BUG-REPRO** panel at the top of the Transcript tab with the bug description, where to look, and expected vs observed behavior.

> **Browser-verified (per-finding rigorous pass):** each repro was opened in `inspect view` via Playwright, screenshotted, and independently inspected by a dedicated agent against the source. See [`verify/VERIFICATION.md`](verify/VERIFICATION.md) for the master report, [`verify/per-finding/`](verify/per-finding/) for individual evidence + screenshots, and [`verify/accuracy/`](verify/accuracy/) for the per-finding description-accuracy audit log.
>
> **39 CONFIRMED · 13 CONFIRMED_MINOR · 1 questionable-design (F10.6)** — 6 non-issues removed (see [`REMOVED.md`](REMOVED.md))

## Viewing

```bash
# View one batch:
uv run inspect view --log-dir findings/repros/logs/<batch>

# View all repros at once:
uv run inspect view --log-dir findings/repros/logs
```

Batches: `01-events`, `02-transform`, `10-chat`, `11-tools`, `20-samples`, `30-loglist`, `40-content`, `90-cross`

## Index

| Finding | Severity | Verification | Title | Batch | Task source | View instructions |
|---|---|---|---|---|---|---|
| F01.1 | HIGH | CONFIRMED | `ModelEventView` drops preceding user/system messages when input ends with an assistant message | 01-events | [task](tasks/01-events/F01.1_model_summary_drops_preceding.py) | Transcript → Model event → Summary tab |
| F01.2 | HIGH | CONFIRMED | `ToolChoiceView` renders literal `` `$ `` characters around function name | 01-events | [task](tasks/01-events/F01.2_tool_choice_literal_dollar.py) | Transcript → Model event → Tools tab → Tool Choice row |
| F01.3 | HIGH | CONFIRMED | `ScoreEditEventView` renders the `"UNCHANGED"` sentinel as real data | 01-events | [task](tasks/01-events/F01.3_score_edit_unchanged_sentinel.py) | Transcript → expand the Score Edit event |
| F02.1 | MEDIUM | CONFIRMED | Sandbox grouping is a no-op in span-based logs | 02-transform | [task](tasks/02-transform/F02.1_sandbox_grouping_noop.py) | Transcript → solver: three separate sandbox event rows |
| F02.2 / F02.3 | MEDIUM | CONFIRMED_MINOR ↓LOW | `injectScorersSpan` synthetic span keyed by wrong field | 02-transform | [task](tasks/02-transform/F02.2_F02.3_scorers_span_injection.py) | Transcript root level + Outline panel |
| F02.4 | MEDIUM | CONFIRMED | `unwrapNode` only adjusts immediate-child depth, not descendants | 02-transform | [task](tasks/02-transform/F02.4_unwrap_main_grandchild_depth.py) | Transcript → solver → compare grandchild indent depth |
| F02.5 | MEDIUM | CONFIRMED ↓LOW | `reduceDepth` recursion hard-codes `1`, breaking `skipThisNode` | 02-transform | [task](tasks/02-transform/F02.5_handoff_reducedepth_hardcoded.py) | Transcript → handoff tool call → agent-span indent |
| F03.4 | MEDIUM | CONFIRMED_MINOR ↓LOW | Outline toggle click also triggers select + navigate | 02-transform | [task](tasks/02-transform/F03.4_outline_chevron_bubbles.py) | Transcript Outline → click chevron (not label) |
| F03.5 | MEDIUM | CONFIRMED | Outline → transcript navigation silently fails when target is collapsed | 02-transform | [task](tasks/02-transform/F03.5_outline_nav_collapsed_target.py) | Transcript → collapse parent then click outline child |
| F04.2 | HIGH¹ | CONFIRMED | Tools tab hidden when exactly one tool is defined | 01-events | [task](tasks/01-events/F04.2_tools_tab_hidden_single_tool.py) | Transcript → Model event → panel tab strip |
| F04.5 | MEDIUM | CONFIRMED | `event.retries` and `event.cache` never displayed | 01-events | [task](tasks/01-events/F04.5_model_retries_cache_hidden.py) | Transcript → Model event → all tabs |
| F04.7 | MEDIUM | CONFIRMED | `output.error` and `stop_reason` not displayed | 01-events | [task](tasks/01-events/F04.7_stop_reason_output_error_hidden.py) | Transcript → Model event → Summary / All tabs |
| F04.8 | MEDIUM | CONFIRMED | Zero-valued token counts render as blank | 01-events | [task](tasks/01-events/F04.8_usage_zero_renders_blank.py) | Transcript → Model event → Usage tab |
| F05.1 | HIGH | CONFIRMED | `setPath` only descends into newly-created keys → wrong state diffs (= F03.1) | 01-events | [task](tasks/01-events/F05.1_state_setpath_wrong_diff.py) | Transcript → State Updated event → Diff view |
| F05.4 | MEDIUM | CONFIRMED_MINOR ↓LOW | `generatePreview` exact-count match prevents preview for multi-op signatures | 01-events | [task](tasks/01-events/F05.4_state_tools_preview_count.py) | Transcript → State Updated event (add_three_tools) |
| F05.5 | MEDIUM | CONFIRMED | `ScoreEditEventView` hides edited value when it is `0` / `false` / `""` | 01-events | [task](tasks/01-events/F05.5_score_edit_falsy_value_hidden.py) | Transcript → expand the three Score Edit events |
| F05.6 | LOW | CONFIRMED_MINOR | `ScoreEditEventView` Metadata `data-name` nested inside Summary → never a tab | 01-events | [task](tasks/01-events/F05.6_score_edit_metadata_not_tab.py) | Transcript → Score Edit event → tab strip |
| F05.9 | LOW | CONFIRMED_MINOR | `SandboxEventView` `ExecView` checks `=== null` but field is also optional | 01-events | [task](tasks/01-events/F05.9_sandbox_exec_cmd_undefined.py) | Transcript → Sandbox: Execute event |
| F05.11 | LOW | CONFIRMED_MINOR ↓INFO | `SampleInitEventView` never shows `sample.sandbox` or `sample.id` | 01-events | [task](tasks/01-events/F05.11_sample_init_omits_sandbox_id.py) | Transcript → Sample Init event |
| F05.12 | LOW | CONFIRMED_MINOR ↓INFO | `BranchEventView` discards `event.metadata` | 01-events | [task](tasks/01-events/F05.12_branch_event_omits_metadata.py) | Transcript → Branch event |
| F10.1 | HIGH | CONFIRMED ↓MEDIUM | Orphan tool messages are silently dropped | 10-chat | [task](tasks/10-chat/F10.1_orphan_tool_message_dropped.py) | Messages tab (default collapse mode) |
| F10.4 | MEDIUM | CONFIRMED | Citation superscript numbers don't match the citation list | 10-chat | [task](tasks/10-chat/F10.4_citation_numbering_mismatch.py) | Messages → assistant turn → compare superscripts vs list |
| F10.6 | MEDIUM | QUESTIONABLE_DESIGN² | `<think>` / `<internal>` blocks stripped silently from rendered text | 10-chat | [task](tasks/10-chat/F10.6_think_tags_stripped_silently.py) | Messages → assistant turn after the description |
| F10.7 | MEDIUM | CONFIRMED | System-message collapsing loses ids, metadata, timestamps | 10-chat | [task](tasks/10-chat/F10.7_system_messages_merged_hoisted.py) | Messages → note position of every system row |
| F11.1 | HIGH | CONFIRMED | Tool errors rendered identically to successful output | 11-tools | [task](tasks/11-tools/F11.1_tool_error_styled_as_success.py) | Transcript → expand both Tool events; also Messages tab |
| F11.2 | MEDIUM | CONFIRMED | `ToolCallError.type` is never displayed | 11-tools | [task](tasks/11-tools/F11.2_tool_error_type_dropped.py) | Messages → tool result; Transcript Tool event |
| F11.3 | HIGH | CONFIRMED_MINOR ↓LOW | Single content-object outputs are JSON-stringified instead of rendered | 11-tools | [task](tasks/11-tools/F11.3_bare_contentimage_stringified.py) | Transcript → expand both Tool events (bare vs list) |
| F11.4 | MEDIUM | CONFIRMED | `ToolCallContent.format` is ignored | 11-tools | [task](tasks/11-tools/F11.4_toolcallcontent_format_text_ignored.py) | Messages → tool call INPUT block |
| F11.7 | MEDIUM | CONFIRMED_MINOR ↓LOW | `ToolEvent.truncated` is never surfaced | 11-tools | [task](tasks/11-tools/F11.7_toolevent_truncated_not_shown.py) | Transcript → Tool event for `big_output` |
| F11.11 | MEDIUM | CONFIRMED | `ApprovalEventView` drops `modified`, `approver`, and `message` | 11-tools | [task](tasks/11-tools/F11.11_approval_event_drops_fields.py) | Transcript → Tool event → nested Approval event |
| F20.1 | MEDIUM | CONFIRMED | `SampleSummaryView` drops `limit`, `error`, `time` for `SampleSummary` inputs | 20-samples | [task](tasks/20-samples/F20.1_summary_header_drops_limit.py) | Sample → summary header row above tabs |
| F20.4 | MEDIUM | CONFIRMED | Scoring tab uses a different descriptor than list/header → inconsistent rendering | 20-samples | [task](tasks/20-samples/F20.4_scoring_tab_descriptor_diverges.py) | Compare score in Samples list vs header pill vs Scoring tab |
| F20.5 | LOW | CONFIRMED_MINOR ↓INFO | Scoring tab omits `target` | 20-samples | [task](tasks/20-samples/F20.5_scoring_tab_omits_target.py) | Sample → Scoring tab |
| F20.14 | LOW | CONFIRMED | Object/List score descriptors mis-format `0` and `false` | 20-samples | [task](tasks/20-samples/F20.14_list_score_zero_unformatted.py) | Samples list → list_scorer / dict_scorer columns |
| F21.1 | MEDIUM | CONFIRMED | `ScoreDescriptor.compare` is never called; score columns sort with ag-grid default | 20-samples | [task](tasks/20-samples/F21.1_score_column_sort_alphabetical.py) | Samples list → click score column header to sort |
| F21.2 | MEDIUM | CONFIRMED | `categories` shape mismatch breaks filter completions for categorical scores | 20-samples | [task](tasks/20-samples/F21.2_categorical_filter_undefined.py) | Samples list → filter input → autocomplete popover |
| F21.10 | MEDIUM | CONFIRMED | `SamplesGrid` (multi-log) and `SampleList` (single-log) format the same data differently | 20-samples | [task](tasks/20-samples/F21.10_multilog_grid_format_diverges.py) | Multi-log Samples grid vs single-log Samples tab |
| F30.1 | HIGH | CONFIRMED | Per-metric score columns collide when multiple scorers share a metric name | 30-loglist | [task](tasks/30-loglist/F30.1_metric_column_collision.py) | Log list view → dynamic score columns |
| F30.2 | MEDIUM | CONFIRMED | Status icons differ between log-list grid and log-detail header | 30-loglist | [task](tasks/30-loglist/F30.2_status_icon_mismatch.py) | Log list Status column vs detail-header status icon |
| F30.4 | MEDIUM | CONFIRMED | `SecondaryBar` is hidden entirely unless `status === "success"` | 30-loglist | [task](tasks/30-loglist/F30.4_secondary_bar_hidden.py) | Log header → secondary bar (compare to a success log) |
| F31.1 | HIGH¹ | CONFIRMED | `EvalConfig` is built but never rendered in Task tab | 30-loglist | [task](tasks/30-loglist/F31.1_eval_config_not_rendered.py) | Log → Task/Info tab → search for config fields |
| F31.2 | MEDIUM | CONFIRMED | Solver step params are never displayed | 30-loglist | [task](tasks/30-loglist/F31.2_solver_params_not_shown.py) | Log → Info tab → Plan card → Solvers column |
| F31.3 | LOW | CONFIRMED | `EvalPlan.finish` and `EvalPlan.name` are never surfaced | 30-loglist | [task](tasks/30-loglist/F31.3_plan_name_finish_hidden.py) | Log → Info tab → Plan card header |
| F40.1 | HIGH | CONFIRMED | RecordTree default-collapse logic never executes | 40-content | [task](tasks/40-content/F40.1_recordtree_never_collapses.py) | Sample → Metadata tab; Transcript → Score event metadata |
| F40.5 | MEDIUM | CONFIRMED_MINOR ↓LOW | `web_search` renderer output never displays (array fails `isValidElement`) | 40-content | [task](tasks/40-content/F40.5_web_search_array_fallthrough.py) | Transcript → Sample Init → Metadata sub-tab → web_search row |
| F80.10 | MEDIUM | CONFIRMED_MINOR ↓LOW | `formatPrettyDecimal` / `formatDecimalNoTrailingZeroes` break on scientific notation | 90-cross | [task](tasks/90-cross/F80.10_tiny_score_shows_zero.py) | Title-bar metric + log-list score + Samples score column |
| F90.1 | MEDIUM | CONFIRMED | Same screen, two timestamp formats: event panels vs everything app-side | 90-cross | [task](tasks/90-cross/F90.1_two_datetime_formats.py) | Sample header timestamp vs transcript event subtitles |
| F90.2 | LOW | CONFIRMED_MINOR | Sub-minute durations rendered with three different precisions | 90-cross | [task](tasks/90-cross/F90.2_three_duration_formats.py) | Sample Time pill vs transcript span vs Timeline card |
| F90.3 | MEDIUM | CONFIRMED | Transcript `ScoreEvent`/`ScoreEditEvent` bypass the score-descriptor system | 90-cross | [task](tasks/90-cross/F90.3_score_event_bypasses_descriptor.py) | Header score pill / Scoring tab vs Transcript Score event |
| F90.4 | MEDIUM | CONFIRMED | Multi-log `SamplesGrid` "Status" column shows the **log's** status, not the sample's | 90-cross | [task](tasks/90-cross/F90.4_multilog_grid_log_status.py) | Multi-log Samples grid → row for sample `F90.4-errored` |
| F90.5 | MEDIUM | CONFIRMED | Sample "Error" tab omits `error.message`; log "Error" tab shows it | 90-cross | [task](tasks/90-cross/F90.5_sample_error_tab_drops_message.py) | Sample → Error tab → search for marker string |
| F90.7 | LOW | CONFIRMED | `kModelNone` ("none/none") suppressed in title bar but rendered verbatim elsewhere | 90-cross | [task](tasks/90-cross/F90.7_kmodelnone_leaks.py) | Compare title bar (blank) vs log-list / Models tab |
| F90.14 | LOW | CONFIRMED | Metric/score precision differs across headlines, samples, and multi-log grid | 90-cross | [task](tasks/90-cross/F90.14_numeric_score_precision.py) | Title-bar metric vs Samples score vs multi-log grid |

¹ Downgraded to MEDIUM by [verification](../91-high-severity-verification.md); kept as HIGH here per original finding file.
² F10.6: stripping is documented + e2e-tested (PR #2324), but per user feedback the silent-data-loss behaviour is still undesirable — kept as a questionable-design repro rather than a confirmed bug.
↓ Per-finding verification recommends a severity downgrade — see [`verify/per-finding/`](verify/per-finding/) for rationale.

## Removed (non-issues)

6 repros were deleted after rigorous browser verification found the claimed bug does not exist (FALSE_POSITIVE) or is unreachable in `apps/inspect` (scout-only): **F03.2, F03.3, F20.6, F31.6, F10.2, F11.8**. See [`REMOVED.md`](REMOVED.md) for evidence links.

## Not reproducible via .eval

These findings cannot be exercised by a static `.eval` file (HTTP layer, browser storage, render-time side effects, or live-streaming-only paths). See [`NOT_REPRODUCIBLE.md`](NOT_REPRODUCIBLE.md) for full analysis.

| Finding | Reason | Alternative verification |
|---|---|---|
| F02.12 | `Event` is a closed pydantic discriminated union — `inspect eval` cannot emit an unknown event type | `satisfies never` exhaustiveness check, or hex-edit a `.eval` |
| F20.15 | `messagesFromEvents()` only runs on the live-streaming path (`runningSampleData`); completed logs always have `sample.messages` | Unit test feeding a `ModelEvent` with `output.choices: []` |
| F31.13 | Requires `evalStats.started_at` empty → only `status="started"` logs; mockllm always populates it | Open a still-running `.eval` and check Task tab → Start row |
| F40.6 | React render-time prop mutation; only observable via strict-mode double-render or shared object identity | Unit test: `render(<RenderedContent entry={e}/>); expect(e.value).toBe(42)` |
| F80.1 | Latent — `parseLogFileName().timestamp` is computed but never read; "Created" column comes from log header | Node REPL: `Date.parse("2024-01-01T12-34-56+00-00")` → `NaN` |

The four remaining HIGH findings without repros — **F50.1** (zustand store filter), **F51.1** (client-API promise race), **F70.1** / **F70.2** (Python HTTP backend) — are state-management / network-layer bugs that fall outside `.eval` rendering scope by definition; see [`HOWTO.md` §9](HOWTO.md#9-when-a-finding-is-not-reproducible-via-eval).

## Regenerating

```bash
# One file:
./findings/repros/run.sh findings/repros/tasks/<batch>/<file>.py <batch>

# All files:
for f in findings/repros/tasks/*/F*.py; do
  batch=$(basename "$(dirname "$f")")
  ./findings/repros/run.sh "$f" "$batch"
done
```

## Stats

| | |
|---|---|
| Task files | 53 |
| `.eval` files | 57 (verified, 0 broken, 0 orphans) |
| Multi-log repros | 4 (F21.10, F30.1, F90.4, F90.14 → 2 logs each) |
| Intentional `status=error` logs | 3 (F30.2, F30.4, F90.5) |
| Not reproducible via `.eval` | 5 |
| Removed (non-issues) | 6 — see [`REMOVED.md`](REMOVED.md) |
| **HIGH coverage** | **9 of 14** standing HIGH findings have `.eval` repros |

HIGH findings with repros: F01.1, F01.2, F01.3, F03.1 (via F05.1), F10.1, F11.1, F11.3, F30.1, F40.1.
HIGH findings without repros: F50.1, F51.1, F70.1, F70.2 (all outside `.eval` scope); F10.2 (scout-only, removed).
