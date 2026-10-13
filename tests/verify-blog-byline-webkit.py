# oem/log (dev-blog) byline, after adopting the library <PostHead>.
#
# The post page's byline has TWO fragments today (author + date) because no
# post carries `updatedDate`, so it never wraps - and a byline that does not
# wrap cannot strand a separator. That makes the page a weak test of the
# thing it just adopted. So this harness measures BOTH:
#
#   1. the page as a reader sees it, and
#   2. the same byline cloned into a 190px host, which FORCES the wrap and
#      exercises the exact geometry the library's fix is about.
#
# The invariant is "no visual line ends with a separator", measured from the
# DOM (the distinct top edges of visible children), not from a screenshot.
from playwright.sync_api import sync_playwright
import sys

WIDTHS = [(320, 667), (390, 844), (402, 874), (430, 932), (1280, 900)]
URL = "http://192.168.1.68:4322/blog/a-hundred-tor-exits-kept-alive-and-honest/"
NARROW = 190

PROBE = """(sel) => {
  const by = document.querySelector(sel);
  if (!by) return { error: 'no byline at ' + sel };
  const kids = [...by.children].filter(e => e.getBoundingClientRect().height > 0);
  const rows = new Map();
  kids.forEach(el => {
    const t = Math.round(el.getBoundingClientRect().top);
    if (!rows.has(t)) rows.set(t, []);
    rows.get(t).push(el);
  });
  const out = [];
  let stranded = 0;
  rows.forEach(row => {
    const last = row[row.length - 1];
    // Two ways a visual line can END with a separator, and a probe that
    // only reads ELEMENTS sees one of them:
    //   - a separator ELEMENT as the last child (the shipped defect), and
    //   - an `::after` mark on the last child (the wrong fix: it also stops
    //     the dot being a flex item, but rides the PRECEDING fragment, so
    //     the dot is still the last thing on the line).
    // Computed `::after` content is the only thing that can see the second.
    const afterContent = getComputedStyle(last, '::after').content;
    const endsWithSep =
      /sep/.test(last.className) ||
      /\\u00b7/.test(last.textContent) ||
      (afterContent && afterContent.includes('\\u00b7'));
    if (endsWithSep) stranded++;
    out.push({ text: row.map(e => e.textContent.trim()).join(' '),
               left: Math.round(row[0].getBoundingClientRect().left),
               after: afterContent,
               endsWithSep });
  });
  return {
    kind: by.className,
    flexWrap: getComputedStyle(by).flexWrap,
    sepElements: by.querySelectorAll('.sep, .cm-byline__sep').length,
    genMarks: [...by.children].filter((el, i) =>
      i > 0 && getComputedStyle(el, '::before').content.includes('\\u00b7')).length,
    rowCount: rows.size,
    stranded,
    rows: out,
  };
}"""

report, fails = [], []

with sync_playwright() as p:
    browser = p.webkit.launch()
    for w, h in WIDTHS:
        pg = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
        pg.emulate_media(reduced_motion="reduce")
        pg.goto(URL, wait_until="networkidle")
        try:
            pg.wait_for_function(
                "() => !!document.querySelector('.cm-byline') || "
                "document.documentElement.classList.contains('cm-js')", timeout=15000)
        except Exception:
            pass
        pg.evaluate("() => document.fonts.ready")
        pg.wait_for_timeout(250)

        readings = [("page", pg.evaluate(PROBE, ".cm-byline"))]

        # Force the wrappable case the shipped content does not yet produce.
        # The clone gets the THIRD fragment `<PostHead>` renders when
        # `updatedDate` is set - the same bare <span> the component emits,
        # so this is the component's real output shape and not a fiction.
        # Measured with two fragments the row does not wrap even at 190px,
        # so without this the harness would assert the invariant on a layout
        # that cannot violate it.
        pg.evaluate(
            """(n) => {
              const src = document.querySelector('.cm-byline');
              const clone = src.cloneNode(true);
              const span = document.createElement('span');
              span.textContent = 'updated Sep 27, 2026';
              clone.appendChild(span);
              const host = document.createElement('div');
              host.id = '__narrowhost';
              host.style.cssText = 'width:' + n + 'px';
              host.appendChild(clone);
              document.body.appendChild(host);
            }""", NARROW)
        pg.wait_for_timeout(120)
        readings.append((f"narrow{NARROW}", pg.evaluate(PROBE, "#__narrowhost .cm-byline")))
        pg.close()

        for label, r in readings:
            tag = f"{w}x{h} {label}"
            if "error" in r:
                fails.append(f"{tag}: {r['error']}")
                continue
            if r["sepElements"] != 0:
                fails.append(f"{tag}: {r['sepElements']} separator ELEMENT(s) present")
            if r["genMarks"] == 0:
                fails.append(f"{tag}: no generated mark - 'no line ends with a separator' "
                             "would be vacuously true")
            if r["flexWrap"] != "wrap":
                fails.append(f"{tag}: flex-wrap is {r['flexWrap']}, so this measures nothing")
            if r["stranded"]:
                fails.append(f"{tag}: {r['stranded']} line(s) END with a separator")
            report.append((tag, r))

    browser.close()

print("oem/log byline, via the library's <PostHead>")
print()
for tag, r in report:
    print(f"{tag:<22} wrap={r['flexWrap']} sepEls={r['sepElements']} "
          f"genMarks={r['genMarks']} lines={r['rowCount']} stranded={r['stranded']}")

narrow = [r["rowCount"] for tag, r in report if "narrow" in tag]
page = [r["rowCount"] for tag, r in report if tag.endswith("page")]
print(f"\nnarrow{NARROW} line counts: {narrow}")
print(f"page line counts:     {page}")
if len(set(narrow)) == 1 and narrow[0] < 2:
    fails.append("the forced-narrow host never wrapped, so the wrappable case was never rendered")

print()
if fails:
    print(f"FAIL ({len(fails)})")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print(f"PASS - {len(report)} readings; the separator is generated, no element remains, "
      "and no visual line ends with one, including in the forced-wrap host")
