# NEGATIVE CONTROL for tests/verify-blog-byline-webkit.py.
#
# A probe that has never failed is a probe nobody has shown can work. This
# injects the WRONG fix - the separator generated with `::after` on
# :not(:last-child) instead of `::before` on :not(:first-child) - which stops
# the dot being a flex item but keeps it riding the PRECEDING fragment, so
# every wrapped line still ENDS with the dot. The probe reads ELEMENTS, so
# only the computed ::after on each row's last child can see this; if the
# probe stays green here, its "no line ends with a separator" means nothing.
from playwright.sync_api import sync_playwright
import sys

WRONG_FIX = """
  .cm-byline > *:not(:first-child)::before { content: none; }
  .cm-byline > *:not(:last-child)::after {
    content: '\\00b7';
    color: var(--ink-faint);
    opacity: 0.6;
    margin-inline-start: var(--space-2);
    margin-inline-end: 0;
  }
"""

PROBE = """(sel) => {
  const by = document.querySelector(sel);
  if (!by) return { error: 'no byline' };
  const kids = [...by.children].filter(e => e.getBoundingClientRect().height > 0);
  const rows = new Map();
  kids.forEach(el => {
    const t = Math.round(el.getBoundingClientRect().top);
    if (!rows.has(t)) rows.set(t, []);
    rows.get(t).push(el);
  });
  let stranded = 0;
  const detail = [];
  rows.forEach(row => {
    const last = row[row.length - 1];
    const after = getComputedStyle(last, '::after').content;
    const hit = /sep/.test(last.className) || /\\u00b7/.test(last.textContent) ||
                (after && after.includes('\\u00b7'));
    if (hit) stranded++;
    detail.push({ text: last.textContent.trim().slice(0, 20), after });
  });
  return { rows: rows.size, stranded, detail };
}"""

URL = "http://192.168.1.68:4322/blog/a-hundred-tor-exits-kept-alive-and-honest/"

with sync_playwright() as p:
    b = p.webkit.launch()
    pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    pg.emulate_media(reduced_motion="reduce")
    pg.goto(URL, wait_until="networkidle")
    pg.wait_for_function("() => !!document.querySelector('.cm-byline')", timeout=15000)
    pg.wait_for_timeout(200)

    # build the 3-fragment narrow host FIRST, as the real harness does
    pg.evaluate("""() => {
      const src = document.querySelector('.cm-byline');
      const clone = src.cloneNode(true);
      const s = document.createElement('span');
      s.textContent = 'updated Sep 27, 2026';
      clone.appendChild(s);
      const host = document.createElement('div');
      host.id = '__narrowhost';
      host.style.cssText = 'width:190px';
      host.appendChild(clone);
      document.body.appendChild(host);
    }""")
    before = pg.evaluate(PROBE, "#__narrowhost .cm-byline")

    pg.add_style_tag(content=WRONG_FIX)
    pg.wait_for_timeout(150)
    after = pg.evaluate(PROBE, "#__narrowhost .cm-byline")

    b.close()

print("narrow host, correct ::before fix :", before)
print("narrow host, WRONG   ::after fix  :", after)
print()
if after["stranded"] > 0 and before["stranded"] == 0:
    print("NEGATIVE CONTROL PASSES - the probe sees the ::after defect "
          f"({after['stranded']} line(s) flagged) and reports the real fix clean.")
    sys.exit(0)
print("NEGATIVE CONTROL FAILED - the probe is blind to the ::after defect, "
      "so its green run proves nothing.")
sys.exit(1)
