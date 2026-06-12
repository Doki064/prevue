---
name: Component State & Rendering
description: Review component state management and render correctness.
applies-to:
  - "**/*.tsx"
  - "**/*.jsx"
  - "**/*.vue"
---
Review React/Vue component state management and render correctness for anti-patterns that cause bugs or performance regressions:

- Derived state duplicated into `useState` when it can be computed during render — causes sync bugs.
- `useEffect` deps missing or containing inline objects/arrays (`useEffect(..., [{}])`) — causes stale closures or infinite re-renders.
- List keys set to array index (`key={i}`) when items can reorder or be removed — causes mis-mapped state.
- Pointless `useMemo` / `useCallback` wrapping stable primitives — adds overhead with no benefit.
- `dangerouslySetInnerHTML` without sanitization — XSS risk on any user-controlled input.
- State updates inside render body (outside handlers/effects) — guaranteed infinite re-render loop.

For each finding: cite file + line. Infinite re-render loops and missing effect deps on subscriptions → **error**. Unnecessary memoization and derived-state duplication → **warning**.
