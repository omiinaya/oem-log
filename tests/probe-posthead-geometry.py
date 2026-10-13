# dev-blog post-head geometry probe: run BEFORE and AFTER the PostHead adoption
# and diff the two readings. Measures the rendered box, not the source.
from playwright.sync_api import sync_playwright
import json, sys

URL = "http://192.168.1.68:4322/blog/a-hundred-tor-exits-kept-alive-and-honest/"
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/devblog-geom.json"

PROBE = """() => {
  const px = (el, p) => el ? getComputedStyle(el)[p] : null;
  const head = document.querySelector('.cm-post-head') || document.querySelector('.post-head');
  const h1 = head && head.querySelector('h1');
  const kicker = head && head.querySelector('.cm-kicker');
  const by = document.querySelector('.cm-byline') || document.querySelector('.byline');
  const prose = document.querySelector('.cm-prose');
  const byKids = by ? [...by.children].filter(e => e.getBoundingClientRect().height > 0) : [];
  const tops = new Set(byKids.map(e => Math.round(e.getBoundingClientRect().top)));
  const firstProseBlock = prose ? prose.querySelector('h2, p') : null;
  return {
    head: head ? {
      cls: head.className,
      padTop: px(head,'paddingTop'), padBottom: px(head,'paddingBottom'),
      marginBottom: px(head,'marginBottom'), borderBottom: px(head,'borderBottomWidth'),
      height: Math.round(head.getBoundingClientRect().height),
    } : null,
    h1: h1 ? { fontSize: px(h1,'fontSize'), lineHeight: px(h1,'lineHeight'),
               letterSpacing: px(h1,'letterSpacing'), marginBottom: px(h1,'marginBottom'),
               fontWeight: px(h1,'fontWeight'), text: h1.textContent.trim().slice(0,30) } : null,
    kicker: kicker ? { marginBottom: px(kicker,'marginBottom'), cls: kicker.className } : null,
    byline: by ? { cls: by.className, fontSize: px(by,'fontSize'), gap: px(by,'gap'),
                   color: px(by,'color'), flexWrap: px(by,'flexWrap'), rows: tops.size,
                   sepElements: by.querySelectorAll('.sep, .cm-byline__sep').length,
                   genMarks: [...by.children].filter((el,i) =>
                     i>0 && getComputedStyle(el,'::before').content.includes('\\u00b7')).length,
                   text: by.textContent.replace(/\\s+/g,' ').trim() } : null,
    prose: prose ? { fontSize: px(prose,'fontSize'), lineHeight: px(prose,'lineHeight'),
                     color: px(prose,'color'), textAlign: px(prose,'textAlign') } : null,
    h2mark: prose ? px(prose.querySelector('h2'), 'marginTop') : null,
    // the join the library's --stack-head exists to close
    join: (head && firstProseBlock) ? Math.round(
      firstProseBlock.getBoundingClientRect().top - head.getBoundingClientRect().bottom) : null,
    // the h2 '## ' mark is a ::before; prove it is rendered
    h2before: prose && prose.querySelector('h2')
      ? getComputedStyle(prose.querySelector('h2'),'::before').content : null,
    docW: document.documentElement.scrollWidth, winW: window.innerWidth,
  };
}"""

out = {}
with sync_playwright() as p:
    b = p.webkit.launch()
    for w, h in [(390, 844), (1280, 900)]:
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
        pg.emulate_media(reduced_motion="reduce")
        pg.goto(URL, wait_until="networkidle")
        try:
            pg.wait_for_function("() => !!document.querySelector('.cm-byline, .byline') || !!window.cliMono", timeout=15000)
        except Exception:
            pass
        pg.evaluate("() => document.fonts.ready")
        # settle before reading painted layout
        pg.wait_for_timeout(250)
        out[f"{w}x{h}"] = pg.evaluate(PROBE)
        pg.close()
    b.close()

print(json.dumps(out, indent=2))
open(OUT, "w").write(json.dumps(out, indent=2))
print(f"\nwritten to {OUT}")