#!/root/.venvs/mau/bin/python
"""
Mutation harness for the HEADER migration.

The header had the last second-implementation design system left in this
project, and it shipped with two measured layout defects. Four tests now
guard that migration - and a test you have not tried to break is a guess.

Each mutant below reverts ONE thing the migration fixed, then runs BOTH
gates:

  * the contract suite (node --test tests/blog.test.mjs)
  * the WebKit proof (tests/verify-header-webkit.py)

and requires the gates to go RED. A mutant that leaves them green is
MISSED - the check does not guard that - and a mutant whose pattern is
absent from the source is a NO-OP, which is a broken harness and never a
pass. Both are failures here.

Run from the repo root, with the preview already serving:

    /root/.venvs/mau/bin/python tests/mutate-header.py
"""

import os
import subprocess
import sys
import time
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREVIEW = os.environ.get("BLOG_URL", "http://192.168.1.68:4322")
MAU = "/root/.venvs/mau/bin/python"

HDR = os.path.join(REPO, "src/components/Header.astro")

# (name, file, find, replace)
MUTANTS = [
    # --- the markup stops being the library's ---
    (
        "drop .cm-header from the bar",
        HDR,
        "class:list={['cm-header', allLinks.length > 0 && 'cm-header--nav']}",
        "class:list={['not-the-library-header']}",
    ),
    (
        "drop .cm-header__brand from the brand link",
        HDR,
        'class="cm-header__brand"',
        'class="brand"',
    ),
    (
        "drop .cm-header__links from the nav wrapper",
        HDR,
        'class="cm-header__links"',
        'class="links"',
    ),
    (
        "drop .cm-icon-btn from the theme toggle",
        HDR,
        'class="cm-icon-btn"',
        'class="theme-toggle"',
    ),
    (
        "drop the data-cm-header hook the runtime binds to",
        HDR,
        "\tdata-cm-header\n",
        "\n",
    ),
    # --- the hand-rolled stylesheet comes back ---
    (
        "re-declare the sticky bar in a scoped block",
        HDR,
        "@media (min-width: 641px) and (max-width: 999px) {",
        ".header { position: static; top: auto; }\n\t@media (min-width: 641px) and (max-width: 999px) {",
    ),
    # --- the current-page decision goes back to this project ---
    (
        "stop using the library's HeaderLink",
        HDR,
        "<HeaderLink",
        '<a class="cm-header__link nav-active"',
    ),
    (
        "import HeaderLink but never render it",
        HDR,
        "<HeaderLink",
        '<a class="cm-header__link"',
    ),
    # --- identity goes back to inline markup ---
    # The literal lives in a PAGE, not in the header: that is where the
    # blog put it before, and it is the shape the contract test forbids.
    (
        "hardcode the repo URL in the header call",
        os.path.join(REPO, "src/pages/index.astro"),
        "extraLinks={[{ href: SITE.github, label: 'github' }]}",
        "extraLinks={[{ href: 'https://github.com/omiinaya/oem-log', label: 'github' }]}",
    ),
]


def run_suite():
    r = subprocess.run(
        ["node", "--test", "tests/blog.test.mjs"],
        cwd=REPO, capture_output=True, text=True,
    )
    return r.returncode, r.stdout + r.stderr


def run_webkit():
    r = subprocess.run(
        [MAU, "tests/verify-header-webkit.py"],
        cwd=REPO, capture_output=True, text=True,
    )
    return r.returncode, r.stdout + r.stderr


def wait_for_preview():
    for _ in range(40):
        try:
            with urllib.request.urlopen(PREVIEW, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    if not wait_for_preview():
        print("preview is not serving at %s; start it before running this" % PREVIEW)
        sys.exit(1)

    base_rc, base_out = run_suite()
    if base_rc != 0:
        print("baseline contract suite is RED; fix that first")
        print(base_out[-2500:])
        sys.exit(1)
    base_rc, base_out = run_webkit()
    if base_rc != 0:
        print("baseline WebKit verification is RED; fix that first")
        print(base_out[-3000:])
        sys.exit(1)
    print("baseline: contract suite green, WebKit verification green\n")

    killed = missed = noop = 0
    for name, path, find, replace in MUTANTS:
        with open(path, encoding="utf8") as f:
            orig = f.read()
        if find not in orig:
            print("  NO-OP   %s\n            !! pattern not in %s; BROKEN mutation"
                  % (name, os.path.relpath(path, REPO)))
            noop += 1
            continue
        with open(path, "w", encoding="utf8") as f:
            f.write(orig.replace(find, replace, 1))

        build = subprocess.run(["npm", "run", "build"], cwd=REPO,
                               capture_output=True, text=True)
        if not wait_for_preview():
            # A mutation that does not COMPILE has still been caught, and
            # by the strongest gate available: the build refuses it. Treat
            # it as a kill with the compiler's own message.
            #
            # Reporting NO-OP here was wrong twice over - it hid a real
            # kill behind "the preview never came back", and it taught me
            # to read a green line as a pass when the mutation had in fact
            # been rejected outright. A harness that cannot tell "the
            # mutation broke the build" from "the mutation was not
            # applied" is not measuring the test at all.
            if build.returncode != 0:
                err = ""
                for ln in (build.stdout + build.stderr).splitlines():
                    if "ERROR" in ln or "error" in ln:
                        err = ln.strip()
                        break
                print("  KILLED  %s\n            -> [build] %s" % (name, err[:140]))
                killed += 1
            else:
                print("  NO-OP   %s\n            !! the build passed but the preview "
                      "never came back" % name)
                noop += 1
            with open(path, "w", encoding="utf8") as f:
                f.write(orig)
            subprocess.run(["npm", "run", "build"], cwd=REPO, capture_output=True, text=True)
            wait_for_preview()
            continue

        wk_rc, wk_out = run_webkit()
        src_rc, src_out = run_suite()
        if wk_rc == 0 and src_rc == 0:
            print("  MISSED  %s\n            !! both gates stayed GREEN; the check "
                  "does not guard this" % name)
            missed += 1
        else:
            by = []
            detail = ""
            if src_rc != 0:
                by.append("contract")
            if wk_rc != 0:
                for ln in wk_out.splitlines():
                    if ln.strip().startswith("FAIL"):
                        detail = ln.strip()
                        break
                by.append("webkit")
            print("  KILLED  %s\n            -> [%s] %s"
                  % (name, "+".join(by), detail[:140]))
            killed += 1

        with open(path, "w", encoding="utf8") as f:
            f.write(orig)
        subprocess.run(["npm", "run", "build"], cwd=REPO, capture_output=True, text=True)
        wait_for_preview()

    after_rc, _ = run_suite()
    after_wk, _ = run_webkit()
    print("\n%d killed, %d missed, %d no-op" % (killed, missed, noop))
    print("after restore: contract %s, webkit %s"
          % ("green" if after_rc == 0 else "RED",
             "green" if after_wk == 0 else "RED"))
    sys.exit(1 if (missed or noop or after_rc or after_wk) else 0)


main()