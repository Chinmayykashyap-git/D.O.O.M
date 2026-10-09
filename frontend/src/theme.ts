/**
 * D.O.O.M. Design System — Token File
 * All palette, typography, spacing, and motion values.
 * No ad-hoc color strings anywhere else in the codebase.
 *
 * PALETTE RATIONALE:
 * - Dark Iron / Panel: near-black iron, not pure black — gives depth for layering
 * - Doom Green: deep forest / naval, the sovereign base accent
 * - Emerald: bright positive/clear state
 * - Brass: deliberate accent on rules, seals, active states, key numerals
 * - Crimson: CRITICAL ONLY — tamper, broken chain, alert
 * - Amber: elevated severity
 * - Ivory: primary text
 * - Oxidized Steel: secondary / muted text
 *
 * FONT RATIONALE:
 * - Cinzel: engraved Roman capitals for display numerals and titles.
 *   Chosen over Cormorant (too delicate) and Playfair (too editorial).
 *   Cinzel reads like carved stone — authoritative, forensic, unyielding.
 * - Inter: clean grotesk for body. Tabular variant available.
 * - JetBrains Mono: monospace for IDs, hashes, codes, labels.
 */

export const COLORS = {
  // Backgrounds
  darkIron:     '#0B0E0D',
  panel:        '#121816',
  raised:       '#18211E',
  doomGreen:    '#0F3D2E',

  // Accents
  emeraldDim:   '#1F7A5A',
  emerald:      '#3FB68A',
  brassDim:     '#7A6530',
  brass:        '#B8963E',
  brassLight:   '#D9C98F',
  oxSteel:      '#7C8A87',
  ivory:        '#EDE6D3',
  ivoryDim:     '#C8C2B2',
  ivoryMuted:   '#8A8478',

  // Severity
  crimson:      '#B3262B',
  crimsonDim:   '#7B1A1E',
  amber:        '#C98A2B',
  amberDim:     '#6B4A15',

  // Borders & rules
  borderSubtle: '#1E2924',
  borderNormal: '#283330',
  borderBrass:  '#4A3C1F',
  borderEmerald:'#1A4035',

  // Interactive
  focusRing:    '#B8963E',
} as const;

export const FONTS = {
  display:  '"Cinzel", "Palatino Linotype", serif',
  body:     '"Inter", "Helvetica Neue", Arial, sans-serif',
  mono:     '"JetBrains Mono", "Fira Code", "Courier New", monospace',
} as const;

export const TYPE_SCALE = {
  // px sizes
  label:    12,
  body:     13,
  bodyLg:   14,
  subhead:  15,
  heading:  18,
  titleSm:  22,
  title:    28,
  display:  36,
  hero:     48,
} as const;

export const SPACING = {
  px1:  '1px',
  xs:   '4px',
  sm:   '8px',
  md:   '12px',
  lg:   '16px',
  xl:   '24px',
  xxl:  '32px',
  xxxl: '48px',
} as const;

export const RADII = {
  none: '0',
  sm:   '2px',
  md:   '4px',
} as const;

export const MOTION = {
  fast:   '150ms',
  normal: '200ms',
  slow:   '300ms',
  ease:   'cubic-bezier(0.16, 1, 0.3, 1)',
} as const;

/** CSS variable names for use in CSS files */
export const CSS_VARS = {
  darkIron:     'var(--c-dark-iron)',
  panel:        'var(--c-panel)',
  raised:       'var(--c-raised)',
  doomGreen:    'var(--c-doom-green)',
  emeraldDim:   'var(--c-emerald-dim)',
  emerald:      'var(--c-emerald)',
  brassDim:     'var(--c-brass-dim)',
  brass:        'var(--c-brass)',
  brassLight:   'var(--c-brass-light)',
  oxSteel:      'var(--c-ox-steel)',
  ivory:        'var(--c-ivory)',
  ivoryDim:     'var(--c-ivory-dim)',
  ivoryMuted:   'var(--c-ivory-muted)',
  crimson:      'var(--c-crimson)',
  crimsonDim:   'var(--c-crimson-dim)',
  amber:        'var(--c-amber)',
  amberDim:     'var(--c-amber-dim)',
  borderSubtle: 'var(--c-border-subtle)',
  borderNormal: 'var(--c-border-normal)',
  borderBrass:  'var(--c-border-brass)',
  borderEmerald:'var(--c-border-emerald)',
  focusRing:    'var(--c-focus-ring)',
  fontDisplay:  'var(--font-display)',
  fontBody:     'var(--font-body)',
  fontMono:     'var(--font-mono)',
} as const;

/** Severity thresholds matching API */
export function severityLevel(score: number): 'critical' | 'high' | 'medium' | 'standard' {
  if (score >= 90) return 'critical';
  if (score >= 75) return 'high';
  if (score >= 55) return 'medium';
  return 'standard';
}

export function severityColor(level: 'critical' | 'high' | 'medium' | 'standard'): string {
  switch (level) {
    case 'critical': return COLORS.crimson;
    case 'high':     return COLORS.amber;
    case 'medium':   return COLORS.brassLight;
    default:         return COLORS.emerald;
  }
}

