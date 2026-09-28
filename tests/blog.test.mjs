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
	// contains them literally: the guard now takes them from the
	// data-cm-theme-* attributes on <html>, which is what stops it
	// drifting from the runtime. A test that pinned the old
	// `var keys = [...]` shape would fail on the fix, not the bug.
	//
	// The guard lives in BaseHead.astro, the component that owns <head>.
	// It used to live in Header.astro, which renders inside <body> — so
	// it ran after the stylesheets had painted, and the flash it exists
	// to prevent still happened.
	const head = src('components/BaseHead.astro');
	assert.ok(head.includes('data-cm-theme-key'),
		"the FOUC guard must read the project key off <html>");
	assert.ok(head.includes('data-cm-theme-legacy'),
		"the FOUC guard must read the legacy-key list off <html>");
	assert.ok(head.includes('localStorage.getItem'),
		'the FOUC guard must actually read storage');
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
