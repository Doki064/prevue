# Phase 6: Reusable Workflow & Hybrid Classification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-13
**Phase:** 6-Reusable Workflow & Hybrid Classification
**Areas discussed:** Reusable workflow contract, Config (inputs vs prevue.yml), LLM classification fallback, Skip conditions

---

## Reusable Workflow Contract (WKFL-01/02/04)

### Workflow file structure
| Option | Description | Selected |
|--------|-------------|----------|
| Reusable + thin caller | New prevue-review.yml (workflow_call) + review.yml becomes thin pull_request caller; dogfoods consumer path | ✓ |
| Single dual-trigger file | One file: on [pull_request, workflow_call] | |
| Reusable only, no dogfood | Just prevue-review.yml; repo doesn't self-review | |

**User's choice:** Reusable + thin caller (Recommended)

### Secrets passing
| Option | Description | Selected |
|--------|-------------|----------|
| Named per-engine secrets, optional | Declared not-required in secrets: block; consumer passes only chosen engine's secret; no secrets: inherit | ✓ |
| Single generic engine-token secret | One secret mapped internally per engine | |

**User's choice:** Named per-engine secrets, optional (Recommended)

### Prevue code ref
| Option | Description | Selected |
|--------|-------------|----------|
| Pin to matching release in the file | Workflow at vX checks out prevue@vX; optional input override | ✓ |
| Derive from github.workflow_ref | Parse caller ref at runtime | |
| Consumer passes prevue-ref input | Caller supplies ref explicitly | |

**User's choice:** Pin to matching release in the file (Recommended)

### Consumer repo checkout
| Option | Description | Selected |
|--------|-------------|----------|
| Base ref only, diff API-fetched | Checkout base.sha (trusted) for prevue.yml + future skills; PR head never checked out | ✓ |
| No consumer checkout, all via API | Read prevue.yml via contents API at base.sha | |

**User's choice:** Base ref only, diff still API-fetched (Recommended)

---

## Config: inputs vs .github/prevue.yml (WKFL-03)

### Precedence
| Option | Description | Selected |
|--------|-------------|----------|
| input > prevue.yml > built-in | Standard layering | ✓ |
| prevue.yml > input | Repo policy authoritative | |
| No overlap, one source per knob | Each knob in exactly one source | |

**User's choice:** input > prevue.yml > built-in (Recommended)

### Knob split
| Option | Description | Selected |
|--------|-------------|----------|
| Minimal inputs: engine + config-path | All behavioral config in prevue.yml | ✓ |
| Rich inputs mirroring prevue.yml | Most knobs also inputs | |
| prevue.yml only, no behavioral inputs | Single source of truth | |

**User's choice:** Minimal inputs: engine + config-path (Recommended)

### Config path
| Option | Description | Selected |
|--------|-------------|----------|
| .github/prevue.yml from base ref | Canonical location, trusted base-ref checkout; config-path override | ✓ |
| Repo-root prevue.yml | Current cwd location | |

**User's choice:** .github/prevue.yml from base ref (Recommended)

### Schema organization
| Option | Description | Selected |
|--------|-------------|----------|
| Single unified file, named sections | rules + review: + engine: + skip: + classification.fallback:; wire load_ruleset(consumer_path) | ✓ |
| Separate files per concern | | |

**User's choice:** Single unified file, named sections (Recommended)

---

## LLM Classification Fallback (CLSF-02)

### Trigger granularity
| Option | Description | Selected |
|--------|-------------|----------|
| Per-file: unmatched files | LLM classifies files with no glob match; rule-match boolean is the signal; cheap model on paths only | ✓ |
| Only when zero rules matched whole-PR | LLM fires only if entire PR matched no rule | |
| Confidence-scored ambiguity | (dropped) | |

**User's choice:** Per-file: unmatched files (Recommended)
**Notes:** User questioned the "calibrated signal source" vs confidence scoring. Clarified: rule-match boolean IS the signal; confidence scoring needs labeled outcome data that doesn't exist yet, so it would be per-file with an uncalibrated threshold. Per-file is the honest version. Confidence option dropped. Only unmatched file paths enter the prompt → cost scales with ambiguity, clear-cut stays zero-token.

### Fallback engine + model
| Option | Description | Selected |
|--------|-------------|----------|
| Reuse selected adapter, cheap model | Same PREVUE_ENGINE, separate cheap classification model; no new deps | ✓ |
| Always a fixed cheap engine | Second auth path | |
| Direct API SDK | Rejected by CLAUDE.md | |

**User's choice:** Reuse selected adapter, cheap model (Recommended)

### Adapter API shape
| Option | Description | Selected |
|--------|-------------|----------|
| Add classify()/complete() to adapter ABC | Capability method; review() stays final; documented extension | ✓ |
| Sidecar helper, ABC frozen | Extract per-engine subprocess primitive without touching ABC | |
| Reuse review() with classification prompt | Parse labels from findings | |

**User's choice:** Add classify()/complete() to adapter ABC (Recommended)
**Notes:** User asked how Option 1 differs from Option 2 and whether either creates a new adapter. Clarified: neither creates a new adapter. Difference is where the per-engine "send prompt, get text" primitive lives — on the ABC as a method (Option 2, chosen) vs hidden in a sidecar (Option 1). Phase 5 hoisted the prompt but NOT the subprocess spawn, which classification needs. review() stays FINAL; adding a capability method is an extension, not a break.

### On fallback failure
| Option | Description | Selected |
|--------|-------------|----------|
| Degrade to general, review continues | Best-effort; no crash/red X | ✓ |
| Fail-closed (red run) | Like engine failure | |
| Skip review (neutral check) | | |

**User's choice:** Degrade to `general`, review continues (Recommended)
**Notes:** User added: must disclose the degradation explicitly to the consumer (sticky summary states "classification fallback unavailable — reviewed as general").

---

## Skip Conditions (NOIS-01)

### Where evaluated
| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid: drafts at if:, rest in Python | Draft via workflow if: (no runner); bot/label in Python (config-aware, neutral check) | ✓ |
| All in Python | Uniform but spins runner for drafts | |
| All at workflow if: | Cheapest but can't read prevue.yml; leaves required checks pending | |

**User's choice:** Hybrid: drafts at if:, rest in Python (Recommended)

### Bot detection
| Option | Description | Selected |
|--------|-------------|----------|
| GitHub author type == Bot + allowlist | Skip Bot-type authors; review_bots list re-includes specific bots | ✓ |
| Hardcoded login denylist | Fixed list | |
| Login suffix regex (endswith [bot]) | Convention-reliant | |

**User's choice:** GitHub author type == Bot + review-anyway list (Recommended)
**Notes:** User asked whether the "allowlist" controls auto-merge. Clarified: skip ≠ auto-merge. Prevue skipping = no AI review + non-blocking neutral check only; Prevue never merges. Bots not in the review-anyway list are skipped (neutral check won't block a consumer's own auto-merge); bots in the list are reviewed normally. Renamed "allowlist" → review_bots (review-anyway) to avoid ambiguity.

### Title/label default
| Option | Description | Selected |
|--------|-------------|----------|
| Default skip-label convention + configurable filters | `skip-review` label skips by default; skip_labels/skip_title_patterns override | ✓ |
| Empty defaults, opt-in only | Nothing skipped unless configured | |

**User's choice:** Default skip-label convention + configurable filters (Recommended)

### Skip surfacing
| Option | Description | Selected |
|--------|-------------|----------|
| Reuse skip-note + neutral check, with reason | upsert_skip_note + conclude_skip_check + reason string | ✓ |
| Neutral check only, no comment | | |
| Silent, nothing posted | Leaves required check pending | |

**User's choice:** Reuse skip-note + neutral check, with reason (Recommended)

---

## Claude's Discretion

- Exact `prevue.yml` field names within each section (`skip.bots`,
  `skip.review_bots`, `classification.fallback.model`, etc.).
- Exact reusable-workflow input names + the release-tag checkout mechanism.
- Whether the cheap classification model is a fixed per-engine default or a
  config knob (lean: config knob with sensible default).
- Module placement + signature for the LLM-fallback classification logic and the
  `classify()` method.

## Deferred Ideas

- Consumer custom skills/overrides (SKIL-03) — Phase 7.
- Prompt-injection red-team verification (SECR-02) — Phase 7.
- Token transparency reporting (OUTP-04) — Phase 7.
- Large-PR token budget / file packing (DIFF-03) — Phase 7.
- Functional Gemini adapter — stays a skeleton.
- GitHub App installation-token auth — PAT/named-secrets only in v1.
- Per-engine timeout/budget tuning — revisit with latency data.
