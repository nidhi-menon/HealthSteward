# Brand Asset Kit

External/marketing-use brand assets — not referenced by the live site (see `docs/assets/favicon.svg` and `docs/assets/social-preview.png` for those). Use these for LinkedIn, decks, README embeds elsewhere, or any other external surface.

All colors match the canonical brand palette in `docs/SITE_STYLE_GUIDE.md` (teal `#20464c`/`#2f626a`, ink `#171f1d`).

## Icon only (`mark.*`)

- `mark.svg` — vector source, scales to any size
- `mark-16.png` through `mark-1024.png` — pre-rendered PNGs at common sizes (favicons, app icons, social avatars)
- `favicon.ico` — multi-resolution (16/32/48) browser favicon

## Icon + wordmark lockup (`lockup.*`)

- `lockup.svg` — vector source
- `lockup-transparent-2040.png` / `lockup-transparent-3060.png` — transparent background, for overlaying on slides, dark backgrounds, or colored surfaces
- `lockup-on-paper-2040.png` — on the brand's paper background, for contexts needing a solid backdrop (e.g. email signature)

If the brand palette changes (see `docs/SITE_STYLE_GUIDE.md` for the source of truth), regenerate these rather than hand-editing — the SVG sources are simple enough to recolor and re-export via `rsvg-convert`.
