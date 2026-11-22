# BRAND_SWAP.md — rebrand ASCEND in two minutes

ASCEND reads its name, tagline, logo and palette from the database and from a
single design-token block. No template or script edits are needed for a rebrand.

## 1. Change the app name and tagline

Open **Admin → Brand & settings** (`/admin/settings`) as the Super Admin and edit:

| Field | Setting key | Where it appears |
| --- | --- | --- |
| Academy name | `school_name` | Sidebar school chip, topbar breadcrumb, login showcase, `<meta name="description">` |
| App name | `app_name` | `<title>`, sidebar brand, login hero wordmark, footer |
| Tagline | `tagline` | Under the sidebar brand, login hero copy |
| Creator credit | `creator_credit` | Sidebar footer, public footers |

The same values are injected into every page as `window.APP_BRAND`
(`templates/base.html`), so the login hero's letter animation, the sidebar
brand and the mobile topbar all follow automatically.

> `settings.app_name` must match `^[A-Za-z0-9 .&'’-]{1,40}$`; the wordmark
> animation splits the name into letters.

## 2. Swap the app logo (2D + hero)

Replace `static/app-logo.svg`, or upload a new SVG/PNG in **Brand & settings →
Academy logo**. That single file feeds:

- sidebar brand mark and the mobile topbar mark
- `<link rel="icon">` favicon
- login hero badge and the round crest in the top-left of the showcase
- PWA-style avatar fallbacks that use the app mark

School crests are separate: `settings.school_logo_path` renders beside the app
mark in the sidebar chip and login lockup. Use the **Academy logo** upload on
`/admin/settings` — PNG, JPG or WEBP only (SVG uploads are rejected by design),
validated and re-encoded, then written to `/uploads/school_logo.png`. The app
mark and the school crest are stored independently.

## 3. Change the palette

Edit the token block at the top of `static/ui.css`:

```css
:root{
  --green-950:#03261c;  --green-900:#064e3b;  --green-800:#075c49;
  --green-700:#0b7f61;  --green-600:#0f9a73;  --green-500:#16b389;
  --mint-50:#eef9f4;    --mint-100:#d9f2e8;   --mint-200:#bfe9d8;
  --lime-400:#a3d64b;
}
```

Because the legacy sheets (`style.css`, `v12`–`v14`, `design-system.css`,
`parent.css`, `fees.css`) resolve their accents through the bridged
`--orange*`, `--green` and `--teal` aliases, changing only these ten values
re-skins buttons, links, banners, badges, focus rings and the canvas hero
(`static/hero.js` samples `--green-600` at runtime).

Hero canvas geometry, density and tilt live in `static/hero.js`
(`count`, `speed`, `soft`) if the scene needs re-tuning for a new brand colour.

## 4. Fonts

`static/fonts/` is self-hosted and CSP-safe:

- `inter-latin-wght-normal.woff2` — body (already used by the legacy sheets)
- `sora-latin-{600,700,800}-normal.woff2` — display
- `jetbrains-mono-latin-{500,600}-normal.woff2` — eyebrows, metrics, table heads

Both Sora and JetBrains Mono are SIL OFL 1.1; the licence files sit next to the
fonts. To use another family, add the `.woff2` plus its `@font-face` in
`static/ui.css` and point `--font-display` / `--font-body` / `--font-mono` at it.

## 5. Cache busting

`templates/base.html` loads every stylesheet and script with
`?v=academy-15`. Bump that string when shipping asset changes so browsers and
the CDN pick them up:

```html
<link rel="stylesheet" href="/static/ui.css?v=academy-16">
<script src="/static/ui.js?v=academy-16" defer></script>
<script src="/static/hero.js?v=academy-16" defer></script>
```

## 6. What must not be touched

- The `/health` JSON keeps `"version": "1.4.0"` for uptime checks and deploys.
- `settings.app_name`, `tagline`, `creator_credit` and `school_logo_path` are
  the only supported rebrand inputs; the CSS custom properties are the only
  supported palette inputs.
- No external fonts, icons, CDNs or import maps: the app ships a strict
  `script-src 'self'` Content-Security-Policy and must work offline/air-gapped.
