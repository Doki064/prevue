---
name: Accessibility
description: Review UI changes for basic accessibility (a11y) compliance.
applies-to:
  - "**/*.tsx"
  - "**/*.jsx"
  - "**/*.vue"
---
- Interactive elements are real controls (`<button>`/`<a>`) or have correct ARIA role + keyboard handlers.
- Images/icons have meaningful `alt` (or are marked decorative).
- Form inputs have associated `<label>`s; error states are announced, not color-only.
- Focus order is logical; no positive `tabindex`; modals trap + restore focus.
