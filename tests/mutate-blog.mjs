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
		'.footer-meta a:hover { color: var(--ink); }\n\t.never-used-thing { color: red; }'],
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
