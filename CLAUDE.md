# CLAUDE.md

Coding-agent signpost for oem/log. Read [AGENTS.md](./AGENTS.md) first — it has the full repo map, config rules, and design system. This file is the short version.

## What this is

Astro static dev blog deployed to GitHub Pages. Node >= 22.12. Every push to `main` auto-builds and deploys via `.github/workflows/deploy.yml`.

## Critical rules (violating these breaks things)

1. **`base: '/oem-log/'`** is set in `astro.config.mjs`. Every internal link must use `import.meta.env.BASE_URL` — never a hardcoded `href="/..."`. (BaseHead, Header, HeaderLink already do this.)
2. **`src/content.config.ts` validates post frontmatter.** Missing `title`/`description`/`pubDate` fails the build. Run `npm run build` to catch it.
3. **Commit as `omiinaya <omar@mrxlab.net>`** (repo-local identity). The box's global git identity is a real name and must not appear in this repo.
4. **Don't commit** `dist/`, `.astro/`, `node_modules/`, `sketches/` (all gitignored).
5. **Site is public** — never add sensitive/internal identifiers (real names, IPs, infra topology) to posts or `src/consts.ts`.
6. **No post publishes without the maintainer's explicit approval.**

## Design

CLI-mono theme: black/grey/white monospace, **dark by default**, light via opt-in toggle. Tokens in `src/styles/global.css` (`:root` dark, `[data-theme='light']` overrides). Theme toggle in `Header.astro` stores `localStorage['oem-log-theme']` and sets `data-theme`, with an early inline script to prevent theme flash.

## Common tasks

| Task                          | What to touch                                                        |
| :---------------------------- | :------------------------------------------------------------------- |
| Add a post                    | `src/content/blog/<slug>.md` (frontmatter: title, description, pubDate) |
| Change site name/description  | `src/consts.ts`                                                      |
| Change theme/accent/layout    | `src/styles/global.css` (tokens), `BlogPost.astro` (article type)    |
| Add a nav link                | `src/components/Header.astro` (+ HeaderLink for active state)        |
| Change public site URL/base   | `astro.config.mjs` (keep `site` + `base` consistent)                 |

## Verify before finishing

- `npm run build` succeeds.
- Grep the built `dist/` for any `(href|src)="/` that isn't base-prefixed (a stale root-absolute link).
- Commit message concise; aim for `omiinaya` authorship; push `main`.

See [AGENTS.md](./AGENTS.md) for the full workspace map and deploy gotchas.