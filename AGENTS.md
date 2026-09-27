# AGENTS.md — working knowledge for agents editing this repo

This blog is a small Astro static site. This file tells you how it is configured, how it deploys, and how the design system is put together so you can make changes without guessing.

## Quick reference

- **What it runs on:** Astro 7 static site generation, Node >= 22.12.
- **Tests:** `npm test` — contract tests in `tests/blog.test.mjs`, run in CI before the build. `node tests/mutate-blog.mjs` proves those tests can actually fail; run it after touching any test.
- **Verify visually in the engine Omar uses:** real WebKit at an iPhone width (390), both themes, and check `scrollWidth` vs `clientWidth` plus the `window.scrollTo(9999,0)` → `scrollX` question. A green build does not catch contrast, truncation or overflow.
- **Where it's deployed:** GitHub Pages at the custom domain `https://log.oem.ngo/` (served at the root, fronted by Cloudflare). The old `omiinaya.github.io/oem-log/` path auto-301s here.
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
  BaseHead.astro         <head>: the 3 cli-mono layers + site.css, title, description, favicon, sitemap
  Header.astro           brand "$ oem/log", nav, theme toggle markup + FOUC guard
                         (the toggle BEHAVIOUR is cli-mono.js, not this file)
  HeaderLink.astro       nav link that computes active state from base-stripped pathname
  Footer.astro           terminal footer, copyright year, status line
  FormattedDate.astro    pubDate renderer
src/pages/
  index.astro            home: hero + latest notes
  blog/index.astro       notes index
  blog/[...slug].astro   post detail (getStaticPaths from blog collection)
  about.astro            about page
  rss.xml.js             RSS feed
src/styles/site.css      THIS SITE's layer only, loaded last (the design system is oem-ui)
src/styles/cli-mono/     vendored copy of oem-ui: tokens + base + components. Never hand-edit.
src/js/cli-mono.js        vendored runtime: theme toggle, scroll-spy, copy, year
public/                  favicon.ico + favicon.svg (served at site root)
.github/workflows/deploy.yml
sketches/                throwaway design mockups; gitignored
```

## Configuration

### Site URL + base path (`astro.config.mjs`)

The site is served from the custom domain **`log.oem.ngo`**, not a Pages project path. A custom
domain is served at the **root**, so `base` must be `/`:

```js
site: 'https://log.oem.ngo/',
base: '/',
```

**Rule: no hardcoded root-absolute links.** Any internal `href`/`src` that points into the site must be base-aware via `import.meta.env.BASE_URL`. Existing examples: `Header.astro` (brand + nav), `HeaderLink.astro` (strips base from pathname for active state), `BaseHead.astro` (favicon, sitemap). Searching the built `dist/` for `(href|src)="/` that is not base-prefixed is a good post-build check.

**If `base` is ever wrong, the site looks unstyled rather than broken.** Assets are emitted at
`/_astro/*` when `base` is `/` and at `/oem-log/_astro/*` when it is the project path. A mismatch
between the configured `base` and the host actually serving the build produces a 404 on the
stylesheet, and the page renders as unstyled default Times New Roman while the HTML is all correct.
When someone reports "the CSS broke", check `document.querySelector('link[rel=stylesheet]').href`
against the host first, and read the body background/font, before suspecting the design system.

**Custom domain registration lives in the GitHub API, not `public/CNAME`.** With
`build_type: workflow`, `public/CNAME` is uploaded into the artifact and ignored:

```bash
gh api repos/omiinaya/oem-log/pages --jq '{cname,html_url,https_enforced}'
gh api -X PUT repos/omiinaya/oem-log/pages -F cname=log.oem.ngo
```

`cname: null` means GitHub serves "Site not found" while still returning a valid
`x-github-request-id`. `public/oem-log/index.html` is a hand-written redirect shim left from the
move: it is **dead weight**, because GitHub auto-301s the old `<user>.github.io/<project>/` path once
`cname` is registered, before any file is served. Harmless, but do not credit it with fixing
anything, and do not assume it is the thing redirecting.

**TLS is terminated at Cloudflare, not at the GitHub origin.** `https_enforced` stays `false` and
should: GitHub never provisions an origin cert for a hostname proxied through Cloudflare, so
flipping it fails permanently with "The certificate does not exist yet". TLS posture is enforced on
the Cloudflare zone instead (`always_use_https = on`, `min_tls_version = 1.2`). Turning on
`always_use_https` is what closes the plaintext hop in GitHub's own auto-301, which targets
`http://` whenever `https_enforced` is false.

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

- The live site URL is `https://log.oem.ngo/` (custom domain, served at the root). Never point the browser the wrong way.
- `dist/` and `.astro/` are gitignored and never committed; they are build artifacts produced fresh in CI.
- `sketches/` is gitignored — throwaway HTML mockups, not part of the shipped site.
- Astro/lightningcss compiles `@media (max-width: Npx)` into modern range syntax `@media (width<=Npx)`. Valid in modern browsers, but note it when grepping built CSS for media queries.

## Design system (oem-ui / cli-mono)

The theme derives from a terminal: pure black/grey/white, monospace-first, dark by default.

**The design system is NOT this repo's.** It is `oem-ui`, vendored into
`src/styles/cli-mono/` and loaded by `BaseHead.astro` in this order:

1. `cli-mono/tokens.css` — every value, both themes. THE contract.
2. `cli-mono/base.css` — element defaults, prose rhythm, touch ergonomics.
3. `cli-mono/components.css` — all `.cm-*` components.
4. `../styles/site.css` — this site's own layer, loaded LAST so it wins.

`src/styles/site.css` is where site-specific rules go. If a rule could be
expressed with an existing `.cm-*` class or a token, it belongs in oem-ui,
not here. To pull a library update in, re-run
`/root/projects/oem-ui/scripts/install.sh /root/projects/dev-blog` and commit
the result; do not hand-edit anything under `src/styles/cli-mono/`.

**The three files here are a vendored COPY.** A copy is not adoption:
`oem-ui`'s `scripts/check-design-sync.sh` compares them byte-for-byte against
the library AND verifies the project actually imports them. It once reported
"in sync" for a week while this site imported none of them and rendered its own
264-line `global.css` — which is how the secondary text sat at 2.66:1 contrast.
That `global.css` is gone. Do not recreate it.

### Tokens (`src/styles/cli-mono/tokens.css`)

Tokens are owned by the library and declared on `:root` (dark) and
`[data-theme='light']` (light). The ones this site leans on:

- `--bg`, `--bg-2`, `--bg-3` — surfaces
- `--ink`, `--ink-dim`, `--ink-faint` — text hierarchy
- `--line` — borders
- `--panel` — raised card background
- `--radius-sm` — corner radius
- `--maxw: 860px` — the ONE content width for every page
- `--gutter: 1.25rem` — single source of side padding for `main`, `header` and `footer`
- `--head-top: 3rem` — top offset of each page's head block (`.hero`, `.list-head`, `.about-head`, `.post-head`)
- `--head-h1: 2rem` — font size of each page's `h1`
- `--min-font: 12px` — the phone type floor; `--tap: 44px` the target floor

`--ink-faint` is `#8b8b8b` dark / `#6d6d6d` light, which is 5.81:1 and 4.96:1
against `--bg`. Both clear WCAG AA. The values this site used to declare
itself (`#555555` / `#8a8a8a`) measured 2.66:1 and 3.31:1 and both FAILED —
one grey cannot clear 4.5:1 against near-white and near-black, so each theme
needs its own. If you ever need to change a token, change it in oem-ui, where
its contrast test will check it.

The scrollbar is themed by the library via `scrollbar-width: thin` +
`scrollbar-color`, plus a `::-webkit-scrollbar` variant. `html { overflow-y:
scroll }` permanently reserves the scrollbar gutter so short pages and
scrolling pages get the same content width and nothing shifts sideways.

### Theme toggle — the library owns it

- **Dark is the default.** Light is an opt-in toggle, not OS-following.
- `cli-mono.js` (the library runtime) finds `.theme-toggle`, syncs the icon
  and `aria-pressed`, and persists. Do not re-implement it in the component;
  two handlers writing one attribute is a real bug, and a test guards it.
- The storage key stays **`oem-log-theme`**, declared per-page on `<html>` as
  `data-cm-theme-key="oem-log-theme"` with `data-cm-theme-legacy="cm-theme"`.
  Every entry point must declare it.
- The **FOUC guard is still a hand-written inline `is:inline` script** in
  `Header.astro`, and it must stay inline and ahead of every stylesheet. It
  reads `oem-log-theme` first, then the legacy `cm-theme`. Both keys must stay
  in that list or a returning light-theme reader gets a black flash and then
  finds their preference gone.
- Load the runtime with `<script>import '../js/cli-mono.js';</script>`, not a
  raw `src`. `src/pages/blog/index.astro` is one directory deeper, so its path
  is `../../js/cli-mono.js`.

### Layout stability (do not regress)

- **One content width, site-wide.** `--maxw` applies to `main`, `nav` and `.footer-inner` alike. Do not add a per-page `max-width` or a `width: 100%` on a `main` subclass: a class selector beats the global `main` rule and silently widens that page only.
- **One vertical start position, site-wide.** Every page's head block (`.hero`, `.list-head`, `.about-head`, `.post-head`) takes `padding: var(--head-top) 0 ...` and its `h1` uses `var(--head-h1)`. `main` has **no top padding**; `--head-top` is the only vertical offset. Giving `main` a top padding as well double-counts it and knocks the post page out of line.
- **`--gutter` is the only side padding.** `main`, `header` and `footer` all pad with `var(--gutter)`, including inside the ≤680px media block. A hardcoded `1.25rem` in one place and a token in another will drift.
- **The scrollbar gutter stays reserved** (`html { overflow-y: scroll }`). Removing it reintroduces a 12px content-width difference between short and scrolling pages.
- The ≤680px block overrides `--head-top: 2rem` and `--head-h1: 1.95rem` from `:root`. Do not re-add page-local h1 font sizes; they are what made every route's heading a different size.

### The Astro scoped-CSS trap (this bit twice already)

A scoped `<style>` block beats any imported sheet. Two consequences, both
pinned by tests in `tests/blog.test.mjs`:

- **The mobile type floor must be declared in the scoped block**, as
  `max(var(--min-font), 0.66rem)` — not in `site.css`, which cannot win the
  cascade. A bare `0.66rem` is a phone-sized regression (10.56px measured).
- **Every class in a scoped selector must appear in some file's markup.** A
  selector that matches nothing still builds, still ships, still renders; the
  spacing it controlled is simply gone. This is how `.hero .kicker` survived a
  rename to `class="cm-kicker"` on oem-links and welded the eyebrow to the
  title at 0px. Cross-file classes are legitimate (`HeaderLink.astro` adds
  `.nav-active` for `Header.astro` to style), so the check is fleet-wide.
- **Target the element that carries the text.** `FormattedDate.astro` renders
  a bare `<time>`, so a `font-size` on its parent `<p class="post-date">` is
  only an inherited default — the child measured 11.52px. Use
  `.post-date :global(time)`.

### Mobile / responsive

- The ≤680px responsive block is in the library's `base.css`: `main` bottom padding, `--head-top` to `2rem`, `--head-h1` to `1.95rem`, body 15px, `pre` padding/font tuned.
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