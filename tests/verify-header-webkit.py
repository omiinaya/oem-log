#!/root/.venvs/mau/bin/python
"""
Prove the oem-log header, in the engine Omar actually uses.

Before the migration this project's header was 170 lines of scoped CSS
and a hand-rolled markup tree. Measured in WebKit at 390x844 it was
121px tall - the nav had wrapped onto a SECOND ROW - and its theme
toggle measured 32x44: base.css gives every button min-height:var(--tap)
and the hand-rolled toggle declared only width and height, so 44px of
floor stretched a 32px box into a pill that is too narrow to hit.

That is the bug the library had already fixed, in a file this project
vendors. The nav links were bare <a> with no .cm-header__link class at
all, so the runtime's scroll-spy and the library's own
[aria-current=page] rule could not see them.

Run from the repo root with the preview already serving:

    /root/.venvs/mau/bin/python tests/verify-header-webkit.py
"""

import asyncio
import os
import sys

from playwright.async_api import async_playwright

BASE = os.environ.get("BLOG_URL", "http://192.168.1.68:4322")

# Every page carries the same header, and WHICH link is current differs
# per page. That difference is the whole point of the migration: the
# current-page state used to be hand-computed in four places.
PAGES = [
    ("/", "home"),
    ("/blog/", "notes"),
    ("/about/", "about"),
    ("/blog/", "notes"),
]

failures = []


def check(ok, label, detail=""):
    print(("  ok   " if ok else "  FAIL ") + label + (("  " + detail) if detail else ""))
    if not ok:
        failures.append(label + ("  " + detail if detail else ""))


# One read of the header, taken from the DOM rather than from the source:
# the claim under test is about LAYOUT and STATE, both of which a source
# assertion cannot see.
PROBE = r"""() => {
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      w: Math.round(r.width), h: Math.round(r.height),
      top: Math.round(r.top), left: Math.round(r.left),
      display: cs.display, position: cs.position,
      fontWeight: cs.fontWeight, textDecoration: cs.textDecorationLine,
    };
  };
  const header = document.querySelector('header');
  const links = [...document.querySelectorAll('header a')];
  const toggle = document.querySelector('[data-cm-theme-toggle], .theme-toggle');
  const brand = document.querySelector('.cm-header__brand, .brand');
  const navlinks = [...document.querySelectorAll('.cm-header__link')];
  const out = {
    header: box(header),
    brand: box(brand),
    toggle: box(toggle),
    // Every anchor in the header, so a link that lost its class is visible
    // as a link with no cm-header__link rather than as a silent pass.
    anchors: links.map((a) => ({
      text: (a.textContent || '').trim().slice(0, 20),
      cls: a.className,
      isNavLink: a.classList.contains('cm-header__link'),
      cur: a.getAttribute('aria-current'),
      h: Math.round(a.getBoundingClientRect().height),
      w: Math.round(a.getBoundingClientRect().width),
      weight: getComputedStyle(a).fontWeight,
      deco: getComputedStyle(a).textDecorationLine,
    })),
    navLinkCount: navlinks.length,
    // A WRAPPED header is a second row of children at a different top.
    // Counted as distinct top edges of the header's VISIBLE children only:
    // a collapsed drawer keeps its links in the DOM at height 0, and those
    // all report top 0, which is a phantom "row" that is not a layout at
    // all. Scoping to the header, and dropping the zero-height children,
    // is what makes the count mean "rows the reader can see".
    rowCount: header
      ? new Set([...header.querySelectorAll('a,button')]
          .filter((e) => e.getBoundingClientRect().height > 0)
          .map((e) => Math.round(e.getBoundingClientRect().top))).size
      : 0,
    docW: document.documentElement.scrollWidth,
    clientW: document.documentElement.clientWidth,
  };
  const cs = header ? getComputedStyle(header) : null;
  out.headerSticky = cs ? (cs.position === 'sticky' || cs.position === 'fixed') : false;
  return out;
}"""


async def main():
    async with async_playwright() as p:
        browser = await p.webkit.launch()

        # Three phone heights on purpose. The header used to WRAP into a
        # second row, and a wrap is a function of the available WIDTH -
        # but the column-wrap drawer bug in this library was triggered by
        # HEIGHT, so sweeping height is the cheap half of the insurance.
        for label, (vw, vh) in [
            ("iPhone 12/13/14 390x844", (390, 844)),
            ("iPhone SE 375x667", (375, 667)),
            ("small phone 320x568", (320, 568)),
        ]:
            ctx = await browser.new_context(
                viewport={"width": vw, "height": vh},
                device_scale_factor=3, is_mobile=True, has_touch=True,
            )
            page = await ctx.new_page()
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            print(label)
            for path, _ in PAGES:
                await page.goto(BASE + path, wait_until="networkidle")
                d = await page.evaluate(PROBE)
                check(d["headerSticky"], path + ": the header is sticky",
                      "position=" + str((d["header"] or {}).get("position")))
                # The whole defect: a second ROW of nav inside a header
                # that was meant to be one line.
                check(d["rowCount"] == 1, path + ": the header is ONE row, not a wrapped second row",
                      "distinct child top edges=" + str(d["rowCount"]))
                check(d["navLinkCount"] > 0, path + ": the nav links carry the library's .cm-header__link",
                      "found " + str(d["navLinkCount"]))
                if d["toggle"]:
                    check(d["toggle"]["w"] == d["toggle"]["h"],
                          path + ": the theme toggle is SQUARE, not a 44-tall pill",
                          "%dx%d" % (d["toggle"]["w"], d["toggle"]["h"]))
                    check(d["toggle"]["h"] >= 44, path + ": the theme toggle meets the 44px tap floor",
                          "h=%d" % d["toggle"]["h"])
                else:
                    check(False, path + ": a theme toggle exists", "none found")
                # Every nav link is a tap target. A link inside the header
                # that is under the floor is a link a thumb misses.
                short = [a["text"] for a in d["anchors"] if a["h"] < 44 and a["w"] > 0]
                check(not short, path + ": every header link meets the tap floor",
                      "under 44px: " + str(short) if short else "")
                check(d["docW"] <= d["clientW"], path + ": no sideways scroll",
                      "scrollWidth %d vs clientWidth %d" % (d["docW"], d["clientW"]))
            check(not errors, label + ": no console errors", "; ".join(errors[:2]))
            await page.screenshot(path="/tmp/blog-header-%d.png" % vw, full_page=False)
            await ctx.close()

        # ---------- the current-page state, per page ----------
        # This is the part four hand-written components used to get wrong
        # independently, and the part the library's HeaderLink owns.
        print("current-page state")
        ctx = await browser.new_context(
            viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
        )
        page = await ctx.new_page()
        for path, want in PAGES:
            await page.goto(BASE + path, wait_until="networkidle")
            d = await page.evaluate(PROBE)
            current = [a for a in d["anchors"] if a["cur"] == "page"]
            check(len(current) == 1, path + ": exactly one link is aria-current",
                  "found " + str([a["text"] for a in current]))
            if len(current) == 1:
                a = current[0]
                check(a["text"].lower().startswith(want),
                      path + ": the current link is " + want,
                      "got " + repr(a["text"]))
                # Not just the attribute: the library must make it LOOK
                # current, or the state is invisible to a reader.
                #
                # Only asserted when the link is actually RENDERED. At a
                # phone width the nav is a closed drawer, so the current
                # link measures 0x0 and no rule with a text-decoration
                # matches it - the computed value is the base rule's
                # `none`, which says nothing about how the state looks
                # when the reader can see it. Measuring a hidden element
                # and reporting the base value as a missing style is the
                # "probe asserts the wrong thing" failure this repo keeps
                # paying for; the desktop pass below is where the claim
                # is actually true.
                if a["w"] > 0 and a["h"] > 0:
                    check(a["weight"] == "700", path + ": the current link is bold",
                          "font-weight=" + a["weight"])
                    check("underline" in a["deco"], path + ": the current link is underlined",
                          "text-decoration=" + a["deco"])
                else:
                    print("  skip %s: the current link is inside the closed drawer "
                          "(0x0); its appearance is asserted at desktop width" % path)
        await ctx.close()

        # ---------- the current link's APPEARANCE, where it is visible ----------
        # The phone pass cannot make this claim: the nav is a closed
        # drawer there, so the current link is 0x0. At desktop width the
        # nav is a row and the state is visible, which is where "the
        # library makes the current page LOOK current" is a real claim.
        print("current-page appearance at 1280x900")
        dctx = await browser.new_context(viewport={"width": 1280, "height": 900})
        dpage = await dctx.new_page()
        for path, want in PAGES:
            await dpage.goto(BASE + path, wait_until="networkidle")
            d = await dpage.evaluate(PROBE)
            check(d["headerSticky"], path + "@1280: the header is sticky")
            current = [a for a in d["anchors"] if a["cur"] == "page"]
            check(len(current) == 1, path + "@1280: exactly one link is aria-current",
                  "found " + str([a["text"] for a in current]))
            if len(current) == 1:
                a = current[0]
                check(a["w"] > 0 and a["h"] > 0, path + "@1280: the current link is rendered",
                      "%dx%d" % (a["w"], a["h"]))
                check(a["weight"] == "700", path + "@1280: the current link is bold",
                      "font-weight=" + a["weight"])
                check("underline" in a["deco"], path + "@1280: the current link is underlined",
                      "text-decoration=" + a["deco"])
        await dctx.close()

        # ---------- the drawer: the header's own runtime capability ----------
        # Only rendered when there is a nav to disclose. Without this the
        # migration could pass while shipping a header whose phone nav is
        # unreachable behind a bar.
        print("phone drawer")
        ctx = await browser.new_context(
            viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
        )
        page = await ctx.new_page()
        await page.goto(BASE + "/", wait_until="networkidle")
        burger = await page.evaluate(r"""() => {
            const b = document.querySelector('[data-cm-nav-toggle]');
            if (!b) return { exists: false };
            const r = b.getBoundingClientRect();
            const cs = getComputedStyle(b);
            return { exists: true, display: cs.display, w: Math.round(r.width),
                     h: Math.round(r.height), expanded: b.getAttribute('aria-expanded') };
        }""")
        check(burger["exists"], "a menu button exists for the phone nav")
        if burger["exists"]:
            check(burger["display"] != "none", "the menu button is visible on a phone",
                  "display=" + burger["display"])
            check(burger["w"] >= 44 and burger["h"] >= 44,
                  "the menu button meets the tap floor",
                  "%dx%d" % (burger["w"], burger["h"]))
            # Click it at its own coordinates. page.click() scrolls its
            # target into view as part of actionability, which moves the
            # document; a real tap does not.
            box = await page.evaluate(r"""() => {
                const r = document.querySelector('[data-cm-nav-toggle]').getBoundingClientRect();
                return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
            }""")
            await page.mouse.click(box["x"], box["y"])
            await page.wait_for_timeout(250)
            opened = await page.evaluate(r"""() => {
                const b = document.querySelector('[data-cm-nav-toggle]');
                const panel = document.getElementById('cm-header-links');
                if (!panel) return { panel: false };
                const r = panel.getBoundingClientRect();
                return { panel: true, expanded: b.getAttribute('aria-expanded'),
                         visible: r.width > 0 && r.height > 0,
                         w: Math.round(r.width), h: Math.round(r.height) };
            }""")
            check(opened.get("panel"), "the drawer panel is in the DOM")
            check(opened.get("expanded") == "true", "the button reports the drawer open",
                  "aria-expanded=" + str(opened.get("expanded")))
            check(opened.get("visible"), "the drawer is actually visible",
                  "%sx%s" % (opened.get("w"), opened.get("h")))

            # The scrim, asserted because a vision model reported the live
            # drawer's background as "still live, no dim overlay" and it
            # was wrong: the scrim exists, is rgba(0,0,0,0.55) at full
            # opacity with pointer-events:auto, and is simply
            # imperceptible over near-black content at that contrast. A
            # claim about a scrim is a claim about GEOMETRY AND STATE, so
            # it is measured, not eyeballed.
            scrim = await page.evaluate(r"""() => {
                const s = document.querySelector('[data-cm-nav-scrim]');
                if (!s) return null;
                const cs = getComputedStyle(s);
                const r = s.getBoundingClientRect();
                return { bg: cs.backgroundColor, opacity: cs.opacity,
                         pe: cs.pointerEvents, z: cs.zIndex,
                         coversViewport: Math.round(r.width) >= window.innerWidth
                                         && Math.round(r.height) >= window.innerHeight };
            }""")
            check(scrim is not None, "the runtime created a scrim for the drawer")
            if scrim:
                check(float(scrim["opacity"]) > 0.9, "the scrim is opaque while the drawer is open",
                      "opacity=%s" % scrim["opacity"])
                check(scrim["pe"] != "none", "the scrim swallows taps behind the drawer",
                      "pointer-events=%s" % scrim["pe"])
                check(scrim["coversViewport"], "the scrim covers the viewport")
                check("rgba(0" in scrim["bg"] or scrim["bg"].startswith("rgb(0"),
                      "the scrim is a dark wash, not a colour that hides nothing",
                      "background=%s" % scrim["bg"])
            # And the header must still be pinned WITH it open - the
            # regression this library's drawer shipped once.
            #
            # Scrolled to the REAL maximum, not a hardcoded offset:
            # scrollTo clamps, and on a page with only 353px of scroll a
            # request for 600 lands at 0, so the header is never given a
            # chance to move and the check passes for the wrong reason.
            # Assert that the document ACTUALLY moved before asserting it
            # stayed put - otherwise "the page did not scroll" reads as
            # "the header is pinned".
            pinned = await page.evaluate(r"""async () => {
                const max = document.documentElement.scrollHeight - window.innerHeight;
                window.scrollTo(0, max);
                await new Promise(r => setTimeout(r, 250));
                const h = document.querySelector('header').getBoundingClientRect();
                return { top: Math.round(h.top), y: Math.round(window.scrollY), max: Math.round(max) };
            }""")
            check(pinned["max"] > 0, "the page has enough scroll to move the header",
                  "max scroll=%d" % pinned["max"])
            check(pinned["y"] > 0, "the document actually scrolled",
                  "scrollY=%d of max %d" % (pinned["y"], pinned["max"]))
            check(pinned["top"] == 0,
                  "the header stays pinned with the drawer open",
                  "scrollY=%d headerTop=%d" % (pinned["y"], pinned["top"]))
        await page.screenshot(path="/tmp/blog-drawer-390.png", full_page=False)
        await ctx.close()
        await browser.close()

    print()
    if failures:
        print("FAILED: %d" % len(failures))
        for f in failures:
            print("  - " + f)
        sys.exit(1)
    print("all checks passed in WebKit")


asyncio.run(main())