/**
 * oem-ui site config, adapted for oem/log.
 *
 * Copied from /root/projects/oem-ui/src/astro/config.ts on 2026-09-30, the
 * file that calls itself "the ONE place to set your identity". Before this,
 * the blog's identity lived in three places: src/consts.ts (title, handle,
 * email), and the GitHub URL written out inside Header.astro's markup
 * beside the brand text in that same file. Header.astro now reads all of
 * it from here, so a change to the site's name or its repo is one edit.
 *
 * src/consts.ts is still the source for the *content* (post metadata,
 * RSS, bylines); it is not deleted, because deleting the blog's own
 * constants is this project's call and not the design system's. This file
 * holds only what the library's chrome needs.
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