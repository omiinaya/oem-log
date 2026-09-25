# oem/log

A dark, terminal-edged dev blog built with [Astro](https://astro.build), published as a static site on GitHub Pages.

- **Live:** <https://omiinaya.github.io/oem-log/>
- **Static site:** no server runtime, no database. GitHub Actions builds `./dist/` and deploys it to Pages on every push to `main`.

## Requirements

- Node.js **>= 22.12** (see `package.json` `engines`)
- npm

## Quick start

```bash
npm install
npm run dev      # http://localhost:4321
```

## Commands

| Command           | Action                                                   |
| :---------------- | :------------------------------------------------------- |
| `npm install`     | Install dependencies                                      |
| `npm run dev`     | Local dev server at `localhost:4321`                      |
| `npm run build`   | Build the production site to `./dist/`                    |
| `npm run preview` | Preview the built site locally before deploying           |

## Configuration

### Site URL and base path (`astro.config.mjs`)

The site lives at a sub-path, not the repo root, so two settings must stay in sync:

- `site: 'https://omiinaya.github.io/oem-log/'`
- `base: '/oem-log/'`

The `base` is the GitHub Pages project-site sub-path. **Every internal link** must be base-aware — in this codebase that means using `import.meta.env.BASE_URL` (see AGENTS.md), never a hardcoded `href="/..."`.

Fonts are configured here too via `fontProviders.local()` (Atkinson regular/bold from `src/assets/fonts/`).

### Global site data (`src/consts.ts`)

`SITE_TITLE`, `SITE_DESCRIPTION`, `AUTHOR_HANDLE`, `AUTHOR_NAME`, `AUTHOR_EMAIL`, `AUTHOR_GITHUB`. Change the site name/description/contact here; the components import from this one file.

### Content schema (`src/content.config.ts`)

Frontmatter is validated against a Zod schema. A post file with missing/invalid frontmatter fails the build. Supported fields:

| Field          | Type     | Required |
| :------------- | :------- | :------- |
| `title`        | string   | yes      |
| `description`  | string   | yes      |
| `pubDate`      | date     | yes      |
| `updatedDate`  | date     | no       |
| `heroImage`    | image    | no       |
| `tags`         | string[] | no       |

## Deployment

Push to `main` and GitHub Actions does the rest:

1. `.github/workflows/deploy.yml` triggers on push to `main` and `workflow_dispatch`.
2. The `build` job checks out, installs with `npm ci`, runs `npm run build`, uploads `dist/` as a Pages artifact.
3. The `deploy` job publishes it to GitHub Pages.

**GitHub Pages must be enabled** on the repo (Settings → Pages → source = GitHub Actions) for the deploy job to succeed. If a deploy fails with a 404, Pages is usually disabled or still provisioning.

## Project layout

```
astro.config.mjs     site URL + base path + font config
package.json         scripts, node engine, deps
src/consts.ts        global site data
src/content.config.ts blog frontmatter schema
src/content/blog/    posts, one markdown file each (slug = filename)
src/layouts/         BlogPost.astro + base layout
src/components/      Header, Footer, BaseHead, HeaderLink, FormattedDate
src/pages/           routes: index, blog/index, blog/[slug], about, rss
src/styles/global.css design tokens + base styles
public/              favicons (served at site root)
.github/workflows/   deploy.yml — Pages build + deploy
```

## License

MIT