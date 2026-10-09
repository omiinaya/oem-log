#!/root/.venvs/mau/bin/python
"""Mutation proof for the 2026-10-09 header migration (dev-blog -> oem-ui).

Each mutant asserts ONE claim a re-derived test makes. A test that has
never been broken is a guess, and the three tests rewritten this cycle are
exactly the shape that goes soft: they now assert the ABSENCE of the header
in the consumer file and the PRESENCE in the vendored copy, which is easy
to satisfy by accident.

Rules this harness obeys, learned the hard way in oem-ui:

  * SNAPSHOT to a scratch file BEFORE every mutation and restore with cp.
    `git checkout -- <file>` would revert the whole cycle's work, not just
    the mutation, and on a repo with concurrent runs it is how someone
    else's in-flight edit disappears.
  * PATTERN ABSENT is an ERROR, never a survival. Every pattern is
    pre-checked against the current file before it is applied; a miss
    exits non-zero so a drifted product edit cannot shrink the run while
    the summary still looks healthy.
  * Kill count and summary come from the SAME variable - the counter is
    incremented on the line that reports the kill.
  * The expected victim is NAMED per mutant. A mutation that fails a
    DIFFERENT test is not proof of the claim under test, so it is
    reported as MISATTRIBUTED and counted as a failure of the harness.

Run:  /root/.venvs/mau/bin/python tests/mutate-header-migration.py
      (build is NOT needed: none of these contracts read dist/)
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRATCH = Path(tempfile.mkdtemp(prefix='mutate-hdr-'))
TESTS = ['npm', 'test']

# (label, path relative to ROOT, find, replace, victim)
MUTANTS = [
    # ---- test 10: the consumer file writes none of the header ----
    ('the consumer file grows its own <header> again',
     'src/components/Header.astro',
     '<LibHeader',
     '<header class="cm-header" data-cm-header></header>\n<LibHeader',
     'the header is the library component, not a hand-rolled bar'),

    ('the consumer file grows a scoped stylesheet again',
     'src/components/Header.astro',
     '/>',
     '/>\n<style>\n\t.cm-header__link { padding: 0; }\n</style>',
     'the header is the library component, not a hand-rolled bar'),

    ('the wrapper stops rendering the library header',
     'src/components/Header.astro',
     "import LibHeader from '../astro/Header.astro';",
     "const LibHeader = (_props: unknown) => null;",
     'the header is the library component, not a hand-rolled bar'),

    # ---- test 4 (astro half): the vendored copy is byte-identical ----
    # Anchored on `data-cm-header`, which occurs once. `<header
    # class:list` does not occur at all: the two attributes are on
    # separate lines, and a pattern written from memory rather than from
    # the file is PATTERN ABSENT - reported as an error, not as a pass.
    ('the vendored library header drifts by one word',
     'src/astro/Header.astro',
     'data-cm-header',
     'data-cm-header data-mutated',
     'the vendored layers are byte-identical to the library'),

    ('a library component the consumer never got goes unnoticed',
     'src/astro/current.ts',
     'export const isCurrentPage',
     'export const isCurrentPage_RENAMED',
     'the vendored layers are byte-identical to the library'),

    # ---- test 11: one matcher, no third copy ----
    # Both patterns anchor on `label: 'notes', matchSegment: true }`, the
    # code, and not on the bare phrase: the frontmatter NAMES matchSegment
    # while explaining it, so `matchSegment: true` matches twice and the
    # pre-flight would (correctly) refuse it as ambiguous.
    ('the wrapper writes a per-page active boolean again',
     'src/components/Header.astro',
     "label: 'notes', matchSegment: true }",
     "label: 'notes', matchSegment: true, active: true }",
     'the current nav link is decided by the library, not by this project'),

    ('the notes link stops opting into the segment match',
     'src/components/Header.astro',
     "label: 'notes', matchSegment: true }",
     "label: 'notes', matchSegment: false }",
     'the current nav link is decided by the library, not by this project'),

    # Anchored on the page's config import, not on `---\n`: an Astro
    # file has TWO of those (frontmatter open and close), so the
    # pre-flight refused the pattern as ambiguous - correctly, because
    # replace(..., 1) would have landed the mutant in the wrong place.
    ('a private normaliser reappears in a page component',
     'src/pages/index.astro',
     "import { SITE } from '../astro/config';",
     "const strip = (p: string) => p;\nimport { SITE } from '../astro/config';",
     'the current nav link is decided by the library, not by this project'),

    ('the header stops calling the shared matcher',
     'src/astro/Header.astro',
     "import { isCurrentPage } from './current';",
     'const isCurrentPage = () => false;',
     'the current nav link is decided by the library, not by this project'),

    # ---- test 12: one config, this site's identity ----
    ('the second config comes back',
     'src/pages/index.astro',
     "import { SITE } from '../astro/config';",
     "export const SITE = { title: 'x' };\nimport { SITE } from '../astro/config';",
     'the site identity comes from one config, not three places'),

    ('the identity reverts to the library placeholder',
     'src/astro/config.ts',
     "title: 'oem/log',",
     "title: 'oem/ui',",
     'the site identity comes from one config, not three places'),

    ('the brand is a literal instead of the config',
     'src/components/Header.astro',
     'brand={SITE.title}',
     'brand="oem/log"',
     'the site identity comes from one config, not three places'),
]


def run_suite() -> tuple[bool, str, list[str]]:
    """Return (ok, transcript, failed test names)."""
    p = subprocess.run(TESTS, cwd=ROOT, capture_output=True, text=True, timeout=600)
    out = (p.stdout or '') + '\n' + (p.stderr or '')
    failed = [ln.split(' - ', 1)[1].strip()
              for ln in out.splitlines()
              if ln.startswith('not ok') and ' - ' in ln]
    return p.returncode == 0 and not failed, out, failed


def main() -> int:
    # Pre-flight: every pattern must match BEFORE anything is mutated.
    for label, rel, old, _new, _victim in MUTANTS:
        p = ROOT / rel
        if not p.is_file():
            print(f'PRE-FLIGHT FAIL: {rel} does not exist ({label})')
            return 2
        body = p.read_text()
        n = body.count(old)
        if n == 0:
            print(f'PATTERN ABSENT: {rel} has no {old!r} ({label})')
            return 2
        if n > 1:
            print(f'PATTERN AMBIGUOUS ({n}x): {rel} {old!r} ({label}) - the mutant '
                  f'would land in the wrong place')
            return 2

    base_ok, base_out, base_victim = run_suite()
    print(f'baseline suite {"green" if base_ok else "RED"}')
    if not base_ok:
        print(base_out[-4000:])
        print('ABORT: the baseline is not green; a mutation run would measure nothing')
        return 3

    killed = survived = misattr = 0
    error = None
    for label, rel, old, new, victim in MUTANTS:
        p = ROOT / rel
        snap = SCRATCH / (rel.replace('/', '__') + '.bak')
        if not snap.exists():
            snap.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, snap)
        original = p.read_text()
        outcome = None
        detail = ''
        try:
            p.write_text(original.replace(old, new, 1))
            if new not in p.read_text():
                outcome, detail = 'ERROR', 'mutation did not land'
            else:
                ok, out, fails = run_suite()
                if ok:
                    outcome = 'SURVIVED'
                elif victim not in out:
                    outcome, detail = 'MISATTRIBUTED', f'failed {fails!r}, expected {victim!r}'
                else:
                    outcome = 'killed'
        except Exception as exc:  # noqa: BLE001 - a crash must not read as a survival
            outcome, detail = 'ERROR', f'{type(exc).__name__}: {exc}'
        finally:
            shutil.copy2(snap, p)
            restored = p.read_text() == original
        if not restored:
            print(f'  ERROR    {label}: restore did not return the original bytes')
            return 5

        if outcome == 'killed':
            killed += 1
            print(f'  killed   {label}')
        elif outcome == 'SURVIVED':
            survived += 1
            print(f'  SURVIVED {label}')
        elif outcome == 'MISATTRIBUTED':
            misattr += 1
            print(f'  MISATTRIBUTED {label}: {detail}')
        else:
            error = f'{label}: {detail}'
            print(f'  ERROR    {error}')
            break
    if error:
        return 4

    print(f'\n{killed} killed, {survived} survived, {misattr} misattributed '
          f'of {len(MUTANTS)} mutants')
    return 0 if (killed == len(MUTANTS) and survived == 0 and misattr == 0) else 1


if __name__ == '__main__':
    sys.exit(main())
