# Owner-supplied visual token extraction

**Date received:** 13/08/2026

**Evidence status:** `OWNER-SUPPLIED EXTRACTION — SCREENSHOT NOT ATTACHED`

**Use:** visual-language calibration only; never product/runtime authority.

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
- the absent screenshot prevents any claim that hierarchy, density, or overall visual feel has been visually matched.

The canonical disposition of this evidence is recorded in `docs/ux/BOSS_DESIGN_SYSTEM_V1.md`.
