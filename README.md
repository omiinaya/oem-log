# oem/log

Short writeups of things we learned while building and breaking stuff. The reusable middle, without the sensitive parts or the full blueprint.

A dark, terminal-edged dev blog built with [Astro](https://astro.build), published as a static site. Dark by default, with a light theme toggle.

## Commands

| Command           | Action                                       |
| :---------------- | :------------------------------------------- |
| `npm install`     | Install dependencies                         |
| `npm run dev`     | Local dev server at `localhost:4321`         |
| `npm run build`   | Build the production site to `./dist/`       |
| `npm run preview` | Preview the build locally before deploying   |

## Structure

- `src/content/blog/` — posts, one markdown file each
- `src/components/` — header, footer, shared UI
- `src/layouts/` — page and post layouts
- `src/styles/global.css` — design tokens and base styles
- `src/pages/` — routes (home, blog index, about)

## License

MIT