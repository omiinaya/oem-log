/* Contract tests for oem/log after the oem-ui migration.
 *
 * The blog had NO test suite, which is the other half of why the drift
 * went unnoticed: a consumer with no tests cannot notice that it stopped
 * being a consumer. These lock the four things that actually broke, plus
 * the dead-CSS failure the build cannot see.
 *
 * Run: npm test
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const root = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const read = (p) => readFileSync(join(root, p), 'utf8');
const src = (p) => readFileSync(join(root, 'src', p), 'utf8');

const astroFiles = () => {
	const out = [];
	(function walk(d) {
		for (const e of readdirSync(d)) {
			const p = join(d, e);
			if (statSync(p).isDirectory()) walk(p);
			else if (e.endsWith('.astro')) out.push(p);
		}
	})(join(root, 'src'));
	return out;
};
const stripComments = (css) => css.replace(/\/\*[\s\S]*?\*\//g, '');

/* ---------- the migration itself ---------- */

test('the design system is imported, in order, and last is the site layer', () => {
	const head = src('components/BaseHead.astro');
	const order = ['cli-mono/tokens.css', 'cli-mono/base.css', 'cli-mono/components.css', 'styles/site.css'];
	let at = -1;
	for (const layer of order) {
		const i = head.indexOf(layer);
		assert.ok(i > -1, `${layer} is never imported from BaseHead.astro`);
		assert.ok(i > at, `${layer} must come after the layer before it`);
		at = i;
	}
});

test('the old hand-written design system is gone', () => {
	// A comment naming the file it replaced is fine. An import is not.
	for (const f of astroFiles()) {
		const body = readFileSync(f, 'utf8');
		const imports = body.match(/^import\s+['"][^'"]*global\.css['"]/m);
		assert.ok(!imports, `${f} still imports the retired global.css`);
	}
	assert.ok(!existsSync(join(root, 'src/styles/global.css')),
		'src/styles/global.css still exists; it re-declared the whole design system');
});

test('emphasis is left to the library, not re-declared per page', () => {
	// The blog used to own `strong` TWICE - once in the home page's scoped
	// block and once on /about - because oem-ui had no rule for it. That is
	// the whole failure this library exists to prevent: a second
	// implementation of surface the design system owns, so a library fix
	// never reaches the page.
	//
	// A scoped, comment-stripped scan, so a COMMENT explaining the removal
	// is not read as the rule coming back. The vendored base layer is
	// skipped: it legitimately declares the element default, and that is the
	// one place it is allowed.
	for (const f of astroFiles()) {
		if (f.includes(`${root}src/styles`)) continue;
		const blocks = (readFileSync(f, 'utf8').match(/<style>[\s\S]*?<\/style>/g) || [])
			.map(stripComments).join('\n');
		for (const m of blocks.matchAll(/(^|[\s,}])(strong|\bb)\b[^{}]*\{/g)) {
			assert.fail(`${f.replace(root, '')} re-declares an element the library already owns: ${m[0].trim()}`);
		}
	}
	// ...and the library really does declare it, or this test would be
	// green for the wrong reason: guarding a rule that does not exist yet.
	const base = stripComments(read('src/styles/cli-mono/base.css'));
	assert.ok(/(^|\n)strong,\s*b\s*\{/.test(base),
		'the vendored base layer has no strong/b element default to inherit');
});

test('the vendored layers are byte-identical to the library', () => {
	// oem-ui's own check-design-sync.sh proves this across the fleet; this
	// pins it in the blog's own suite so `npm test` alone catches it.
	const map = {
		'src/styles/cli-mono/tokens.css': 'src/styles/tokens.css',
		'src/styles/cli-mono/base.css': 'src/styles/base.css',
		'src/styles/cli-mono/components.css': 'src/styles/components.css',
		'src/js/cli-mono.js': 'src/js/cli-mono.js',
	};
	const lib = process.env.OEM_UI_SRC || '/root/projects/oem-ui';
	for (const [vendored, origin] of Object.entries(map)) {
		if (!existsSync(join(lib, origin))) continue; // library not on this box
		assert.equal(read(vendored), readFileSync(join(lib, origin), 'utf8'),
			`${vendored} has drifted from the library; run scripts/install.sh`);
	}

	// The Astro COMPONENTS are vendored exactly the same way and drift
	// exactly the same way, and NOTHING OUTSIDE this repo would notice:
	// check-design-sync.sh's MAP names the three CSS layers and the two
	// runtime files, and has no entry for src/astro/. install.sh --astro
	// promises "--astro names any consumer whose copy of a library
	// component has drifted"; until this loop, the only thing that could
	// was this suite. Measured 2026-10-09: Header.astro and
	// HeaderLink.astro were both stale here, and current.ts - the module
	// both of them import - was missing outright.
	//
	// config.ts is the ONE exception and it is deliberate, not a gap:
	// install.sh skips an existing config.ts because "it is the one file
	// the consumer OWNS and edits with its own title, author and email".
	// So it is asserted to exist and to be THIS site's identity in the
	// identity test below, never to be byte-identical.
	const astroDir = join(root, 'src', 'astro');
	if (existsSync(join(lib, 'src/astro')) && existsSync(astroDir)) {
		for (const f of readdirSync(astroDir)) {
			if (f === 'config.ts') continue;
			const origin = join(lib, 'src/astro', f);
			assert.ok(existsSync(origin),
				`src/astro/${f} exists here but not in the library: it is a fork or a leftover`);
			assert.equal(readFileSync(join(astroDir, f), 'utf8'), readFileSync(origin, 'utf8'),
				`src/astro/${f} has drifted from the library; run scripts/install.sh --astro`);
		}
	}
});

test('renamed classes are the library ones, and the old names are gone', () => {
	// This is the exact bug oem-links shipped: the markup was renamed to
	// cm-kicker but the selector was left as .kicker, so the margin was
	// dead CSS and the eyebrow welded itself to the title.
	//
	// Parse the class attribute into tokens instead of regexing inside it.
	// Two attempts at one regex were both wrong: a plain \bkicker\b matches
	// the tail of "cm-kicker", and `(?:^|[\s"])` never matches because ^
	// anchors to the whole string, not to the text after class=". A test
	// that cannot match the bug it names is worse than no test.
	const renames = { kicker: 'cm-kicker', 'sr-only': 'cm-sr-only', prose: 'cm-prose' };
	const olds = new Set(Object.keys(renames));
	for (const f of astroFiles()) {
		const body = readFileSync(f, 'utf8');
		for (const m of body.matchAll(/class="([^"]*)"/g)) {
			for (const token of m[1].split(/\s+/)) {
				assert.ok(!olds.has(token),
					`${f} still uses class="${token}" (should be ${renames[token]})`);
			}
		}
	}
	// and the new names really are used
	const all = astroFiles().map(f => readFileSync(f, 'utf8')).join('\n');
	for (const n of Object.values(renames)) {
		assert.ok(all.includes(`class="${n}"`) || all.includes(`${n} `), `${n} is never used in markup`);
	}
});

/* ---------- the second migration: library components, not local copies ---------- */

test('the home and index pages use the library row, not a local copy', () => {
	// The first migration moved the blog onto the vendored layers but left
	// the home page and the index page owning a SECOND implementation of
	// `.cm-head`, `.cm-list-head`, `.cm-status` and the whole row list -
	// nine parts, ~160 lines of scoped CSS. A local copy is a second owner
	// for a rule the library owns, so a library fix never reaches the page.
	//
	// The row class is the load-bearing one and it is the one a CSS-only
	// check cannot see: drop `cm-row` off the anchor and every part still
	// lays out, the page still builds, and the row is just a stack of
	// spans. That is the exact state the first draft of this migration
	// shipped into.
	for (const f of ['pages/index.astro', 'pages/blog/index.astro']) {
		const body = src(f);
		assert.ok(/<a class="cm-row" href=/.test(body),
			`${f}: every row anchor needs class="cm-row" or the library does not style it`);
		for (const part of ['cm-row__idx', 'cm-row__body', 'cm-row__title',
			'cm-row__desc', 'cm-row__meta', 'cm-row__sym']) {
			assert.ok(body.includes(`class="${part}"`),
				`${f}: .${part} is missing from the row markup`);
		}
	}
	// and the variant is what the library declares
	assert.ok(/class="cm-rows cm-rows--inline"/.test(src('pages/index.astro')),
		'the home page opts into the library\'s --inline variant, which is what hides the desc and date on a phone');
	assert.ok(/class="cm-rows cm-rows--stacked"/.test(src('pages/blog/index.astro')),
		'the index page opts into the library\'s --stacked variant');
});

test('the retired local classes do not come back', () => {
	// These are the project classes the migration deleted. They are not
	// merely unused: each was a re-implementation of a component the
	// library owns, so a reappearance means a second owner again. Assert
	// both directions - no markup uses them, and no scoped block selects
	// them - because a rule with no markup behind it is dead CSS that
	// still ships.
	const retired = ['hero', 'hero-title', 'hero-desc', 'hero-actions', 'btn-primary',
		'status', 'lbl', 'val', 'list-head', 'sub', 'latest', 'all-notes',
		'post-list', 'post-grid', 'post-idx', 'post-num', 'post-body', 'post-title',
		'post-desc', 'post-date', 'post-sym', 'arrow'];
	for (const f of astroFiles()) {
		const raw = readFileSync(f, 'utf8');
		const markup = raw.replace(/<style>[\s\S]*?<\/style>/g, '').replace(/<!--[\s\S]*?-->/g, '');
		for (const m of markup.matchAll(/class="([^"]*)"/g)) {
			for (const token of m[1].split(/\s+/)) {
				assert.ok(!retired.includes(token),
					`${f.replace(root, '')} uses class="${token}", a local copy of a library component`);
			}
		}
		const style = (raw.match(/<style>[\s\S]*?<\/style>/g) || []).map(stripComments).join('\n');
		for (const c of retired) {
			assert.ok(!new RegExp(`\\.${c}(?![\\w-])`).test(style),
				`${f.replace(root, '')}: .${c} is back in a scoped block; the library owns it`);
		}
	}
});

/* ---------- dead CSS: the failure the build cannot see ---------- */

test('no scoped-style selector targets a class its own file does not use', () => {
	// Dead CSS still builds, still ships and still renders. Nothing in the
	// pipeline notices, and a visual pass reads the CSS rather than the
	// computed layout. This is the check that would have caught the
	// welded kicker on oem-links.
	//
	// Cross-file classes are legitimate: HeaderLink.astro adds .nav-active
	// to the anchors that Header.astro styles, and nothing in Header's
	// own markup mentions it. So a class counts as used if ANY file's
	// markup uses it - a per-file check reports that as dead and trains
	// you to delete a working rule.
	const used = new Set();
	for (const f of astroFiles()) {
		const markup = readFileSync(f, 'utf8').replace(/<style>[\s\S]*?<\/style>/g, '');
		for (const m of markup.matchAll(/class="([^"]*)"/g)) {
			for (const c of m[1].split(/\s+/)) if (c) used.add(c);
		}
		// and classes assigned from a JS expression, e.g. const x = 'nav-active'
		for (const m of markup.matchAll(/'([a-z][a-z0-9_-]*)'/g)) used.add(m[1]);
	}
	const problems = [];
	for (const f of astroFiles()) {
		const style = (readFileSync(f, 'utf8').match(/<style>[\s\S]*?<\/style>/g) || []).join('\n');
		for (const m of style.matchAll(/\.([a-z][a-z0-9_-]*)/gi)) {
			const cls = m[1];
			if (cls.startsWith('cm-') || /^\d/.test(cls)) continue;
			if (!used.has(cls)) problems.push(`${f.replace(root, '')}: .${cls} is styled but never used`);
		}
	}
	assert.deepEqual(problems, [], problems.join('\n'));
});

test('no font-size in a scoped block is below the mobile floor', () => {
	// --min-font is 12px and the flooring rule lives in base.css, which an
	// Astro scoped block outranks. So the floor has to be declared next to
	// the size it overrides. Anything BARE is a phone-sized regression.
	//
	// `max(var(--min-font), 0.72rem)` is the floored form and is fine. A
	// bare `0.72rem` is not - and reading the bare number out of a floored
	// declaration reports a fixed rule as a violation, which is how a real
	// regression gets filed next to a non-problem.
	const problems = [];
	for (const f of astroFiles()) {
		const body = stripComments(readFileSync(f, 'utf8'));
		for (const m of body.matchAll(/font-size:\s*([^;]+);/g)) {
			const value = m[1].trim();
			if (value.includes('var(--min-font)')) continue;
			const r = value.match(/([\d.]+)rem/);
			if (!r) continue;
			const px = parseFloat(r[1]) * 16;
			if (px < 12) {
				problems.push(`${f.replace(root, '')}: font-size ${value} = ${px}px, under --min-font`);
			}
		}
	}
	assert.deepEqual(problems, [], problems.join('\n'));
});

/* ---------- the theme handoff ---------- */

/* ---------- the header is the library's, not a second copy ---------- */

test('the header is the library component, not a hand-rolled bar', () => {
	// The migration that removed this project's second design system left
	// ONE second implementation standing: the header. 170 lines of scoped
	// CSS in one component - its own sticky bar, brand, pipe-separated nav,
	// theme toggle, GitHub link and three breakpoints - and the library has
	// owned every one of those since before the blog's rows were migrated.
	//
	// Measured in WebKit at 390x844, that copy was 121px tall (the nav
	// wrapped onto a second row) and its theme toggle measured 32x44: a
	// pill. Both defects are in classes the library defines and this
	// component did not use.
	// Re-derived 2026-10-09, when the last second implementation - the
	// 2026-09-30 fork of the library header - became a wrapper. The old
	// assertion GREPPED this file for the class names, which is exactly
	// what a fork satisfies and a wrapper does not: the fork contained
	// every one of them. The claim is now inverted - the consumer file
	// writes NONE of the header, and the vendored library copy writes ALL
	// of it - so a fork cannot pass either half.
	//
	// All three comment forms are stripped first. The wrapper's own
	// frontmatter names `.cm-header__link` while explaining why it must
	// not emit one, and it literally says "There is no <header>, no
	// <style> block" - so an unstripped scan trips on its own
	// explanation and reports violations no markup commits. A class
	// named in a comment is the same trap as a hex named in one.
	const wrap = src('components/Header.astro');
	const code = wrap
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/\{\/\*[\s\S]*?\*\/\}/g, '')
		.replace(/\/\*[\s\S]*?\*\//g, '')
		.replace(/(^|\s)\/\/.*$/gm, '$1');
	// The <style>/<header> checks run on `code`, which still HAS its
	// style tags; `markup` below has them removed with their contents.
	assert.ok(!/<style>/.test(code),
		'Header.astro carries a scoped stylesheet; every header metric belongs to the library');
	assert.ok(!/<header[\s>]/.test(code),
		'Header.astro opens its own <header> element; that is a second implementation');
	const markup = code.replace(/<style>[\s\S]*?<\/style>/g, '');

	// It RENDERS the library's markup...
	assert.ok(/from\s+['"]\.\.\/astro\/Header\.astro['"]/.test(code),
		'Header.astro must import the library header from ../astro/Header.astro');
	assert.ok(/<LibHeader/.test(code),
		'Header.astro renders no <LibHeader>; the site would ship no header at all');

	// ...and writes none of it itself.
	for (const c of ['cm-header', 'cm-header__nav', 'cm-header__brand',
		'cm-header__links', 'cm-header__controls', 'cm-icon-btn']) {
		assert.ok(!markup.includes(c),
			`Header.astro hand-writes .${c}; the library's vendored header owns it`);
	}

	// ...and the copy that DOES render them is the library's, in-repo.
	const lib = src('astro/Header.astro');
	for (const c of ['cm-header', 'cm-header__nav', 'cm-header__brand',
		'cm-header__links', 'cm-header__controls', 'cm-icon-btn']) {
		assert.ok(lib.includes(c), `the vendored library header no longer emits .${c}`);
	}
});

test('the current nav link is decided by the library, not by this project', () => {
	// Four pages each decided "which link is am I on" by hand, in a
	// .nav-active class the library cannot see. HeaderLink owns that
	// decision, and it normalises the trailing slash, the query, the hash
	// and the site base before comparing - which is why /blog stays
	// current on /blog/a-post and on /blog/.
	// Re-derived 2026-10-09. The old version asserted that THIS file
	// imported <HeaderLink> and that a LOCAL HeaderLink.astro held a
	// `strip()` normaliser - which pinned the fork, not the guarantee.
	// The guarantee is: one matcher, in one module, called by both
	// library components, and no third copy anywhere in this project.
	//
	// Checked HERE, inside this repo, and not by reading the library's
	// path: a test that reaches outside the repository passes on this
	// host and fails on every CI runner with EACCES, which is the one
	// failure a suite that gates a deploy must never have. src/astro/
	// is vendored, so it is inside this repo while still being the
	// library's code - which is what makes it checkable at all.
	const hdr = src('components/Header.astro');
	const cur = src('astro/current.ts');
	assert.ok(/export const isCurrentPage/.test(cur),
		'src/astro/current.ts no longer exports isCurrentPage; the matcher has no home');
	for (const f of ['astro/Header.astro', 'astro/HeaderLink.astro']) {
		const body = src(f);
		assert.ok(/from\s+['"]\.\/current['"]/.test(body) && /isCurrentPage\(/.test(body),
			`${f} does not call the shared isCurrentPage matcher; a second copy has appeared`);
	}

	// The old hand-computed state must be gone from this project
	// entirely - and the PRIVATE normaliser with it. Both used to live
	// here: `nav-active` in the markup, `const strip =` in the local
	// HeaderLink, and a third spelling of the same idea inlined into the
	// fork's nav block as `matchSegment={l.label === 'notes' || ...}`.
	for (const f of astroFiles()) {
		const body = stripComments(readFileSync(f, 'utf8'));
		assert.ok(!/const strip\s*=/.test(body),
			`${f.replace(root, '')} carries its own strip() normaliser; src/astro/current.ts owns that`);
		assert.ok(!/nav-active/.test(body),
			`${f.replace(root, '')} still computes .nav-active instead of aria-current`);
	}

	// The wrapper's ONLY statement about "which page am I on" is which
	// link is allowed to stay lit past its own path. Every hand-written
	// `active: true` boolean - the trap that forced the fork - is gone.
	// Read from the comment-stripped file: the frontmatter explains the
	// opt-in by naming it, so an unstripped grep finds the phrase in
	// prose and a mutation that deletes the real one passes.
	const hcode = stripComments(hdr);
	assert.ok(/matchSegment:\s*true/.test(hcode),
		'the notes link must opt in with matchSegment, or /blog goes dark on /blog/a-note');
	assert.ok(!/active:\s*true/.test(hcode),
		'Header.astro hand-writes `active: true`; that is the per-page boolean that drifts');
});

test('the site identity comes from one config, not three places', () => {
	// config.ts calls itself "the ONE place to set your identity". The blog
	// kept its title in src/consts.ts and its GitHub URL inline in the
	// header's markup. The first pass moved the real values into
	// components/config.ts - and left the file the LIBRARY components
	// actually read, src/astro/config.ts, holding the library's own
	// `oem/ui` placeholder. Two configs is the same disease as three
	// places: whichever one is dead is the one a reader will edit.
	//
	// The identity now lives in src/astro/config.ts and nowhere else.
	// That is the file install.sh --astro refuses to overwrite ("the one
	// file the consumer OWNS"), so it is the only place that survives a
	// re-vendor - which is precisely why it has to be the real one.
	const cfg = src('astro/config.ts');
	const def = stripComments(cfg);
	assert.ok(/export const SITE/.test(cfg), 'src/astro/config.ts must export SITE');
	assert.ok(!existsSync(join(root, 'src/components/config.ts')),
		'the second config is back; src/astro/config.ts is the one the library reads');

	// Exactly one definition across the whole source tree, so "one config"
	// is counted rather than assumed.
	const defs = [];
	(function walk(d) {
		for (const e of readdirSync(d)) {
			const p = join(d, e);
			if (statSync(p).isDirectory()) walk(p);
			else if (e.endsWith('.astro') || e.endsWith('.ts')) {
				if (/export const SITE\s*=/.test(readFileSync(p, 'utf8'))) {
					defs.push(p.replace(root + '/', ''));
				}
			}
		}
	})(join(root, 'src'));
	assert.deepEqual(defs, ['src/astro/config.ts'],
		`SITE must be defined exactly once: found ${defs.join(', ') || 'none'}`);

	// The values are THIS site's, read from the declaration and not from
	// the prose around it - the file's own comment names `oem/ui` while
	// explaining that it used to be wrong, so an unstripped scan trips on
	// its own explanation and calls the fix a bug.
	assert.ok(def.includes("title: 'oem/log'"), 'the site title is not oem/log');
	assert.ok(!/title:\s*'oem\/ui'/.test(def),
		'src/astro/config.ts still carries the library placeholder; the brand would print $ oem/ui');
	assert.ok(def.includes('https://log.oem.ngo'), 'SITE.url is not this site');

	// The wrapper reads SITE from it and hands it to the header as the
	// brand, so the header cannot print an identity the config does not
	// name.
	const hdr = src('components/Header.astro');
	assert.ok(/from\s+['"]\.\.\/astro\/config['"]/.test(hdr),
		'Header.astro must read SITE from ../astro/config');
	assert.ok(/brand=\{SITE\.title\}/.test(hdr),
		'Header.astro must pass SITE.title as the brand; a literal would be a second source of truth');
	// No literal repo URL in the header markup any more.
	const markup = stripComments(hdr).replace(/<style>[\s\S]*?<\/style>/g, '');
	assert.ok(!/https:\/\/github\.com\/[a-z]/i.test(markup),
		'Header.astro hardcodes a github.com URL in its markup; that is what SITE.github is for');

	// And none in the CALL either. Scanning only the component passed with
	// the literal sitting in a page, because the page is where the header
	// is actually invoked: `<Header extraLinks={[{ href: 'https://…',
	// label: 'github' }]} />` is the same second source of truth, one file
	// over. Every entry point is a place it can hide, so every entry point
	// is scanned.
	for (const f of astroFiles()) {
		const body = readFileSync(f, 'utf8')
			.replace(/<style>[\s\S]*?<\/style>/g, '')
			.replace(/<!--[\s\S]*?-->/g, '');
		for (const m of body.matchAll(/https:\/\/github\.com\/[a-z][^\s'"`)]*/gi)) {
			assert.fail(`${f.replace(root, '')} hardcodes the repo URL ${m[0]}; read SITE.github`);
		}
	}
});

test('every entry point declares the project theme key and the runtime', () => {
	const entries = ['pages/index.astro', 'pages/about.astro', 'pages/blog/index.astro', 'layouts/BlogPost.astro'];
	for (const e of entries) {
		const body = src(e);
		assert.ok(body.includes('data-cm-theme-key="oem-log-theme"'),
			`${e} must declare data-cm-theme-key="oem-log-theme" or returning readers lose their theme`);
		assert.ok(/import\s+['"](\.\.\/)+js\/cli-mono\.js['"]/.test(body),
			`${e} must load the library runtime, which owns the toggle`);
	}
	// The old key must still be READABLE, or a light-theme reader gets a
	// black flash and then finds their preference gone.
	//
	// Assert the guard READS the keys it is given rather than that it
	// contains them literally: the guard takes them from the
	// data-cm-theme-* attributes on <html>, which is what stops it
	// drifting from the runtime. A test that pinned the old
	// `var keys = [...]` shape would fail on the fix, not the bug.
	//
	// The guard lives in BaseHead.astro, the component that owns <head>.
	// It used to live in Header.astro, which renders inside <body> — so
	// it ran after the stylesheets had painted, and the flash it exists
	// to prevent still happened.
	//
	// The guard BODY now lives in the library's own file, inlined with
	// ?raw. So BaseHead is asserted to WIRE it, and the vendored file is
	// asserted to BE the guard. Checking the component for the body would
	// be a check naming a superseded symbol: it would pass for any copy
	// of the guard, including a broken one, and fail the moment the
	// project stopped hand-rolling it. Which is the whole point of the
	// change.
	const head = src('components/BaseHead.astro');
	assert.ok(/cli-mono-theme-guard\.js\?raw/.test(head),
		'BaseHead must inline the library guard with ?raw; a hand-rolled copy is what caused the flash');
	assert.ok(head.includes('set:html={themeGuard}'),
		'BaseHead must actually emit the guard');

	const guard = src('js/cli-mono-theme-guard.js');
	assert.ok(guard.includes('data-cm-theme-key'),
		'the FOUC guard must read the project key off <html>');
	assert.ok(guard.includes('data-cm-theme-legacy'),
		'the FOUC guard must read the legacy-key list off <html>');
	assert.ok(guard.includes('localStorage.getItem'),
		'the FOUC guard must actually read storage');
	assert.ok(!guard.replace(/\/\*[\s\S]*?\*\//g, '').includes('localStorage.setItem'),
		'the guard must not write to storage; that is the runtime\'s job, after the paint');

	assert.ok(!src('components/Header.astro').includes('data-theme'),
		'Header.astro renders inside <body> and must not carry the theme guard');
});

test('the theme toggle is not implemented twice', () => {
	const hdr = src('components/Header.astro');
	// The runtime's TOGGLE_SEL already covers .theme-toggle. A second
	// copy of this logic in the component means two handlers writing one
	// attribute.
	assert.ok(!/addEventListener\(\s*['"]click['"]\s*,\s*[^)]*theme/i.test(hdr),
		'Header.astro re-implements the theme toggle that cli-mono.js already owns');
	assert.ok(!/localStorage\.setItem\(\s*['"]oem-log-theme/.test(hdr),
		'Header.astro writes the theme key itself; the runtime owns persistence');
});

/* ---------- the runtime actually ships ---------- */

test('the runtime is referenced as a real import, not a raw src', () => {
	// The documented Astro trap: a <script src> with a variable src and no
	// is:inline is dropped from dist/ entirely, and the page looks wired up
	// with no toggle and no warning.
	for (const e of ['pages/index.astro', 'pages/about.astro', 'pages/blog/index.astro', 'layouts/BlogPost.astro']) {
		const body = src(e);
		const hasScriptTag = /<script[^>]*src=/.test(body);
		const hasImport = /<script>\s*import\s+/.test(body);
		assert.ok(!hasScriptTag || /is:inline/.test(body),
			`${e} uses a raw <script src>; without is:inline Astro drops it from dist/`);
		assert.ok(hasImport || hasScriptTag, `${e} loads no runtime at all`);
	}
});
