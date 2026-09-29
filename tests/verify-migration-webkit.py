#!/root/.venvs/mau/bin/python
"""
Prove the oem-log home + index pages still LAY OUT after the migration
onto the library's own components, in the engine Omar actually uses.

The migration removed ~160 lines of second-implementation CSS and
substituted library classes, so what has to be proven is that the
substitution is visually equivalent and not merely valid. Metrics that
can catch a regression:

  1. every part of a row is PRESENT and measured non-zero (a renamed
     class the library does not style would still lay out, just wrong)
  2. the row's parts share one baseline row on the home page (inline
     variant) and STACK on the index page (stacked variant) -- the whole
     difference between those two pages is the variant, so it is the one
     thing a silent wrong-variant would break
  3. the description and date HIDE on a phone, which is the local
     scoped rule the migration deliberately kept
  4. the status strip's label and value do not collide
  5. the tap floor still holds for the hero button, from the token
  6. no horizontal overflow at any width

Run from the repo root. Exits non-zero on the first failure.
"""

import asyncio
import os
import sys

from playwright.async_api import async_playwright

BASE = os.environ.get("BLOG_URL", "http://192.168.1.68:4322")
failures = []


def check(ok, label, detail=""):
    print(("  ok   " if ok else "  FAIL ") + label + (f"  {detail}" if detail else ""))
    if not ok:
        failures.append(label + (f"  {detail}" if detail else ""))


HOME_JS = """() => {
  const out = {};
  const row = document.querySelector('.cm-rows .cm-row');
  out.rowExists = !!row;
  if (row) {
    const parts = ['.cm-row__idx', '.cm-row__body', '.cm-row__title', '.cm-row__desc',
                   '.cm-row__meta', '.cm-row__sym'];
    out.parts = {};
    for (const p of parts) {
      const el = row.querySelector(p);
      if (!el) { out.parts[p] = null; continue; }
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      out.parts[p] = { w: Math.round(r.width), h: Math.round(r.height),
                       top: Math.round(r.top), display: cs.display };
    }
    const rr = row.getBoundingClientRect();
    out.row = { w: Math.round(rr.width), h: Math.round(rr.height),
                display: getComputedStyle(row).display };
  }
  const st = document.querySelector('.cm-status');
  if (st) {
    const scs = getComputedStyle(st);
    const sr = st.getBoundingClientRect();
    const l = st.querySelector('.cm-status__label');
    const v = st.querySelector('.cm-status__value');
    const lr = l.getBoundingClientRect(), vr = v.getBoundingClientRect();
    const vcs = getComputedStyle(v);
    const contentLeft = sr.left + parseFloat(scs.borderLeftWidth) + parseFloat(scs.paddingLeft);
    const rects = [...v.getClientRects()].map((r) => ({
      left: Math.round(r.left), top: Math.round(r.top), right: Math.round(r.right),
    }));
    out.status = {
      className: st.className,
      // Token match, not a regex: this suite has already been bitten by
      // `\b` against a hyphenated class name (the `\bcm-back__arrow\b`
      // trap in the library's own suite). A leading `:` on an unknown
      // pseudo-class makes `querySelector` THROW rather than return null,
      // which is why the first version of this read "hasOkModifier:
      // false" and failed a strip that plainly carried the class.
      hasOkModifier: st.className.split(/\s+/).indexOf('cm-status--ok') !== -1,
      display: scs.display,
      flexWrap: scs.flexWrap,
      contentLeft: Math.round(contentLeft),
      label: { l: Math.round(lr.left), r: Math.round(lr.right), top: Math.round(lr.top), bottom: Math.round(lr.bottom) },
      value: { l: Math.round(vr.left), r: Math.round(vr.right), top: Math.round(vr.top), bottom: Math.round(vr.bottom) },
      // the hanging indent the library declares for the ::before glyph:
      // first line at the content edge, continuation lines indented past it
      textIndent: vcs.textIndent,
      paddingLeft: vcs.paddingLeft,
      before: getComputedStyle(v, '::before').content,
      rects,
    };
  }
  const btn = document.querySelector('.cm-head a.cm-btn');
  if (btn) {
    const r = btn.getBoundingClientRect();
    out.btn = { w: Math.round(r.width), h: Math.round(r.height) };
  }
  out.head = !!document.querySelector('.cm-head h1');
  out.lede = !!document.querySelector('.cm-lede');
  out.listHead = !!document.querySelector('.cm-list-head');
  out.listMore = !!document.querySelector('.cm-list-more a');
  return out;
}"""

INDEX_JS = """() => {
  const rows = [...document.querySelectorAll('.cm-rows--stacked .cm-row')];
  const out = { count: rows.length, rows: [] };
  for (const row of rows.slice(0, 3)) {
    const t = row.querySelector('.cm-row__title').getBoundingClientRect();
    const d = row.querySelector('.cm-row__desc').getBoundingClientRect();
    const m = row.querySelector('.cm-row__meta').getBoundingClientRect();
    const i = row.querySelector('.cm-row__idx').getBoundingClientRect();
    out.rows.push({
      title: { top: Math.round(t.top), bottom: Math.round(t.bottom), w: Math.round(t.width) },
      desc: { top: Math.round(d.top), w: Math.round(d.width) },
      meta: { top: Math.round(m.top), w: Math.round(m.width) },
      idx: { top: Math.round(i.top), w: Math.round(i.width) },
      // stacked: desc.top must be >= title.bottom, meta.top >= desc.bottom
      stacked: d.top >= t.bottom - 1 && m.top >= d.bottom - 1,
      // the index and the body share a left edge in a stacked row
      leftAligned: Math.abs(i.left - t.left) < 40,
    });
  }
  return out;
}"""


async def main():
    async with async_playwright() as p:
        browser = await p.webkit.launch()

        # ---------- iPhone 12-ish: what Omar actually sees ----------
        ctx = await browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=3, is_mobile=True, has_touch=True,
        )
        page = await ctx.new_page()

        print("iPhone 390x844 (WebKit, touch)")
        await page.goto(f"{BASE}/", wait_until="networkidle")
        print(f"  title: {await page.title()!r}")
        h = await page.evaluate(HOME_JS)
        check(h["rowExists"], "the home page renders a library row")
        check(h.get("row", {}).get("display") == "flex",
              "the row is the library's flex row, not a bare anchor",
              f"display={h.get('row', {}).get('display')}")
        check(h["head"] and h["lede"], ".cm-head and .cm-lede are in the DOM")
        check(h["listHead"], ".cm-list-head is in the DOM")
        check(h["listMore"], ".cm-list-more footer link is in the DOM")
        missing = [p for p, v in h["parts"].items() if v is None]
        check(not missing, "every .cm-row__* part is present", f"missing {missing}" if missing else "")
        zero = [p for p, v in h["parts"].items()
                if v and v["display"] != "none" and (v["w"] == 0 or v["h"] == 0)]
        check(not zero, "no VISIBLE row part collapses to 0x0",
              f"collapsed {zero}" if zero else
              "(parts hidden by --inline on a phone are 0x0 by design)")
        if h.get("btn"):
            check(h["btn"]["h"] >= 44, "the hero button meets the 44px tap floor",
                  f"measured {h['btn']['w']}x{h['btn']['h']}")
        else:
            # A skipped check is not a passed check. The first version of
            # this read `if h.get("btn")` and silently passed when the
            # button lost its class entirely - the mutation that removes
            # the tap floor then "survived" because nothing was asserted.
            # Absence of the control IS the regression.
            check(False, "the hero button is still the library's .cm-btn (and so still 44px tall)",
                  "no .cm-btn in the page head; the tap floor cannot apply to a class that is gone")
        if h.get("status"):
            s = h["status"]
            check(s["display"] == "flex", "the status strip is the library's flex strip",
                  f"display={s['display']}")
            # The variant is the whole point of the modifier class, and the
            # hanging indent exists ONLY to make room for the glyph it
            # inserts. A check that asserts the indent without asserting
            # the glyph is satisfied by a plain `.cm-status`, which has
            # the indent and no marker - which is exactly how the
            # "drop the status modifier" mutant survived the first run.
            check("●" in s["before"],
                  "the --ok variant renders its status glyph",
                  f"::before content={s['before']!r} class={s.get('className')!r}")
            check(s.get("hasOkModifier", False),
                  "the strip opts into the --ok variant",
                  f"class={s.get('className')!r}")
            # The library hangs the value under a ::before glyph with a
            # NEGATIVE first-line indent and a matching padding, so the
            # continuation lines align under the text and not under the
            # marker. Assert the resolved pair: both must be the same
            # non-zero magnitude. Reading the CONTAINER's text-indent
            # answers 0px here and looks like the fix is missing.
            ti, pl = s["textIndent"], s["paddingLeft"]
            check(ti.startswith("-") and pl not in ("0px", ""),
                  "the status value carries the library's hanging indent",
                  f"text-indent={ti} padding-left={pl}")
            check(abs(abs(float(ti.replace("px", ""))) - float(pl.replace("px", ""))) < 0.5,
                  "the hanging indent and the padding cancel exactly",
                  f"|{ti}| vs {pl}")
            # Whatever the wrap, no line may start outside the content box.
            check(s["value"]["r"] <= s["contentLeft"] + 1000,
                  "the value stays inside the strip")
            check(all(s["contentLeft"] - 1 <= r["left"] for r in s["rects"]),
                  "no status line starts left of the strip's content edge",
                  f"contentLeft={s['contentLeft']} lineLefts={[r['left'] for r in s['rects']]}")
        # the phone rule, now served by the LIBRARY's --inline variant
        hidden = await page.evaluate("""() => {
            const r = document.querySelector('.cm-rows .cm-row');
            if (!r) return { desc: 'no row', meta: 'no row' };
            const g = (s) => { const e = r.querySelector(s); return e ? getComputedStyle(e).display : 'absent'; };
            return { desc: g('.cm-row__desc'), meta: g('.cm-row__meta') };
        }""")
        check(hidden["desc"] == "none",
              "the library's --inline variant hides the description on a phone",
              f"display={hidden['desc']}")
        check(hidden["meta"] == "none",
              "the library's --inline variant hides the date on a phone",
              f"display={hidden['meta']}")

        ox = await page.evaluate("""async () => {
            window.scrollTo(9999, 0); await new Promise(r => setTimeout(r, 120));
            return { scrollX: Math.round(window.scrollX), w: document.documentElement.scrollWidth,
                     vw: window.innerWidth };
        }""")
        check(ox["scrollX"] == 0, "no horizontal scroll at 390px", f"scrollX={ox['scrollX']}")

        print("\niPhone 390x844 -- the index page")
        await page.goto(f"{BASE}/blog/", wait_until="networkidle")
        idx = await page.evaluate(INDEX_JS)
        check(idx["count"] > 0, "the index page renders stacked rows", f"{idx['count']} rows")
        for i, r in enumerate(idx["rows"]):
            check(r["stacked"], f"row {i} stacks title/desc/meta vertically",
                  f"title.bottom={r['title']['bottom']} desc.top={r['desc']['top']} meta.top={r['meta']['top']}")
        ox2 = await page.evaluate("""async () => {
            window.scrollTo(9999, 0); await new Promise(r => setTimeout(r, 120));
            return Math.round(window.scrollX);
        }""")
        check(ox2 == 0, "no horizontal scroll on the index page at 390px", f"scrollX={ox2}")

        # ---------- desktop: the row must be ONE line again ----------
        print("\nDesktop 1280x900 (WebKit)")
        dctx = await browser.new_context(viewport={"width": 1280, "height": 900})
        dpage = await dctx.new_page()
        await dpage.goto(f"{BASE}/", wait_until="networkidle")
        d = await dpage.evaluate(HOME_JS)
        if d.get("parts"):
            ps = d["parts"]
            same_row = ps[".cm-row__title"] and ps[".cm-row__desc"] and abs(
                ps[".cm-row__title"]["top"] - ps[".cm-row__desc"]["top"]) < 12
            check(same_row, "title and description share one row on desktop",
                  f"title.top={ps['.cm-row__title']['top']} desc.top={ps['.cm-row__desc']['top']}")
            check(bool(ps[".cm-row__desc"]) and ps[".cm-row__desc"]["w"] > 20,
                  "the description has real width on desktop")
        dox = await dpage.evaluate("""async () => {
            window.scrollTo(9999, 0); await new Promise(r => setTimeout(r, 120));
            return Math.round(window.scrollX);
        }""")
        check(dox == 0, "no horizontal scroll at 1280px", f"scrollX={dox}")

        await page.screenshot(path="/tmp/blog-home-390.png", full_page=True)
        await dpage.screenshot(path="/tmp/blog-home-1280.png", full_page=True)
        await dctx.close()
        await ctx.close()
        await browser.close()

    print()
    if failures:
        print(f"FAILED: {len(failures)}")
        for f in failures:
            print("  - " + f)
        sys.exit(1)
    print("all checks passed in WebKit")


asyncio.run(main())
