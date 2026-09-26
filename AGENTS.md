# AGENTS.md — working knowledge for agents editing this repo

This blog is a small Astro static site. This file tells you how it is configured, how it deploys, and how the design system is put together so you can make changes without guessing.

## Quick reference

- **What it runs on:** Astro 7 static site generation, Node >= 22.12.
- **Where it's deployed:** GitHub Pages at `https://omiinaya.github.io/oem-log/` (project site under `/oem-log/`).
- **How it deploys:** `.github/workflows/deploy.yml` builds `./dist/` and publishes on every push to `main`.
- **Author identity for commits:** always commit as `omiinaya <omar@mrxlab.net>`. This is set repo-locally; the box's global git identity is a real name that must never appear in this repo's history.

## Workspace layout

```
astro.config.mjs         site URL + base path + font registration
package.json             scripts, engine (>=22.12), deps: astro, @astrojs/mdx, sitemap, rss, sharp
tsconfig.json            TS config (bundled template)
src/consts.ts            single source for site data used across components
src/content.config.ts    Zod schema validating post frontmatter (build fails on invalid)
src/content/blog/        posts. one .md per post, filename = slug
src/layouts/
  BlogPost.astro         article page: filename header, byline, prose body, responsive type rules
src/components/
  BaseHead.astro         <head>: global.css import, title, description, favicon, sitemap
  Header.astro           brand "$ oem/log", nav, theme toggle + flash-prevention script
  HeaderLink.astro       nav link that computes active state from base-stripped pathname
  Footer.astro           terminal footer, copyright year, status line
  FormattedDate.astro    pubDate renderer
src/pages/
  index.astro            home: hero + latest notes
  blog/index.astro       notes index
  blog/[...slug].astro   post detail (getStaticPaths from blog collection)
  about.astro            about page
  rss.xml.js             RSS feed
src/styles/global.css    design tokens + base styles (the design system, see below)
public/                  favicon.ico + favicon.svg (served at site root)
.github/workflows/deploy.yml
sketches/                throwaway design mockups; gitignored
```

## Configuration

### Site URL + base path (`astro.config.mjs`)

The site is a Pages **project** site, so it lives under `/oem-log/`, not the domain root. Two values must stay consistent:

```js
site: 'https://omiinaya.github.io/oem-log/',
base: '/oem-log/',
```

**Rule: no hardcoded root-absolute links.** Any internal `href`/`src` that points into the site must be base-aware via `import.meta.env.BASE_URL`. Hardcoding `href="/about/"` breaks under the `/oem-log/` prefix. Existing examples: `Header.astro` (brand + nav), `HeaderLink.astro` (strips base from pathname for active state), `BaseHead.astro` (favicon, sitemap). Searching the built `dist/` for `(href|src)="/` that is not base-prefixed is a good post-build check.

### Global data (`src/consts.ts`)

`SITE_TITLE`, `SITE_DESCRIPTION`, `AUTHOR_HANDLE`, `AUTHOR_NAME`, `AUTHOR_EMAIL`, `AUTHOR_GITHUB`. Components import these rather than duplicating. Contact/name changes live here only.

### Fonts (`astro.config.mjs`)

Atkinson Regular/Bold are bundled locally (`src/assets/fonts/*.woff`) and registered via `fontProviders.local()` with `cssVariable: '--font-atkinson'`. No external font CDN at runtime — keeps the site dependency-free and loadable offline.

### Content schema (`src/content.config.ts`)

Post frontmatter is validated through a Zod schema in `astro:content`. Invalid or missing required fields break the build — this is the gate. Fields: `title` (str), `description` (str), `pubDate` (date, coerced), optional `updatedDate`, `heroImage` (image), `tags` (string[]).

## Deploy mechanics

1. Push to `main` (or manually trigger `workflow_dispatch`).
2. `deploy.yml` `build` job: checkout → `actions/setup-node` node 22 (npm cache from package-lock) → `npm ci` → `npm run build` → `actions/upload-pages-artifact` with `path: dist`.
3. `deploy` job: `actions/deploy-pages`, environment `github-pages`.

**GitHub Pages must be enabled on the repo** (Settings → Pages → Build and deployment → Source: GitHub Actions). A deploy failing with a 404 usually means Pages is off or still provisioning, not a build error.

### Deploy gotchas

- The live site URL is `https://omiinaya.github.io/oem-log/` (trailing slash, sub-path). Never point the browser the wrong way.
- `dist/` and `.astro/` are gitignored and never committed; they are build artifacts produced fresh in CI.
- `sketches/` is gitignored — throwaway HTML mockups, not part of the shipped site.
- Astro/lightningcss compiles `@media (max-width: Npx)` into modern range syntax `@media (width<=Npx)`. Valid in modern browsers, but note it when grepping built CSS for media queries.

## Design system (CLI-mono)

The theme derives from a terminal: pure black/grey/white, monospace-first, dark by default.

### Tokens (`src/styles/global.css`)

Design tokens live as CSS custom properties on `:root` (dark values) and `[data-theme='light']` (light overrides). Recurring ones:

- `--bg`, `--bg-2`, `--bg-3` — surfaces
- `--ink`, `--ink-dim`, `--ink-faint` — text hierarchy
- `--line` — borders
- `--panel` — raised card background
- `--radius-sm` — corner radius
- `--maxw: 860px` — the ONE content width for every page
- `--gutter: 1.25rem` — single source of side padding for `main`, `header` and `footer`
- `--head-top: 3rem` — top offset of each page's head block (`.hero`, `.list-head`, `.about-head`, `.post-head`)
- `--head-h1: 2rem` — font size of each page's `h1`

The scrollbar is themed via `scrollbar-width: thin` + `scrollbar-color`, plus a `::-webkit-scrollbar` variant. `html { overflow-y: scroll }` permanently reserves the scrollbar gutter so short pages and scrolling pages get the same content width and nothing shifts sideways on navigation.

### Theme toggle (`src/components/Header.astro`)

- **Dark is the default.** Light is an opt-in toggle, not OS-following.
- Toggle stores a choice in `localStorage` under key `oem-log-theme` and sets/clears `data-theme` on `<html>`.
- A small **inline `is:inline` script** in the header runs before paint to read the stored value and set the theme attribute, preventing a flash of the wrong theme on load.
- If you change localStorage key or add a theme, update that inline script and keep it executing early.

### Layout stability (do not regress)

- **One content width, site-wide.** `--maxw` applies to `main`, `nav` and `.footer-inner` alike. Do not add a per-page `max-width` or a `width: 100%` on a `main` subclass: a class selector beats the global `main` rule and silently widens that page only.
- **One vertical start position, site-wide.** Every page's head block (`.hero`, `.list-head`, `.about-head`, `.post-head`) takes `padding: var(--head-top) 0 ...` and its `h1` uses `var(--head-h1)`. `main` has **no top padding**; `--head-top` is the only vertical offset. Giving `main` a top padding as well double-counts it and knocks the post page out of line.
- **`--gutter` is the only side padding.** `main`, `header` and `footer` all pad with `var(--gutter)`, including inside the ≤680px media block. A hardcoded `1.25rem` in one place and a token in another will drift.
- **The scrollbar gutter stays reserved** (`html { overflow-y: scroll }`). Removing it reintroduces a 12px content-width difference between short and scrolling pages.
- The ≤680px block overrides `--head-top: 2rem` and `--head-h1: 1.7rem` from `:root`. Do not re-add page-local h1 font sizes; they are what made every route's heading a different size.

### Mobile / responsive

- Global responsive block in `global.css`: below 680px, `main` uses `padding: 0 var(--gutter) 4rem`, `--head-top` drops to `2rem` and `--head-h1` to `1.7rem`, body 15px, `pre` padding/font tuned.
- `main` is capped by `max-width: calc(100% - (2 * var(--gutter)))`, so the reading column is fluid down to phone widths with no hard `--maxw` cap on small screens. There is no `.about-main` / `.post-main` width rule and there should not be one.
- Header below 640px wraps: brand + theme toggle on row one, nav links on their own full-width row.
- `BlogPost.astro` has its own ≤680px block scaling article headings and tightening prose line-height for comfortable narrow-screen reading.

### Visual conventions baked into components

- Header brand: `$ oem/log` with a blinking terminal cursor, `v0.1.0` tag.
- Post page title is framed like a filename; headings render with `## ` -style prefixes (see BlogPost `.prose :global(h2::before)`).
- Footer is a terminal status line: copyright (year computed via `new Date()`), "all systems nominal".

## Workflow for changes

1. Dev: `npm run dev` → `localhost:4321`. (You can also run a preview of a build with `npm run build && npm run preview`.)
2. Always `npm run build` after editing so schema/type errors surface and you can verify the output.
3. Commit as `omiinaya` with a concise message; push to `main` to deploy. Do not push untested/unbuilt changes to `main`.

## What NOT to do

- Don't hardcode root-absolute internal links (`href="/..."`) — use `import.meta.env.BASE_URL`.
- Don't commit `dist/`, `.astro/`, `node_modules/`, or `sketches/`.
- Don't commit under the box's global git identity (real name) — use the repo-local `omiinaya` identity.
- Don't leak sensitive/internal identifiers into posts or `src/consts.ts`: the site is public. Real names, IPs, internal infra topology, and anything mapping to the human author beyond the `omiinaya` handle stay out.
- Don't publish a post without the maintainer's explicit approval.