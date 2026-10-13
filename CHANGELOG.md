# Changelog

All notable changes to oem/log. Format loosely follows [Keep a Changelog](https://keepachangelog.com/), and each entry is anchored to the commit that landed it (author `omiinaya`).

## [Unreleased]

### Changed

- **The article head is the library's `<PostHead>` now, not a second copy
  in the layout.** `BlogPost.astro` hand-rolled its kicker, title and
  byline in four scoped rules — `.post-head`, `.byline`, `.sep` and
  `.updated` — while the library's vendored `PostHead.astro` sat in
  `src/astro/` **unimported**. That is the same failure this repo's
  `Header.astro` comment already records: a fork that only *looks* like
  the library, so every fix the library makes stops at the repo boundary.

  The fork's byline put an ELEMENT separator (`<span class="sep">·</span>`)
  inside a `flex-wrap: wrap` row — precisely the shape oem-ui deleted when
  it made the footer separator generated, and then again for the byline
  (oem-ui `83280fd`). MEASURED in WebKit at 390 and 1280 before the swap:
  `sepElements: 1`, `genMarks: 0`, one line. It did not strand **only
  because no post carries `updatedDate`**, so the row never wrapped. A
  latent bug, not an absent one — the first post with an `updatedDate`
  would have stranded a dot at every phone width. The same swap removes the
  layout's re-declarations of `.cm-prose`'s body colour/size, the `## `
  h2 mark, the link colour pair and the mobile prose bumps, all of which
  `components.css` already owns (the mobile bumps are declared GLOBALLY in
  the library, not only inside `.cm-prose`, so a local copy was pure
  duplication).

  Measured after (WebKit, 390 and 1280): `sepElements: 0`, `genMarks: 1`,
  the generated `::before` dot paints, `.cm-post-head` carries the
  library's border and rhythm, `## ` still renders, and
  `documentElement.scrollWidth == innerWidth` at both widths.

- **The vendored library was brought back in sync while adopting it.** The
  2026-10-09 migration left all five vendored files drifted (tokens 134
  lines, base 235, components 2573, runtime 1560, plus `src/astro/Header.astro`
  at 104). A stale vendored `components.css` is the silent half of every
  consumer migration: the markup adopts, the CSS does not, and the dot
  strands again with nothing red anywhere. `check-design-sync.sh` now
  reports `in sync`.

### Added

- **A negative control for the byline probe** (`tests/negctl-byline-after.py`).
  It injects the *wrong* fix — `::after` on `:not(:last-child)` instead of
  `::before` on `:not(:first-child)` — which also stops the dot being a
  flex item but keeps it riding the PRECEDING fragment. MEASURED: the
  narrow host goes from 2 lines / 0 stranded to 3 lines / **2 stranded**,
  and the probe flags both. Without this, "no line ends with a separator"
  was a claim no run had ever been able to falsify, because the probe read
  ELEMENTS and the wrong fix leaves no element behind.

### Fixed

- **`tests/blog.test.mjs`: the dead-CSS check read comments as CSS.** It
  scanned every `.class`-looking token in a `<style>` block without
  stripping comments, so the first migration that *documented what it
  removed* (`the old .byline rule is gone`) failed on its own explanation.
  Its sibling font-size check already called `stripComments`; this one did
  not. Stripping does not weaken it — the new mutation
  `leave a genuinely dead selector in the layout style block` still kills
  it — which is the point: the check now fails for real dead CSS and not
  for prose.

- **The home page and the index page no longer re-implement components
  oem-ui already owns.** The first migration moved the blog onto the
  vendored layers, but `index.astro` and `blog/index.astro` kept a second
  copy of five of them in scoped `<style>` blocks — `.hero`/`.hero-title`/
  `.hero-desc`/`.hero-actions` (that is `.cm-head` + `.cm-lede`),
  `.btn-primary` (`.cm-btn` + `.cm-btn-group`), `.status`/`.lbl`/`.val`
  (`.cm-status`), `.list-head` (`.cm-list-head`) and the nine-part
  `.post-list`/`.post-grid` row family (`.cm-rows`). About **160 lines
  of second-implementation CSS** across the two files.

  A local copy is a second owner for a rule the library owns, so a
  library fix never reaches the page and the two drift — which is the
  whole reason the layers are vendored at all. `index.astro` now has
  **no scoped block whatsoever**: the one behaviour it genuinely needed
  (drop the description and the date on a phone) is what the library's
  `.cm-rows--inline` variant already declares, so the page opts into a
  variant instead of re-declaring a rule. The only local declaration
  left anywhere is a `font-size` floor on the index page's `<time>`, and
  that exists because `FormattedDate` renders a bare `<time>`.

  Migrated to: `.cm-head`, `.cm-kicker`, `.cm-lede`, `.cm-btn-group`,
  `.cm-btn`, `.cm-status`+`.cm-status--ok`, `.cm-list-head`, `.cm-rows`
  (with `.cm-rows--inline` on the home page and `.cm-rows--stacked` on
  the index page), `.cm-row__idx/__body/__title/__desc/__meta/__sym`,
  `.cm-list-more`.

  One detail that the CSS cannot catch, and that the first draft of this
  migration got wrong on **both** pages: `cm-row` goes on the `<a>`. Drop
  it and the page still builds, every `cm-row__*` part is still in the
  markup, and every source-level test still passes — the row is just a
  stack of unstyled spans. `tests/verify-migration-webkit.py` asserts the
  row's computed `display` is `flex` for exactly that reason.

  Verified in WebKit at 390x844 (touch) and 1280x900 against the LAN
  build: every row part present and non-collapsed, the status strip's
  hanging indent and its `--ok` glyph both resolving
  (`text-indent:-15.088px` / `padding-left:15.088px`, `::before "●"`),
  the hero button at **179x44** from `--tap`, the description and date
  hidden on the phone by the library variant, the index page's rows
  genuinely stacked (title/desc/meta `top`s strictly increasing), and
  `scrollX == 0` at both widths on both pages.

  Two new contract tests (`blog.test.mjs` 10 → 12) assert the row class,
  every part, and that all 22 retired project classes stay gone from
  both the markup and every scoped block. Both directions, because a
  retired class reappearing in a selector is dead CSS that still ships.

- **Emphasis is no longer declared twice on this site.** `index.astro`
  and `about.astro` each carried their own `strong` rule in a scoped
  block, because oem-ui had no rule for a bare `<strong>` and the browser
  default is weight-only — inside an `--ink-dim` paragraph there was
  nothing but stroke weight to read. oem-ui now owns it as an **element
  default** in `base.css`, so both scoped rules are gone.

  Measured in WebKit at 390px, the consumer rule and the library rule
  render identically: a bare `<strong>` (no class) computes to
  `rgb(232,232,232)` = `--ink` at weight 700 inside `rgb(156,156,156)`
  = `--ink-dim` prose. Delete the library rule and the same element
  computes to `rgb(156,156,156)` — identical to its paragraph, with no
  visual distinction at all, which is the regression these two rules
  were papering over.

  Two new consumer tests, both mutation-checked (`tests/mutate-blog.mjs`
  now 14 mutations, all killed): one fails if a scoped block
  re-declares the element, the other fails if the library rule is
  missing, since guarding a rule that does not exist is a green test
  for the wrong reason.

- **Moved the site to the custom domain `log.oem.ngo`.** `site` is now `https://log.oem.ngo/` and `base` is `/` (a custom domain is served at the root, not under a project sub-path). The old `omiinaya.github.io/oem-log/` URL is auto-301'd by GitHub Pages to the new domain.
  - `85161ac` — Move the blog to log.oem.ngo
  - Documentation updated across `README.md`, `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md` to describe the custom-domain topology, why a `base` mismatch renders the site unstyled rather than broken, and why `public/CNAME` is ignored under `build_type: workflow`.

### Deployment notes (not a code change)

- `public/oem-log/index.html` is a hand-written redirect shim from the move. It is **dead weight**: GitHub auto-301s the old project path before any file is served. Left in place, harmless, but it is not what performs the redirect.
- `https_enforced` is `false` on the Pages site and stays that way. GitHub never provisions an origin cert for a hostname proxied through Cloudflare, so setting it fails permanently with "The certificate does not exist yet". TLS is enforced on the Cloudflare zone instead: `always_use_https = on` and `min_tls_version = 1.2`. Turning on `always_use_https` is what closes the plaintext hop in GitHub's own auto-301.

## [0.1.0] — 2026-09-24

Initial public launch of oem/log.

### Added

- Astro static blog scaffolded from the official `blog` template, set up as a GitHub Pages **project site** under `/oem-log/`.
  - `4c0bde4` — Initial oem/log: CLI-mono dev blog with first post
- **CLI-mono design system**: pure black/grey/white monospace, terminal identity, dark by default with an explicit light toggle persisted in `localStorage['oem-log-theme']`, flash-prevention inline script, themed scrollbar.
  - `4c0bde4`, plus the muted variant adopted after design exploration (see sketches)
- **Base-path support** so all internal links/favicon/sitemap resolve under `/oem-log/` via `import.meta.env.BASE_URL`.
  - `af8e980` — Add GitHub Pages CI workflow and base path
  - `4cbbf15` — Prefix all internal links with base path for GitHub Pages subpath
- **Deploy pipeline**: `.github/workflows/deploy.yml` builds `dist/` and publishes to Pages on push to `main`.
  - `af8e980`, enabled via GitHub Actions API
- **First post**: "Building a watchdog that finally stopped lying to us" (journey of a self-healing watchdog, with the real wiring mistakes and their fixes).
  - `4c0bde4`

### Changed

- **Mobile compatibility pass**: header nav wraps below 640px, article/about reading column made fluid (`width:100%` + `max-width` cap), comfortable side padding on narrow screens, article typography tuned for compact phones.
  - `e6ba710` — Responsive header: wrap nav on mobile to prevent overflow
  - `850a0d6` — Make post/about main fluid on mobile (width:100%)
  - `79bdddd` — Add comfortable side padding to article pages on mobile
  - `05d91b6` — Tune article typography for comfortable mobile reading
- **Editorial clarity**: first mention of the proxy relay now introduces it so cold readers have context; removed the "sensitive details" line from the about page.
  - `58e9c56` — Introduce the proxy relay in the watchdog article
  - `be2ad26` — Slim the about page "what it is not" list

### Infra / docs

- Agent-facing docs: README, AGENTS.md, CLAUDE.md, CONTRIBUTING.md (current commit range, see git log).

## Notes

- Git history is an open, public record. Commit author is always `omiinaya`; the box's global identity is never used here.
- `dist/`, `.astro/`, `node_modules/`, `sketches/` are gitignored build artifacts/scratch.