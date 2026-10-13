#!/usr/bin/env node
/* Mutation harness for the dev-blog contract tests.
 *
 * A test you have not tried to break is a guess. Each mutant reverts ONE
 * thing the migration fixed. A correct mutant makes the suite FAIL. A
 * mutant that leaves it green is reported as a NO-OP, never as a pass.
 */
import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const root = process.cwd();
const run = () => spawnSync('node', ['--test', 'tests/blog.test.mjs'], { encoding: 'utf8' });

const base = run();
if (base.status !== 0) { console.error('baseline is not green; fix that first'); process.exit(1); }
console.log('baseline: 9/9 green\n');

/* [name, file, find, replace] */
const MUTANTS = [
	['re-add the import of the retired global.css', 'src/components/BaseHead.astro',
		"import '../styles/site.css';", "import '../styles/global.css';"],

	['load the layers in the wrong order (components before base)', 'src/components/BaseHead.astro',
		"import '../styles/cli-mono/base.css';\nimport '../styles/cli-mono/components.css';",
		"import '../styles/cli-mono/components.css';\nimport '../styles/cli-mono/base.css';"],

	['rename the markup back to the bare class (the oem-links bug)', 'src/pages/index.astro',
		'class="cm-kicker"', 'class="kicker"'],

	['leave the selector un-renamed too, so the margin is dead CSS', 'src/pages/index.astro',
		'.hero .cm-kicker { margin-bottom: 1rem; }', '.hero .kicker { margin-bottom: 1rem; }'],

	['drop the project theme key from one entry point', 'src/pages/about.astro',
		'\tdata-cm-theme-key="oem-log-theme"\n', ''],

	['drop the runtime import from one entry point', 'src/pages/about.astro',
		"import '../js/cli-mono.js';", ''],

	['re-implement the theme toggle in the component', 'src/components/Header.astro',
		'<!-- The theme toggle is owned by the library runtime',
		'<script>\n\tdocument.querySelector(".theme-toggle")\n\t\t.addEventListener("click", () => {\n\t\t\tlocalStorage.setItem("oem-log-theme", "light");\n\t\t});\n</script>\n<!-- owned by the library runtime'],

	['remove the legacy theme key (returning readers lose their theme)', 'src/components/Header.astro',
		"var keys = ['oem-log-theme', 'cm-theme'];", "var keys = ['oem-log-theme'];"],

	['strip the mobile floor from a scoped block', 'src/pages/index.astro',
		'font-size: max(var(--min-font), 0.72rem);', 'font-size: 0.72rem;'],

	['drift a vendored layer out of sync with the library', 'src/styles/cli-mono/base.css',
		'html {', 'html{ /* drifted */'],

	['leave a dead class behind in a scoped style block', 'src/components/Footer.astro',
		'.footer-meta a:hover { color: var(--ink); }',
		'.footer-meta a:hover { color: var(--ink); }\n	.never-used-thing { color: red; }'],

	// The duplication the migration removed. Re-adding it in a scoped block
	// is a second owner for a rule the library owns.
	['re-declare emphasis in a scoped block', 'src/pages/index.astro',
		'	.hero-actions { display: flex;',
		'	.hero-desc strong { color: var(--ink); }\n	.hero-actions { display: flex;'],

	['re-declare emphasis on a second page too', 'src/pages/about.astro',
		'	.about-body p:first-of-type { margin-top: 0; }',
		'	.about-body strong { color: var(--ink); }\n	.about-body p:first-of-type { margin-top: 0; }'],

	// Guarding a rule that does not exist is a green test for the wrong
	// reason, so removing the library side must also be caught.
	['remove the library element default, leaving the consumer guarding nothing',
		'src/styles/cli-mono/base.css',
		'strong, b { color: var(--ink); font-weight: 700; }',
		'/* strong, b removed by mutation */'],

	// ---- the post-head adoption (the consumer keeps the library surface) ----

	// The hand-rolled post head goes back. A consumer that re-implements
	// library surface is the whole failure the migration addresses, and
	// it is invisible to the drift checker because the vendored files are
	// still in sync - the second copy lives in the site's own layout.
	['hand-roll the article head again instead of using <PostHead>',
		'src/layouts/BlogPost.astro',
		'<PostHead title={title} date={pubDate} updatedDate={updatedDate} />',
		'<header class="post-head"><p class="cm-kicker">note</p>' +
		'<h1>··· {title} ···.md</h1><div class="byline">' +
		'<span>@omiinaya</span><span class="sep" aria-hidden="true">·</span>' +
		'</div></header>'],

	// Stop passing updatedDate. The post page then never renders the
	// three-fragment byline, which is the one that wraps - so the
	// stranded-separator case the library just fixed is never exercised
	// here, while the page still looks completely correct.
	['render <PostHead> without updatedDate, so the wrappable case never renders',
		'src/layouts/BlogPost.astro',
		'<PostHead title={title} date={pubDate} updatedDate={updatedDate} />',
		'<PostHead title={title} date={pubDate} />'],

	// The vendored CSS goes back to the ELEMENT separator - the exact
	// pre-fix library. Markup adopts, CSS does not: the dot strands
	// again at phone widths and nothing anywhere is red.
	['revert the vendored byline to the element separator',
		'src/styles/cli-mono/components.css',
		".cm-byline > *:not(:first-child)::before {\n	content: '·';\n	color: var(--ink-faint);\n	opacity: 0.6;",
		'.cm-byline__sep { opacity: 0.6; }\n.cm-byline > *:not(:first-child)::before { content: none;\n	color: var(--ink-faint);\n	opacity: 0.6;'],

	// The strip I added to the dead-CSS check must not blind it: a REAL
	// dead selector in a real style block still has to fail.
	['leave a genuinely dead selector in the layout style block',
		'src/layouts/BlogPost.astro',
		'	.hero-image { margin: 1rem 0 2rem; }',
		'	.hero-image { margin: 1rem 0 2rem; }\n	.the-real-dead-one { color: red; }'],
];

let killed = 0, missed = 0, noop = 0;
for (const [name, file, find, replace] of MUTANTS) {
	const p = join(root, file);
	const orig = readFileSync(p, 'utf8');
	if (!orig.includes(find)) {
		console.log(`  NO-OP   ${name}\n            !! pattern not found in ${file}; BROKEN mutation, not a pass`);
		noop++;
		continue;
	}
	writeFileSync(p, orig.replace(find, replace));
	const r = run();
	if (r.status !== 0) {
		const line = (r.stdout.match(/not ok \d+ - [^\n]*/g) || []).slice(0, 2).join(' | ');
		console.log(`  KILLED  ${name}\n            -> ${line}`);
		killed++;
	} else {
		console.log(`  MISSED  ${name}\n            !! suite stayed green; the test does not guard this`);
		missed++;
	}
	writeFileSync(p, orig);
}

const after = run();
console.log(`\n${killed} killed, ${missed} missed, ${noop} no-op`);
console.log(`suite after restore: ${after.status === 0 ? 'green' : 'RED'}`);
process.exit(missed || noop || after.status !== 0 ? 1 : 0);
