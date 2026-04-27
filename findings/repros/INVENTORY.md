# Repro inventory

Generated 2026-04-24, updated 2026-04-27. All paths relative to `findings/repros/`.

**Summary: 53 `.eval` task files (57 `.eval` logs), 15 non-`.eval` repros (1 false-positive), 9 documented-only, 6 removed (non-issues), 0 failed.**

All `.eval` files >1KB (range 5.2K–23.5K). Multi-log repros (F21.10, F30.1, F90.4, F90.14) intentionally produce 2 files each. F30.2, F30.4, F90.5 intentionally produce `status=error` logs.

| Finding ID | Task file | .eval file(s) | Size | Status |
|---|---|---|---|---|
| F01.1 | `tasks/01-events/F01.1_model_summary_drops_preceding.py` | `logs/01-events/2026-04-24T21-30-29-00-00_F01.1-model-summary-drops-preceding_Mv3roJgC4pL38nLHk44Yob.eval` | 7.0K | generated |
| F01.2 | `tasks/01-events/F01.2_tool_choice_literal_dollar.py` | `logs/01-events/2026-04-24T21-30-21-00-00_F01.2-tool-choice-literal-dollar_cBHsSYJms6gdZEUMKZgQms.eval` | 5.2K | generated |
| F01.3 | `tasks/01-events/F01.3_score_edit_unchanged_sentinel.py` | `logs/01-events/2026-04-24T21-29-54-00-00_F01.3-score-edit-unchanged-sentinel_TUbS7U2guA9PhVrB96Rmfa.eval` | 6.6K | generated |
| F04.2 | `tasks/01-events/F04.2_tools_tab_hidden_single_tool.py` | `logs/01-events/2026-04-24T21-31-30-00-00_F04.2-tools-tab-hidden-single-tool_5zjqNzNwHjnwAYjrAMLA4D.eval` | 6.3K | generated |
| F04.5 | `tasks/01-events/F04.5_model_retries_cache_hidden.py` | `logs/01-events/2026-04-24T21-30-53-00-00_F04.5-model-retries-cache-hidden_FcsbkC2KxYGGyk44FoaYSW.eval` | 5.6K | generated |
| F04.7 | `tasks/01-events/F04.7_stop_reason_output_error_hidden.py` | `logs/01-events/2026-04-24T21-34-17-00-00_F04.7-stop-reason-output-error-hidden_hrrpeRXRbNgCoduC2ySZqV.eval` | 6.9K | generated |
| F04.8 | `tasks/01-events/F04.8_usage_zero_renders_blank.py` | `logs/01-events/2026-04-24T21-32-07-00-00_F04.8-usage-zero-renders-blank_b6UajYietimJ6wiuUTAcJk.eval` | 6.3K | generated |
| F05.1 | `tasks/01-events/F05.1_state_setpath_wrong_diff.py` | `logs/01-events/2026-04-24T21-49-13-00-00_F05.1-state-setpath-wrong-diff_HvnEAUCMcii777bkLweBth.eval` | 6.3K | generated |
| F05.4 | `tasks/01-events/F05.4_state_tools_preview_count.py` | `logs/01-events/2026-04-24T21-48-32-00-00_F05.4-state-tools-preview-count_mtAATh8gQdndBEUENUDuGT.eval` | 6.9K | generated |
| F05.5 | `tasks/01-events/F05.5_score_edit_falsy_value_hidden.py` | `logs/01-events/2026-04-24T21-45-38-00-00_F05.5-score-edit-falsy-value-hidden_eCDJ4RDL5vZm7qfeAGWgtd.eval` | 6.1K | generated |
| F05.6 | `tasks/01-events/F05.6_score_edit_metadata_not_tab.py` | `logs/01-events/2026-04-24T21-46-10-00-00_F05.6-score-edit-metadata-not-tab_jobFnH3mEeSeFWhcWBBkzr.eval` | 6.7K | generated |
| F05.9 | `tasks/01-events/F05.9_sandbox_exec_cmd_undefined.py` | `logs/01-events/2026-04-24T21-49-36-00-00_F05.9-sandbox-exec-cmd-undefined_EFF6A78Ziwm5jcwkLCRFwV.eval` | 5.8K | generated |
| F05.11 | `tasks/01-events/F05.11_sample_init_omits_sandbox_id.py` | `logs/01-events/2026-04-24T21-48-25-00-00_F05.11-sample-init-omits-sandbox-id_WUTX93ieQGBaFZMJ8LyySa.eval` | 7.0K | generated |
| F05.12 | `tasks/01-events/F05.12_branch_event_omits_metadata.py` | `logs/01-events/2026-04-24T21-48-18-00-00_F05.12-branch-event-omits-metadata_65JwyMmdjAosPF25ZvcgpE.eval` | 5.5K | generated |
| F02.1 | `tasks/02-transform/F02.1_sandbox_grouping_noop.py` | `logs/02-transform/2026-04-24T21-32-02-00-00_F02.1-sandbox-grouping-noop_dF4Aqz7SMYhoC36HD45N4H.eval` | 6.5K | generated |
| F02.2 / F02.3 | `tasks/02-transform/F02.2_F02.3_scorers_span_injection.py` | `logs/02-transform/2026-04-24T21-30-36-00-00_F02.2-F02.3-scorers-span-injection_fH9PzP6a5a8HmWjhhzpRBE.eval` | 8.1K | generated |
| F02.4 | `tasks/02-transform/F02.4_unwrap_main_grandchild_depth.py` | `logs/02-transform/2026-04-24T21-04-20-00-00_F02.4-unwrap-main-grandchild-depth_K44iu9kEGpACK9BBjjLynu.eval` | 7.1K | generated |
| F02.5 | `tasks/02-transform/F02.5_handoff_reducedepth_hardcoded.py` | `logs/02-transform/2026-04-24T21-30-43-00-00_F02.5-handoff-reducedepth-hardcoded_E6bUF6hEQK6C9rTeMdGoik.eval` | 7.2K | generated |
| F03.4 | `tasks/02-transform/F03.4_outline_chevron_bubbles.py` | `logs/02-transform/2026-04-24T21-30-13-00-00_F03.4-outline-chevron-bubbles_N3iKgYWwNE9zupvPtLkDCW.eval` | 8.1K | generated |
| F03.5 | `tasks/02-transform/F03.5_outline_nav_collapsed_target.py` | `logs/02-transform/2026-04-24T21-04-30-00-00_F03.5-outline-nav-collapsed-target_TezLV2d8GwdG7UwMVsj94X.eval` | 7.7K | generated |
| F10.1 | `tasks/10-chat/F10.1_orphan_tool_message_dropped.py` | `logs/10-chat/2026-04-24T21-47-18-00-00_F10.1-orphan-tool-message-dropped_EZrxkeKoJ5rAzaL2mZ8Se2.eval` | 6.5K | generated |
| F10.4 | `tasks/10-chat/F10.4_citation_numbering_mismatch.py` | `logs/10-chat/2026-04-24T21-51-37-00-00_F10.4-citation-numbering-mismatch_Cdz5vb7gsqCFskVWu54wJp.eval` | 5.7K | generated |
| F10.6 | `tasks/10-chat/F10.6_think_tags_stripped_silently.py` | `logs/10-chat/2026-04-24T21-51-50-00-00_F10.6-think-tags-stripped-silently_2h4AcTayRDZBNzLfPVsmPu.eval` | 6.4K | generated |
| F10.7 | `tasks/10-chat/F10.7_system_messages_merged_hoisted.py` | `logs/10-chat/2026-04-24T21-50-07-00-00_F10.7-system-messages-merged-hoisted_eJGff7TBPiZS8gDEDpz7mU.eval` | 6.8K | generated |
| F11.1 | `tasks/11-tools/F11.1_tool_error_styled_as_success.py` | `logs/11-tools/2026-04-24T21-49-37-00-00_F11.1-tool-error-styled-as-success_HGB9xgJkAFjgQoqcoyJT4K.eval` | 8.1K | generated |
| F11.2 | `tasks/11-tools/F11.2_tool_error_type_dropped.py` | `logs/11-tools/2026-04-24T21-48-29-00-00_F11.2-tool-error-type-dropped_Zcse3VN6qv2UQ7tJMioYhD.eval` | 5.5K | generated |
| F11.3 | `tasks/11-tools/F11.3_bare_contentimage_stringified.py` | `logs/11-tools/2026-04-24T21-48-34-00-00_F11.3-bare-contentimage-stringified_VmJR4p2Ed7qjH8iQgefzoU.eval` | 6.4K | generated |
| F11.4 | `tasks/11-tools/F11.4_toolcallcontent_format_text_ignored.py` | `logs/11-tools/2026-04-24T22-05-39-00-00_F11.4-toolcallcontent-format-text-ignored_DyjLpMoi3ifnKjPEfums8U.eval` | 5.5K | generated |
| F11.7 | `tasks/11-tools/F11.7_toolevent_truncated_not_shown.py` | `logs/11-tools/2026-04-24T22-04-11-00-00_F11.7-toolevent-truncated-not-shown_7GvambwmAkSJEtffCRXCyR.eval` | 7.6K | generated |
| F11.11 | `tasks/11-tools/F11.11_approval_event_drops_fields.py` | `logs/11-tools/2026-04-24T22-08-09-00-00_F11.11-approval-event-drops-fields_T8aZmHNzVgiy6a6rN74n2E.eval` | 8.0K | generated |
| F20.1 | `tasks/20-samples/F20.1_summary_header_drops_limit.py` | `logs/20-samples/2026-04-24T22-05-05-00-00_F20.1-summary-header-drops-limit_mhfo2B8PvSjhePjBpCaar6.eval` | 6.0K | generated |
| F20.4 | `tasks/20-samples/F20.4_scoring_tab_descriptor_diverges.py` | `logs/20-samples/2026-04-24T22-06-04-00-00_F20.4-scoring-tab-descriptor-diverges_coWVnQdSqefbBmxNTJN439.eval` | 12.8K | generated |
| F20.5 | `tasks/20-samples/F20.5_scoring_tab_omits_target.py` | `logs/20-samples/2026-04-24T22-05-53-00-00_F20.5-scoring-tab-omits-target_8fvt9CJtHgBCPAxS6QVrfH.eval` | 6.4K | generated |
| F20.14 | `tasks/20-samples/F20.14_list_score_zero_unformatted.py` | `logs/20-samples/2026-04-24T22-10-48-00-00_F20.14-list-score-zero-unformatted_c8tC2GxATuHymDB8CkfWgw.eval` | 12.8K | generated |
| F21.1 | `tasks/20-samples/F21.1_score_column_sort_alphabetical.py` | `logs/20-samples/2026-04-24T22-05-52-00-00_F21.1-score-column-sort-alphabetical_inGUngb8MEgErK9J6CNBFW.eval` | 14.6K | generated |
| F21.2 | `tasks/20-samples/F21.2_categorical_filter_undefined.py` | `logs/20-samples/2026-04-24T22-06-50-00-00_F21.2-categorical-filter-undefined_AfidJqdQwh2LbWoeN5bUVT.eval` | 12.2K | generated |
| F21.10 | `tasks/20-samples/F21.10_multilog_grid_format_diverges.py` | `logs/20-samples/2026-04-24T22-10-11-00-00_F21.10-multilog-a_e4tF4mzpN5XTa53ELAGjw9.eval`<br>`logs/20-samples/2026-04-24T22-10-11-00-00_F21.10-multilog-b_Sm26Am7FC6FVf5cQxhwFM6.eval` | 10.5K / 10.5K | generated |
| F30.1 | `tasks/30-loglist/F30.1_metric_column_collision.py` | `logs/30-loglist/2026-04-24T22-07-54-00-00_F30.1-metric-collision-a_W9aQnVqiEn7J3o8RHMrLxF.eval`<br>`logs/30-loglist/2026-04-24T22-07-55-00-00_F30.1-metric-collision-b_fu2pzSx9o6kpFscnYcDtZk.eval` | 7.3K / 7.3K | generated |
| F30.2 | `tasks/30-loglist/F30.2_status_icon_mismatch.py` | `logs/30-loglist/2026-04-24T22-06-43-00-00_F30.2-status-icon-mismatch-ERROR_E4w9MELqaeGq4Nwp4kUwBV.eval` | 8.7K | generated |
| F30.4 | `tasks/30-loglist/F30.4_secondary_bar_hidden.py` | `logs/30-loglist/2026-04-24T22-09-01-00-00_F30.4-secondary-bar-hidden-ERROR_n2HvmRHwpGpxsJjGdWCsgF.eval` | 9.2K | generated |
| F31.1 | `tasks/30-loglist/F31.1_eval_config_not_rendered.py` | `logs/30-loglist/2026-04-24T22-18-21-00-00_F31.1-eval-config-not-rendered_BCb8zgWv5b5kzzY6kymJP8.eval` | 23.5K | generated |
| F31.2 | `tasks/30-loglist/F31.2_solver_params_not_shown.py` | `logs/30-loglist/2026-04-24T22-21-14-00-00_F31.2-solver-params-not-shown_W8gVvrD34sWfL8ZdEsBiH9.eval` | 6.6K | generated |
| F31.3 | `tasks/30-loglist/F31.3_plan_name_finish_hidden.py` | `logs/30-loglist/2026-04-24T22-24-55-00-00_F31.3-plan-name-finish-hidden_SxGemb9uvNvTW7sRakU8yV.eval` | 7.5K | generated |
| F40.1 | `tasks/40-content/F40.1_recordtree_never_collapses.py` | `logs/40-content/2026-04-24T22-19-37-00-00_F40.1-recordtree-never-collapses_S8VDLkZeVJeUhqknTXEZ9r.eval` | 6.6K | generated |
| F40.5 | `tasks/40-content/F40.5_web_search_array_fallthrough.py` | `logs/40-content/2026-04-24T22-20-02-00-00_F40.5-web-search-array-fallthrough_Q6ezd3gaUUPcJyf9FysxGa.eval` | 6.8K | generated |
| F80.10 | `tasks/90-cross/F80.10_tiny_score_shows_zero.py` | `logs/90-cross/2026-04-24T22-19-08-00-00_F80.10-tiny-score-shows-zero_JiStvGguzYRQTh2GdM3Z4x.eval` | 7.7K | generated |
| F90.1 | `tasks/90-cross/F90.1_two_datetime_formats.py` | `logs/90-cross/2026-04-24T22-20-49-00-00_F90.1-two-datetime-formats_nBQT5aaRpzFUXHtciuWfsH.eval` | 6.7K | generated |
| F90.2 | `tasks/90-cross/F90.2_three_duration_formats.py` | `logs/90-cross/2026-04-24T22-23-22-00-00_F90.2-three-duration-formats_H7NS7cwmrMyAjc5YePSUug.eval` | 6.9K | generated |
| F90.3 | `tasks/90-cross/F90.3_score_event_bypasses_descriptor.py` | `logs/90-cross/2026-04-24T22-21-35-00-00_F90.3-score-event-bypasses-descriptor_FA8MmUZWRZ7RdFmmWWpdys.eval` | 7.1K | generated |
| F90.4 | `tasks/90-cross/F90.4_multilog_grid_log_status.py` | `logs/90-cross/2026-04-24T22-20-03-00-00_F90.4-multilog-grid-log-status-A_dtg6FJiY92gdyaPcqjyMds.eval`<br>`logs/90-cross/2026-04-24T22-20-03-00-00_F90.4-multilog-grid-log-status-B_gpnPaDptiSHzPTMw9HyHcz.eval` | 11.7K / 7.5K | generated |
| F90.5 | `tasks/90-cross/F90.5_sample_error_tab_drops_message.py` | `logs/90-cross/2026-04-24T22-20-26-00-00_F90.5-sample-error-tab-drops-message_LsxmeecEs3dGTTRmKqhjTJ.eval` | 8.1K | generated |
| F90.7 | `tasks/90-cross/F90.7_kmodelnone_leaks.py` | `logs/90-cross/2026-04-24T22-21-39-00-00_F90.7-kmodelnone-leaks_K9dX7vVvUscp9dfdpX26Pr.eval` | 5.9K | generated |
| F90.14 | `tasks/90-cross/F90.14_numeric_score_precision.py` | `logs/90-cross/2026-04-24T22-23-06-00-00_F90.14-numeric-score-precision-A_gZNqdQccjR2zWKRCoCALxH.eval`<br>`logs/90-cross/2026-04-24T22-23-06-00-00_F90.14-numeric-score-precision-B_RyTiWhx4ScjqEXwPQuGkKG.eval` | 7.2K / 7.2K | generated |
| F02.12 | see [Non-.eval repros](#non-eval-repros) | `logs/02-transform/F02.12-unknown-event-type.eval` | 6.6K | post-processed |
| F20.15 | see [Non-.eval repros](#non-eval-repros) | — | — | tsx script |
| F31.13 | see [Non-.eval repros](#non-eval-repros) | `logs/30-loglist/F31.13-missing-started-at.eval` | 6.2K | post-processed |
| F40.6 | see [Non-.eval repros](#non-eval-repros) | — | — | node script |
| F80.1 | see [Non-.eval repros](#non-eval-repros) | — | — | tsx script |
| F03.2 | — | — | — | removed (FALSE_POSITIVE) |
| F03.3 | — | — | — | removed (FALSE_POSITIVE) |
| F10.2 | see [Non-.eval repros](#non-eval-repros) | — | — | scout-only — vitest unit repro |
| F11.8 | see [Non-.eval repros](#non-eval-repros) | — | — | scout-only — vitest unit repro |
| F20.6 | — | — | — | removed (FALSE_POSITIVE) |
| F31.6 | — | — | — | removed (FALSE_POSITIVE) |

## Non-.eval repros

Findings reproduced via pytest, standalone Node/tsx scripts, post-processed `.eval` zips, or Playwright interaction scripts — i.e. anything that does **not** go through `run.sh`. See per-batch READMEs for full details.

| Finding ID | Repro type | Path | Run command | Status |
|---|---|---|---|---|
| F70.1 | pytest | `tasks/70-backend/test_F70_repros.py` | `uv run python -m pytest findings/repros/tasks/70-backend/test_F70_repros.py -v` | **CONFIRMED** |
| F70.2 | pytest | `tasks/70-backend/test_F70_repros.py` | ″ | **CONFIRMED** |
| F70.3 | pytest | `tasks/70-backend/test_F70_repros.py` | ″ | **CONFIRMED** |
| F70.4 | pytest | `tasks/70-backend/test_F70_repros.py` | ″ | **CONFIRMED** |
| F50.1 | tsx script | `tasks/51-clients/F50.1_isLargeSample_always_true.ts` | `bash findings/repros/tasks/51-clients/run-all.sh` | **CONFIRMED** |
| F51.1 | node script | `tasks/51-clients/F51.1_pending_log_promise_race.mjs` | ″ | **CONFIRMED** |
| F20.15 | tsx script | `tasks/51-clients/F20.15_messagesFromEvents_empty_choices.ts` | ″ | **CONFIRMED** |
| F40.6 | node script | `tasks/51-clients/F40.6_renderer_mutates_entry.mjs` | ″ | **CONFIRMED** |
| F80.1 | tsx script | `tasks/51-clients/F80.1_parseLogFileName_invalid_date.ts` | ″ | **CONFIRMED** |
| F02.12 | post-processed `.eval` | `tasks/02-transform/F02.12_unknown_event_type.py` | `uv run --frozen python findings/repros/tasks/02-transform/F02.12_unknown_event_type.py` | **CONFIRMED** |
| F31.13 | post-processed `.eval` | `tasks/30-loglist/F31.13_missing_started_at.py` | `uv run --frozen python findings/repros/tasks/30-loglist/F31.13_missing_started_at.py` | **CONFIRMED** |
| F50.3 | playwright + `.eval` | `tasks/50-state/F50.3_verify.py` | `uv run --with playwright python findings/repros/tasks/50-state/F50.3_verify.py` | **CONFIRMED (partial)** — unbounded growth real; positional-collision claim wrong |
| F50.9 | playwright | `tasks/50-state/F50.9_indexeddb_cache_miss.py` | `uv run --with playwright python findings/repros/tasks/50-state/F50.9_indexeddb_cache_miss.py` | **FALSE_POSITIVE** — caller pre-resolves path |
| F10.2 | vitest unit test (scout) | `tasks/10-chat/F10.2_F11.8_scout_only.md` | `pnpm --filter @tsmono/inspect-components test` (after dropping the test file in) | **CONFIRMED (scout-only)** |
| F11.8 | vitest unit test (scout) | `tasks/10-chat/F10.2_F11.8_scout_only.md` | ″ | **CONFIRMED (scout-only)** |

See [`DOCUMENTED_ONLY.md`](DOCUMENTED_ONLY.md) for 9 perf / race-condition findings (F21.5, F40.7, F02.13, F70.9, F50.7, F51.7, F60.28, F60.36, F60.37) that have a written repro recipe but no executable artifact, and [`REMOVED.md`](REMOVED.md) for the 6 removed non-issues.
