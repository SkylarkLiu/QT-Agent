# Frontend UI Agent Guide

## Objective
Build and modify frontend pages strictly following the design system below.
When generating UI, prefer maintainable component structure, reusable tokens, and no inline styling for color/spacing/typography.

## Design System Rules

### Color System
- Define CSS variables:
  - --color-primary
  - --color-secondary
  - --color-neutral-50
  - --color-neutral-100
  - --color-neutral-200
  - --color-neutral-300
  - --color-neutral-500
  - --color-neutral-700
  - --color-neutral-900
  - --color-success
  - --color-warning
  - --color-error
- Backgrounds allowed only:
  - #ffffff
  - #f8f9fa
  - #f3f4f6
- Do not use gradients on backgrounds or buttons.
- Never use blue-purple gradients, violet/indigo gradients, neon colors, or rainbow palettes.
- Use no more than 3 brand colors in one view.
- Text colors:
  - primary: #111827
  - secondary: #6b7280
  - tertiary: #9ca3af

### Typography
- Use only this font scale:
  - --text-xs: 12px
  - --text-sm: 14px
  - --text-base: 16px
  - --text-lg: 20px
  - --text-xl: 24px
  - --text-2xl: 32px
- Body text:
  - font-weight: 400
  - line-height: 1.5
- Headings:
  - font-weight: 600
  - line-height: 1.25
- Use px only.
- Do not use arbitrary font sizes.

### Spacing
- Use 4px base grid only:
  - 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64px
- Define spacing tokens from --space-1 through --space-16.
- No magic numbers.

### Components
#### Cards
- Use border OR shadow, never both.
- Allowed shadows only:
  - level-1: 0 1px 3px rgba(0,0,0,0.08)
  - level-2: 0 4px 12px rgba(0,0,0,0.1)
- Radius only 6px or 8px.

#### Buttons
- Primary: solid fill only, no gradient.
- Secondary: outline or ghost.
- Hover: darken by ~10%, no color switching.
- No rounded-full on rectangular buttons.

#### Inputs
- Border: 1px solid #d1d5db
- Radius: 6px
- Focus: border-color change + outline only, no glow.

### Icons
- Use one icon system consistently: Lucide, Heroicons, or Phosphor.
- Inline icons: 16px
- Standalone icons: 20px
- No emoji as functional icons.

### Forbidden Patterns
- No blue-purple gradients
- No glassmorphism unless explicitly requested
- No emoji icons
- No excessive shadows
- No inline styles for color, spacing, or typography
- No magic numbers
- No more than 2 shadow depth levels per page

## Implementation Rules
- Extract design tokens into a shared stylesheet or theme file first.
- Reuse existing UI components before creating new ones.
- Prefer small, composable React components.
- Any new screen must first create or use:
  1. design tokens
  2. button/card/input primitives
  3. page-level layout component if needed

## Verification Checklist
Before finishing:
1. Search for inline style usage related to color/spacing/typography and remove it.
2. Ensure all spacing/font-size/radius/shadow values match tokens.
3. Ensure no gradient classes or custom CSS gradients are introduced.
4. Ensure no more than one icon library is used.
5. Run lint and type-check.
6. Summarize which files were changed and how the design rules were enforced.