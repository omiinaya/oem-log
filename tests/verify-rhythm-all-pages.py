"""Measure the vertical rhythm on every page of a site at once.

The library's stack owns the gap between top-level blocks. A page-local
margin on one of those blocks does not replace that gap, it stacks on
top of it, so the join reads gap + margin. That is how links came to
measure 56px against a 24px rhythm, and portfolio 72px: the stack still
reports 24, so the CSS looks right and only the geometry gives it away.

Measures real joins, not declared values, in WebKit at Omar's iPhone
viewport. Exits non-zero if any top-level block carries a vertical
margin, naming the element and the page.
"""

import asyncio
import sys

from playwright.async_api import async_playwright

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.68:4401/"
PATHS = sys.argv[2:] or ["/"]

JS = """() => {
  const main = document.querySelector('main');
  if (!main) return {error: 'no <main>'};
  const cs = getComputedStyle(main);
  const kids = [...main.children].filter((e) => {
    const c = getComputedStyle(e);
    return c.display !== 'none' && c.position !== 'sticky' && c.position !== 'fixed';
  });

  // A main with a single child has nothing to separate, so a top-level
  // rhythm is meaningless there and its absence is not a defect. A blog
  // post is one <article>: the reading column IS the layout. Only a main
  // with two or more blocks needs an owner, and that is the case where a
  // missing stack shows up as ad-hoc per-section margins.
  if (kids.length < 2)
    return {single: true, cls: main.className, n: kids.length,
            stack: cs.display.includes('flex')};

  if (!cs.display.includes('flex'))
    return {error: '<main> has ' + kids.length + ' top-level blocks but is not a '
                 + 'flex stack, so nothing owns the rhythm',
            cls: main.className, display: cs.display, n: kids.length};
  const offenders = [];
  for (const e of kids) {
    const c = getComputedStyle(e);
    const mt = parseFloat(c.marginTop), mb = parseFloat(c.marginBottom);
    if (mt > 0 || mb > 0)
      offenders.push({
        el: e.tagName.toLowerCase() + '.' + (e.className.split(' ')[0] || '(none)'),
        mt: c.marginTop, mb: c.marginBottom,
        inline: e.getAttribute('style') || '(none)',
      });
  }
  const joins = [];
  for (let i = 1; i < kids.length; i++) {
    const a = kids[i - 1].getBoundingClientRect(), b = kids[i].getBoundingClientRect();
    joins.push(Math.round((b.top - a.bottom) * 10) / 10);
  }
  return {cls: main.className, gap: cs.gap, n: kids.length,
          joins: joins, offenders: offenders};
}"""


async def main():
    failures = []
    async with async_playwright() as pw:
        browser = await pw.webkit.launch()
        for path in PATHS:
            ctx = await browser.new_context(viewport={"width": 402, "height": 874})
            page = await ctx.new_page()
            try:
                await page.goto(BASE_URL.rstrip("/") + path,
                                wait_until="networkidle", timeout=45000)
                await page.wait_for_timeout(600)
                r = await page.evaluate(JS)
            except Exception as exc:
                msg = f"  {path}: could not load ({str(exc)[:60]})"
                print("FAIL " + msg)
                failures.append(msg)
                await ctx.close()
                continue

            if r.get("single"):
                print(f"SKIP {path:<28} main={r['cls']!r} has {r['n']} block: "
                      f"nothing to separate")
                await ctx.close()
                continue

            if "error" in r:
                msg = f"  {path}: {r['error']}"
                print("FAIL " + msg)
                failures.append(msg)
                await ctx.close()
                continue

            distinct = sorted(set(r["joins"]))
            head = (f"gap={r['gap']:>5}  n={r['n']}  joins={distinct}")
            if len(distinct) == 1 and not r["offenders"]:
                print(f"PASS {path:<28} {head}")
            else:
                note = "" if len(distinct) == 1 else "  <-- MIXED RHYTHM"
                print(f"FAIL {path:<28} {head}{note}")
                failures.append(f"  {path}: joins {distinct} are not uniform")
                for o in r["offenders"]:
                    print(f"       carries its own margin: {o['el']} "
                          f"mt={o['mt']} mb={o['mb']} inline={o['inline']}")
                    failures.append(
                        f"  {path}: {o['el']} carries margin-bottom on top "
                        f"of the stack gap")
            await ctx.close()
        await browser.close()

    if failures:
        print()
        print("\n".join(failures))
        print("FAIL: a page-local margin is stacking on the library's gap")
        sys.exit(1)
    print("PASS: every main with 2+ top-level blocks is a stack, and nothing "
          "overrides its gap")


asyncio.run(main())