# Contributing to oem/log

Thanks for helping with the blog. This guide covers local setup, how to make changes, and how to get them deployed. Everything here is mechanical — config, build, deploy. For the design system and repo map, read [AGENTS.md](./AGENTS.md) first.

## Local setup

```bash
npm install
npm run dev
```

The dev server runs at `http://localhost:4321`. Edit files and it hot-reloads.

To preview the production build instead:

```bash
npm run build
npm run preview
```

Requires Node **>= 22.12**.

## What you can change and where

### Add a post

1. Create `src/content/blog/<slug>.md`, e.g. `src/content/blog/your-topic.md`. The filename becomes the URL slug.
2. Write frontmatter at the top:

```markdown
---
title: 'Your title'
description: 'One or two lines, shown in lists and metadata.'
pubDate: 'Sep 24 2026'
---
```

   Optional frontmatter: `updatedDate`, `heroImage` (an imported/local image), `tags` (array of strings).

3. Write the body in Markdown. Headings (`##`) render as article sections.
4. `npm run build` to confirm frontmatter validates and the post compiles.
5. Commit as `omiinaya` and push `main` to deploy.

> Do not publish a post without the maintainer's explicit approval.

### Change site-wide text/branding

Edit `src/consts.ts`: `SITE_TITLE`, `SITE_DESCRIPTION`, author fields. Components import from here, so one change propagates.

### Change design / theme

- **Tokens & base styles:** `src/styles/global.css`. Colors, spacing, typography scale, responsive rules live here as CSS variables. Dark values are on `:root`, light overrides on `[data-theme='light']`.
- **Article page typography:** `src/layouts/BlogPost.astro` (its own `<style>` block, incl. the ≤680px responsive tweaks).
- **Header/nav/theme toggle:** `src/components/Header.astro` and `HeaderLink.astro`.

### Change the site URL or host it elsewhere

Edit `astro.config.mjs`:
- `site` = canonical URL
- `base` = sub-path the site is served under (currently `/oem-log/` for the GitHub Pages project site)

**When changing `base`, re-check every internal link.** They must use `import.meta.env.BASE_URL`; if you hardcode `/...` paths they will break under a non-root base.

## Committing and deploying

- Commit identity: `omiinaya <omar@mrxlab.net>` (repo-local). The machine's global git identity is a real name; never use it here.
- Almost always commit to `main`, then push. `.github/workflows/deploy.yml` builds `dist/` and deploys to GitHub Pages automatically.
- Never commit `dist/`, `.astro/`, `node_modules/`, or `sketches/` (gitignored).
- Keep commits small and messages concise. Prefer building before pushing so failures don't land on `main`.

### If a deploy fails

Check `.github/workflows/deploy.yml` run on GitHub first. Common causes:

1. **Pages disabled on the repo** → enable it: Settings → Pages → Source = GitHub Actions. (Deploy 404s here.)
2. **Frontmatter schema error** → `npm run build` locally shows it; CI fails at the build step.
3. **npm install / node version** → `engines` requires Node >= 22.12; CI uses node 22.

## House style for the build

- `npm run build` must pass before pushing to `main`.
- After a build, grep `dist/` for stray `(href|src)="/` to catch a hardcoded root-absolute link (should be none — all base-aware).
- This blog has one post and one visual theme; keep additions consistent with the CLI-mono system rather than introducing a competing style.