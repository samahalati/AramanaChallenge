# Visual design: "Earth & Olive"

**English** · [فارسی](fa/DESIGN.md)

A warm, calm look for a mental-health product: cream surfaces, an olive primary colour and a terracotta accent. Persian-first (right-to-left), with a full English mode. Everything is driven by CSS variables in `frontend/src/styles.css`, so a re-theme is a change of a dozen values.

## Name and mark
The product name is **آرامانا** (English: *Aramana*). The mark is a leaf (growth and care): `frontend/src/components/Logo.jsx` (inline SVG, colours from the theme) and `frontend/public/favicon.svg`.

## Palette
| Token | Light | Dark | Used for |
|---|---|---|---|
| `--bg` | `#FAF6EF` | `#1B1612` | page, header, inputs |
| `--card` | `#FFFFFF` | `#251F19` | cards, tables, dialogs |
| `--ink` | `#2A2018` | `#F1E9DD` | text |
| `--muted` | `#6A5B4E` | `#B5A793` | secondary text |
| `--line` | `#E7DDCF` | `#3A3027` | borders |
| `--brand` | `#3F6212` (olive) | `#A3C255` | primary buttons, active navigation, links |
| `--soft` | `#EAF0DB` | `#2C3320` | highlights, hover rows, info notices |
| `--accent` | `#C2410C` (terracotta) | `#FB923C` | focus ring |
| risk levels | low `#6A5B4E` on `#EFE8DC` · medium `#92400E` on `#FEF3C7` · high `#9A3412` on `#FFEDD5` · critical `#B91C1C` on `#FEE2E2` | tuned for dark | badges, scores |

Text/background pairs are chosen for WCAG AA contrast (≥ 4.5:1). Risk is never conveyed by colour alone: every badge also carries the level's name. Dark mode follows the operating-system setting.

## Typography
| Role | Persian | English / Latin |
|---|---|---|
| Headings | Noto Naskh Arabic (700) | Georgia, serif fallback |
| Body and controls | Noto Sans Arabic (400/600/700) | system UI font |
| Digits (Persian mode) | **Persian digits everywhere**: the digit range is served by Vazirmatn FD in front of both fonts (`unicode-range` in `styles.css`), so Latin digits in API data are drawn as ۰۱۲۳ |

Fonts are bundled from npm (`@fontsource/noto-*`, `vazirmatn`): no external requests, works offline, and the strict Content-Security-Policy stays `font-src 'self'`.

## Shape and spacing
Cards radius 18 px, controls 12 px, pills 999 px; 44 px minimum touch height for primary actions; right-to-left layout uses CSS logical properties (`inline-start/end`) so the same stylesheet serves both directions.

## Changing the look
Edit the variables at the top of `frontend/src/styles.css` (`:root` and the dark `@media` block), the leaf in `Logo.jsx` / `public/favicon.svg`, and the font imports. Button and screen wording is separate: `frontend/src/lib/fa.js` (see [I18N.md](I18N.md)).

The design proposals that led to this choice (three directions, button-wording options and logo variants) were reviewed and the "Earth & Olive" direction was selected.
