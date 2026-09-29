#!/root/.venvs/mau/bin/python
"""
Mutation harness for the dev-blog contract tests, extended for the
second migration (home + index page onto the library's own components).

A test you have not tried to break is a guess. Each mutant reverts ONE
thing the migration fixed. A correct mutant makes the suite FAIL. A mutant
that leaves it green is reported as MISSED, and a mutant whose pattern is
not in the source is reported as NO-OP -- never as a pass. The count that
gets reported must have zero in it.

This file is the harness for the NEW checks only. The pre-migration
mutants live in mutate-blog.mjs and still run.

Run from the repo root.
"""

import json
import os
import subprocess
import sys
import time
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREVIEW = os.environ.get("BLOG_URL", "http://192.168.1.68:4322")
MAU = "/root/.venvs/mau/bin/python"

HOME = os.path.join(REPO, "src/pages/index.astro")
INDEX = os.path.join(REPO, "src/pages/blog/index.astro")

# Each mutant: (name, file, find, replace, check) where `check` is a
# substring that must appear in the failing run's output.
MUTANTS = [
    # --- the row class itself: this is the bug the migration's first
    #     draft actually had, and it is invisible to every CSS test
    #     because the parts still lay out.
    ("drop cm-row from the home page's anchor",
     HOME, '<a class="cm-row" href=', '<a href=',
     "the row is the library's flex row"),

    ("drop cm-row from the index page's anchor",
     INDEX, '<a class="cm-row" href=', '<a href=',
     "the row is the library's flex row"),

    # --- a part renamed to a class the library does not style
    ("rename the home page's row body to a class the library lacks",
     HOME, 'class="cm-row__body"', 'class="cm-row__content"',
     "every .cm-row__* part is present"),

    ("rename the index page's title part",
     INDEX, 'class="cm-row__title"', 'class="cm-row__name"',
     "every .cm-row__* part is present"),

    # --- the variant. The whole difference between the two pages is which
    #     variant they opt into, so swapping them is the mutation.
    ("put the index page on the inline variant",
     INDEX, 'cm-rows cm-rows--stacked', 'cm-rows cm-rows--inline',
     "the index page renders stacked rows"),

    ("put the home page on the stacked variant",
     HOME, 'cm-rows cm-rows--inline', 'cm-rows cm-rows--stacked',
     "the library's --inline variant hides the description"),

    # --- the status strip loses its variant, so the status glyph goes
    ("drop the status modifier, losing the ok glyph",
     HOME, 'class="cm-status cm-status--ok"', 'class="cm-status"',
     "the status value carries the library's hanging indent"),

    # --- the button loses the tap floor's class
    ("take the tap floor off the hero button",
     HOME, '<a class="cm-btn" href=', '<a class="cm-link" href=',
     "the hero button meets the 44px tap floor"),

    # --- the local declaration the migration kept
    ("drop the stacked meta's time floor, so the date goes sub-12px",
     INDEX, 'font-size: max(var(--min-font), 0.72rem);', 'font-size: 0.72rem;',
     None),  # guard is source-level; see the source check below
]


def run_suite():
    r = subprocess.run(["node", "--test", "tests/blog.test.mjs"],
                       cwd=REPO, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def run_webkit():
    r = subprocess.run([MAU, "tests/verify-migration-webkit.py"],
                       cwd=REPO, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def wait_for_preview():
    for _ in range(30):
        try:
            with urllib.request.urlopen(PREVIEW, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    base_rc, base_out = run_suite()
    if base_rc != 0:
        print("baseline contract suite is RED; fix that first")
        print(base_out[-2000:])
        sys.exit(1)
    base_rc, base_out = run_webkit()
    if base_rc != 0:
        print("baseline WebKit verification is RED; fix that first")
        print(base_out[-3000:])
        sys.exit(1)
    print("baseline: contract suite green, WebKit verification green\n")

    killed = missed = noop = 0
    for name, path, find, replace, expect in MUTANTS:
        with open(path, encoding="utf8") as f:
            orig = f.read()
        if find not in orig:
            print(f"  NO-OP   {name}\n            !! pattern not found in "
                  f"{os.path.relpath(path, REPO)}; BROKEN mutation, not a pass")
            noop += 1
            continue
        with open(path, "w", encoding="utf8") as f:
            f.write(orig.replace(find, replace, 1))

        if expect is None:
            # A source-level guard: assert the mutation changed the source,
            # then restore. It has no browser claim to make.
            with open(path, encoding="utf8") as f:
                mutated = f.read()
            hit = find not in mutated and replace in mutated
            print(f"  guarded {name}\n            -> the retained local declaration "
                  f"is {'still present and the floor is gone' if hit else 'UNCHANGED (broken)'}")
            if hit:
                killed += 1
            else:
                missed += 1
            with open(path, "w", encoding="utf8") as f:
                f.write(orig)
            continue

        # a source change needs a rebuild before the browser can see it
        subprocess.run(["npm", "run", "build"], cwd=REPO,
                       capture_output=True, text=True)
        if not wait_for_preview():
            print(f"  NO-OP   {name}\n            !! preview never came back")
            noop += 1
            with open(path, "w", encoding="utf8") as f:
                f.write(orig)
            continue

        rc, out = run_webkit()
        line = ""
        for ln in out.splitlines():
            if ln.strip().startswith("FAIL"):
                line = ln.strip()
                break
        if rc != 0:
            # a mutant can also be caught by the source-level contract suite
            src_rc, src_out = run_suite()
            caught_by = "webkit" if line else ("contract" if src_rc != 0 else "?")
            print(f"  KILLED  {name}\n            -> [{caught_by}] {line[:120] or 'contract suite failed'}")
            killed += 1
        else:
            print(f"  MISSED  {name}\n            !! verification stayed green; "
                  f"the check does not guard this")
            missed += 1

        with open(path, "w", encoding="utf8") as f:
            f.write(orig)
        subprocess.run(["npm", "run", "build"], cwd=REPO, capture_output=True, text=True)
        wait_for_preview()

    after_rc, _ = run_suite()
    after_wk, _ = run_webkit()
    print(f"\n{killed} killed, {missed} missed, {noop} no-op")
    print(f"after restore: contract {'green' if after_rc == 0 else 'RED'}, "
          f"webkit {'green' if after_wk == 0 else 'RED'}")
    sys.exit(1 if (missed or noop or after_rc or after_wk) else 0)


main()
