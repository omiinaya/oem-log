# Changelog

All notable changes to oem/log. Format loosely follows [Keep a Changelog](https://keepachangelog.com/), and each entry is anchored to the commit that landed it (author `omiinaya`).

## [Unreleased]

- (nothing yet — add in-flight work here)

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