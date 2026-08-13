# Owner-supplied visual token extraction

**Date received:** 13/08/2026

**Evidence status:** `OWNER-SUPPLIED EXTRACTION + SCREENSHOT — PARTIAL VISUAL SUPPORT`

**Use:** visual-language calibration only; never product/runtime authority.

**Screenshot:** `owner-supplied-workbench-reference.jpg` (`720×450`, JPEG, SHA-256 `201358d56d1a404e46b149677c0e78e15ee57cdb45664445ffd3240b5634480f`)

## Direction supplied

- Vibe: vibrant, modern, compact, subtly rounded, and flat by default.
- Foundation: 4px rhythm, Inter variable body text at 14px/1.6, and Radix UI as the source implementation substrate.
- Key colors: `#5EB1EF` primary, `#7EC1F2` accent, `#222222` background, `#FBFCFC` elevated surface, `#FFFFFF` text, and `#838383` muted.
- Radius evidence: 6px button/control, 8px card, and 4px chip.
- Core spacing: 4/8/12/16/20/24px; extended source values include 0/2/32/40/48px.
- Motion: 150ms and 75ms, `ease-out`.
- Focus evidence: 2px `#BFDBFE` ring.
- Content evidence: maximum 800px frame and 8px internal gutter.
- Source shadow recipes range from inset/extra-small to extra-large.
- Source responsive CSS contains near-duplicate thresholds around 576px, 650px, 768px, and 780px, plus component-specific queries above 1258px.
- Source layer values range from 150 to `2147483647`.

## BOSS evidence boundary

The user explicitly requested inspiration without copying brand assets, logos, identity, or source-library naming. Therefore:

- named source variables such as Ant Design/Retool properties are not BOSS tokens;
- colors and geometry are mapped to semantic BOSS roles rather than copied as a source palette API;
- duplicate breakpoints and extreme z-index values are treated as extraction artifacts;
- supplied color pairings remain subject to WCAG contrast checks;
- the screenshot supports only the visible desktop workbench state described below; it cannot prove mobile behavior, focus/hover states, color tokens hidden outside the crop, or full-product consistency.

## Screenshot review

### Directly observed

- A desktop workbench split into a narrow control/conversation pane and a wider preview pane, separated by a thin vertical divider.
- Compact top bars and tabs, with small labels and controls rather than oversized navigation.
- Flat surfaces and border-led separation. No visible card shadow system drives the hierarchy.
- Subtle rounding on the preview canvas and lower input surface.
- A large calm work area with a small centered loading state; secondary chrome stays visually quiet.
- Generous empty space inside the preview pane despite dense controls around it.

### Not supported by this screenshot

- The screenshot is predominantly light and does not visually confirm the extracted `#222222` dark background direction.
- The primary button is clipped at the upper-right edge, so its text color, size, and full geometry cannot be measured.
- The capture is compressed/washed out; exact neutral colors, border contrast, font weights, and shadow opacity cannot be sampled reliably.
- No mobile state, modal, tooltip, menu, focused control, hover state, error state, or populated data collection is visible.
- The image appears to show a builder/workbench context, not a Ventures lifecycle workspace. Its split-pane hierarchy may inspire desktop composition, but its labels, brand, and tool-specific structure must not be copied.

### BOSS disposition

- `ADOPT`: quiet chrome, compact hierarchy, flat border-led separation, and large focused work area.
- `ADAPT`: the desktop split-pane idea into collection/detail continuity for Ventures; do not copy the builder layout literally.
- `REFERENCE ONLY`: light neutral treatment, because it conflicts with the supplied dark palette and the screenshot is too washed out for color calibration.
- `REJECT`: source labels, brand/tool identity, tiny text/touch targets, and any assumption that this desktop crop defines mobile behavior.

The canonical disposition of this evidence is recorded in `docs/ux/BOSS_DESIGN_SYSTEM_V1.md`.
