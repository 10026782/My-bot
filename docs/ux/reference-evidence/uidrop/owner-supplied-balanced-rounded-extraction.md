# Owner-supplied balanced/rounded dark extraction

**Date received:** 13/08/2026

**Evidence status:** `OWNER-SUPPLIED EXTRACTION + SCREENSHOT — VISUALLY REVIEWED`

**Use:** visual-language calibration only; never product/runtime authority.

**Screenshot:** `owner-supplied-balanced-rounded-reference.png` (`1024×505`, PNG, SHA-256 `5e190e0fc4a395de606111c0f35ef8da63d405c7e42976113e1ebb29cef725c4`)

## Direction supplied

- Vibe: balanced, rounded, dark, and flat.
- Foundation: Radix UI, 4px grid, pill buttons, generous line-height, and no default shadows.
- Palette evidence: `#5E6AD2`, `#7E88DB`, `#08090A`, `#1C1D1E`, `#F7F8F8`, `#8A8F98`, `#E5E5E6`, and `#C2D2F2`.
- Typography evidence: Inter; 64px display H1, 40px H2, 13px eyebrow/H3, and 16px body.
- Geometry evidence: pill buttons, 4px cards, 6px inputs.
- Spacing evidence: 4/8/12/16/20/24/32/48/96/128px.
- Motion evidence: 100ms and 160ms; the supplied cubic-bezier value is truncated after `0.25, 0.46`.
- Responsive evidence: 560/600/640/768/1024/1120/1280/1536px and a 1265px maximum layout width.

## Screenshot review

### Directly observed

- Near-black full-page canvas with high-contrast white typography and muted gray support copy.
- Very quiet, compact top navigation; the primary action is a high-contrast light pill.
- A large display headline with short measure, strong line breaks, and generous empty space.
- Thin border-led separation and flat surfaces; no visible card-shadow vocabulary.
- Content aligned to a wide desktop frame with restrained side padding.
- A low-contrast framed content region begins below the hero, using minimal rounding.

### Evidence limits

- This is a marketing landing-page crop, not an application workspace or Ventures flow.
- The visible brand mark, product name, marketing copy, navigation labels, and exact page composition are source identity and must not be copied.
- Purple accent usage, inputs, cards, focus, hover, active, modal, and mobile states are not visible in the screenshot.
- A 64px headline and 96/128px spacing are display/marketing evidence, not app-density evidence.
- Screenshot review cannot establish keyboard behavior, contrast compliance across all states, or Radix implementation quality.

## BOSS disposition

- `ADOPT`: near-black canvas, quiet chrome, high-contrast text, flat borders, compact navigation density, and generous whitespace around the primary decision.
- `ADAPT`: light pill geometry for high-priority actions only; purple as an accent/selection system; wide desktop frame with an 800px focused-reading/work column.
- `REFERENCE ONLY`: 64/40px display scale and 96/128px spacing, reserved for future marketing/editorial surfaces rather than BOSS workspaces.
- `REJECT`: brand/logo/navigation copying, disappearing `opacity: 0` hover behavior, shadow-only focus, 4px viewport gutters, and raw z-index `10000`.

The canonical merged decision is recorded in `docs/ux/BOSS_DESIGN_SYSTEM_V1.md`.
