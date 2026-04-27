# Removed Repros

These repros were deleted because rigorous browser verification found the claimed bug does not exist (FALSE_POSITIVE) or is unreachable in the inspect viewer (scout-only). The original findings should be downgraded/removed.

| ID | Reason | Evidence |
|---|---|---|
| F03.2 | FALSE_POSITIVE — checkbox toggles correctly (stale-closure makes double-fire idempotent) | [per-finding/F03.2.md](verify/per-finding/F03.2.md) |
| F03.3 | FALSE_POSITIVE — breadcrumb guard drops phantom prefixes; renders correctly | [per-finding/F03.3.md](verify/per-finding/F03.3.md) |
| F20.6 | FALSE_POSITIVE — limit value shown in SampleLimitEvent message ("limit: 12,345") | [per-finding/F20.6.md](verify/per-finding/F20.6.md) |
| F31.6 | FALSE_POSITIVE — config.epochs always ≥1 via eval_config_defaults(); `\|\|0` unreachable | [per-finding/F31.6.md](verify/per-finding/F31.6.md) |
| F10.2 | scout-only — collapseToolMessages=false path; inspect renders error correctly | [per-finding/F10.2.md](verify/per-finding/F10.2.md) · [non-.eval repro](tasks/10-chat/F10.2_F11.8_scout_only.md) |
| F11.8 | scout-only — same gate; ContentData renders correctly in inspect | [per-finding/F11.8.md](verify/per-finding/F11.8.md) · [non-.eval repro](tasks/10-chat/F10.2_F11.8_scout_only.md) |

The per-finding verification reports and screenshots are preserved in [`verify/per-finding/`](verify/per-finding/) and [`verify/accuracy/`](verify/accuracy/).
