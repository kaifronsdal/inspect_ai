# [Area Name]

**Reviewer scope:** [files/directories reviewed]
**Date:** 2026-04-22

---

## Summary

[2-4 sentence overview: what was reviewed, overall health, key concerns]

---

## Findings

### [ID] — [Short title]

- **Severity:** HIGH | MEDIUM | LOW | INFO
- **Location:** `path/to/file.tsx:123` (and related: `other/file.ts:45`)
- **Category:** correctness | event-display | consistency | collapse-expand | dead-code | fallback-hiding-errors | code-smell | styling | a11y | perf

**Description:**
[What the issue is. Be specific about what is wrong.]

**Evidence:**
```
[relevant code snippet, ≤15 lines]
```

**Why it matters / impact:**
[What the user sees or what could go wrong. If it's a display inconsistency, describe both sides.]

**Suggested fix:**
[Optional. Brief.]

---

### [ID] — [Next finding]
...

---

## Files reviewed

- [ ] `path/one.tsx` — [one-line note]
- [ ] `path/two.tsx` — [one-line note]

## Open questions / needs verification

- [Anything the reviewer was unsure about that another agent should verify]
