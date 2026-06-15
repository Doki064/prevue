# Phase 7: Customization & Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-14
**Phase:** 7-Customization & Hardening
**Areas discussed:** Consumer skill override (SKIL-03), Injection verification (SECR-02), Token transparency (OUTP-04), Large-PR budget (DIFF-03), plus follow-up gray areas (partial-coverage gate, fallback cost, no-fit edge, pack×skill scope, consumer-skill caps, framework docs)

---

## Area selection

User selected **all four** gray areas (SKIL-03, SECR-02, OUTP-04, DIFF-03).

---

## Consumer Skill Override (SKIL-03)

| Question | Options | Outcome |
|----------|---------|---------|
| Override granularity | Bundle-dir replace / Per-file merge | User: "what if consumer wants to add files to the same domain (e.g. security) alongside built-in?" → **per-file merge keyed on `bundle/filename`** (D-02) |
| Malformed consumer skill | Skip + disclose / Fail-closed | **Fail-closed**, + user asked for an exclude config → added `skills.exclude` (D-04/D-05) |
| Custom-bundle requirements | Drop .md only / Require route entry | **Drop .md only** — glob is the trigger, no routing entry needed (D-03) |

**Notes:** User noted Q1/Q3 overlapped (correct — same glob-based mechanism). Resolved the "malformed override, want built-in back" edge case: **delete the override file** (built-in is the fallback layer); `exclude` stays "don't load this path, period" (D-06). Confirmed override key = `bundle/filename`; exclude addressed the same way; exclude applies to both built-in and consumer skills.

---

## Injection Verification (SECR-02)

| Question | Options | Outcome |
|----------|---------|---------|
| Vectors to red-team | diff content / filenames / classify prompt / engine tool access | **All four** ("use recommended for best privacy and security") (D-08) |
| Defense posture | Verify+document only / Verify+add hardening | **Verify + add hardening** (D-10) |
| Durable artifact | Tests + threat doc / One-time report | **Adversarial CI tests + SECURITY.md threat model** (D-12) |

**Notes:** Baseline already strong — `DiffBundle` excludes PR title/body; `prompt.py` fences untrusted data. Phase 7 proves + hardens.

---

## Token Transparency (OUTP-04)

| Question | Options | Outcome |
|----------|---------|---------|
| Token source | Hybrid actual-else-est / Estimated only / Actual only | **Hybrid actual-else-est** (D-13) |
| Skipped-side display | Loaded+skipped count / Loaded+full list / Loaded+total | User asked for per-bundle grouping → **per-bundle compact ratios** (refinement of count) (D-15) |
| Cost breakdown | Split review+classify / Single total / Full per-stage | **Split review + classify** (D-14) |

**Notes:** User asked whether skills are bundle-categorized — yes (Bundles line exists), refined to `security 2/3 · frontend 1/4 …` ratios.

---

## Large-PR Budget (DIFF-03)

| Question | Options | Outcome |
|----------|---------|---------|
| Packing priority | Skill/risk-weighted / Smallest-diff first / Consumer path priority | **Skill/risk-weighted** (D-18) |
| Budget sizing + reserve | Config knob + reserve / Derive from model window / Fixed cap | **Config knob + output reserve** (D-20) |
| Skipped-file disclosure | Count + collapsible / Count only / Full inline | **Count + collapsible list** (D-21) |
| Pack × skill scope | Full changed set / Packed set only | **Packed set only** + explicit disclosure that coverage reflects reviewed files (D-16/19) |
| Partial-coverage gate | No green when incomplete / Reviewed-files verdict | **No green when incomplete** → neutral (D-23) |
| Classify-fallback cost | Cap calls / No cap | Found P6 already batches at 100/call → **keep batched + scope to packed set** (D-22) |
| No-file-fits edge | Skip + neutral disclosure / Truncate top file | **Skip + neutral disclosure** (D-24) |

**Notes:** Packing is file-granular, no mid-file truncation (D-17). User emphasized a partial review must never show green for a security gate. User questioned per-file LLM calls as "outrageous" — confirmed already batched at `CLASSIFY_BATCH_SIZE=100`.

---

## Consumer-skill guardrails + framework docs

| Question | Options | Outcome |
|----------|---------|---------|
| Consumer skill caps | Size + count caps / No caps | **Size + count caps**, over-cap skipped + disclosed (D-07) |
| Consumer docs deliverable | Authoring + config guide / Minimal inline | **Authoring + config guide** (D-25) |

---

## Claude's Discretion

- Exact `.github/prevue.yml` field names (`skills.exclude`, skill caps, `review.max_input_tokens`, output reserve).
- Token-estimate heuristic constant + estimator placement.
- Final hardening set within D-10.
- Non-canonical bundle display/ordering rule.
- Exact consumer-skill cap values.
- classify↔pack sequencing implementation.
- Skipped-file tie-breaking within skill/risk priority.

## Deferred Ideas

- **Incremental / lifecycle review** (user-raised): review only newest diff since last-reviewed SHA; dedupe commits that address prior findings. Maps to v2 LIFE-01/02/04. Recommended as its own phase under a v2 "Review Lifecycle" milestone after v1 ships.
- Functional Gemini adapter (skeleton) — carried from P6.
- GitHub App installation-token auth — carried from P6.
- Per-engine timeout/budget tuning — carried from P5/P6.
