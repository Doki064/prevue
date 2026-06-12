---
name: Component State & Rendering
description: Review component state management and render correctness.
applies-to:
  - "**/*.tsx"
  - "**/*.jsx"
  - "**/*.vue"
---
- No derived state duplicated into local state when it can be computed during render.
- Effects have correct dependency arrays; no missing deps causing stale closures, no objects/arrays recreated each render as deps.
- Keys on list items are stable + unique (not array index when items reorder).
- Avoid expensive work in render; memoize only where measured.
