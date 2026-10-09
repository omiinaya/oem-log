/**
 * oem/log's site config — the ONE place to set this site's identity.
 *
 * This is `oem-ui/src/astro/config.ts` after the copy step install.sh
 * describes: "the one file the consumer OWNS and edits with its own title,
 * author and email". install.sh --astro deliberately does NOT overwrite it
 * on a re-vendor, so this file survives every sync — which is exactly why
 * the library's components read their default identity from HERE.
 *
 * Until 2026-10-09 the real identity lived in `src/components/config.ts`
 * while THIS file — the one `<Header>`'s `brand = SITE.title` default
 * actually reads — still carried the library's `oem/ui` placeholder. Two
 * configs, one of them live and wrong: rendering `<Header />` with no
 * explicit `brand` printed `$ oem/ui` on this site. src/consts.ts still
 * owns content (post metadata, RSS, bylines); this file owns only what the
 * library's chrome needs.
 *
 * `github` is load-bearing, not decoration: <Header> turns it into the
 * header's GitHub mark. When this file still named a placeholder while the
 * markup hardcoded the real URL, the file that advertised itself as the
 * single source of truth was the one thing the page did not read.
 *
 * The header renders `$ <title>`, so the title is a shell prompt, not a
 * page heading: `$ oem/log`, the same way the other oem sites print.
 */
export const SITE = {
	title: 'oem/log',
	description:
		'Short writeups of things we learned while building and breaking stuff. The reusable middle, without the sensitive parts or the full blueprint.',
	author: '@omiinaya',
	email: 'omar@mrxlab.net',
	github: 'https://github.com/omiinaya',
	url: 'https://log.oem.ngo',
} as const;
