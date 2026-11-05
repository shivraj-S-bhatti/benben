"""Render SPEC.md into one portable HTML file; no server, network or build tool."""
from pathlib import Path
import base64
import mimetypes
import re

import markdown

ROOT = Path(__file__).resolve().parent
source = (ROOT / 'SPEC.md').read_text()
body = markdown.markdown(source, extensions=['tables', 'fenced_code', 'toc'])

def embed(match):
    name = match.group(1)
    path = ROOT / name
    mime = mimetypes.guess_type(name)[0] or 'application/octet-stream'
    encoded = base64.b64encode(path.read_bytes()).decode()
    return 'src="data:' + mime + ';base64,' + encoded + '"'

body = re.sub(r'src="(assets/[^"#]+)"', embed, body)
links = re.findall(r'<h2 id="([^"]+)">([^<]+)</h2>', body)
nav = ''.join(f'<a href="#{anchor}">{title}</a>' for anchor, title in links)
css = '''
:root{color-scheme:light;--paper:#f8f7f0;--ink:#213d37;--muted:#647169;--rule:#d7ded2;--accent:#267564}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}body{margin:0;background:var(--paper);color:#25352e;font:16px/1.7 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
a{color:#176854;text-underline-offset:3px}a:hover{color:#154433}header{padding:24px 5vw;border-bottom:1px solid var(--rule);display:flex;justify-content:space-between;gap:20px;font-size:13px;letter-spacing:.02em;color:var(--muted)}header strong{color:var(--ink)}.layout{display:grid;grid-template-columns:220px minmax(0,1000px);gap:52px;max-width:1370px;margin:auto;padding:42px 40px 100px}nav{position:sticky;top:24px;align-self:start;font-size:12px;line-height:1.6}nav a{display:block;text-decoration:none;padding:9px 0;border-bottom:1px solid var(--rule)}nav .caption{font-weight:700;letter-spacing:.12em;font-size:10px;margin-bottom:14px;color:var(--muted)}main{min-width:0}h1{font:normal clamp(40px,5vw,68px)/1.08 Georgia,serif;letter-spacing:-.035em;color:var(--ink);margin:4px 0 25px;max-width:870px}h2{font:normal 34px/1.15 Georgia,serif;color:var(--ink);margin:74px 0 24px;padding-top:26px;border-top:1px solid var(--rule)}h3{font-size:20px;margin-top:36px;line-height:1.3}p{max-width:86ch;margin:16px 0}main>p:first-of-type{color:var(--muted);font-size:14px}strong{color:var(--ink)}img{display:block;max-width:100%;height:auto;margin:22px auto 10px;border:1px solid var(--rule);border-radius:5px;background:white}img[src^="data:image/png"]{max-height:540px;width:100%;object-fit:contain}p:has(>em:only-child){font-size:13px;color:var(--muted);line-height:1.55;margin-top:8px}table{display:block;overflow:auto;width:100%;border-collapse:collapse;font-size:14px;line-height:1.65;margin:24px 0;background:#fff}th,td{text-align:left;vertical-align:top;padding:15px 17px;border:1px solid var(--rule);min-width:160px}th{color:var(--ink);background:#e9eee3;font-size:12px}pre{overflow:auto;padding:24px;background:#e8ede3;border:1px solid var(--rule);border-radius:5px;font-size:13px;line-height:1.7}code{font: .87em ui-monospace,SFMono-Regular,Menlo,monospace;background:#e8ede3;padding:2px 4px;border-radius:3px}pre code{padding:0}li{padding:4px 0;max-width:88ch}footer{border-top:1px solid var(--rule);padding:30px 5vw;color:var(--muted);font-size:12px}button{font:inherit;font-size:12px;border:1px solid var(--rule);background:white;border-radius:5px;padding:7px 13px;cursor:pointer}a:focus-visible,button:focus-visible{outline:3px solid #b27a21;outline-offset:3px}@media(max-width:1050px){.layout{display:block;padding:28px 22px 70px}nav{position:static;display:flex;flex-wrap:wrap;gap:4px 16px;margin-bottom:35px}nav .caption{width:100%}nav a{max-width:270px}h2{margin-top:54px}header{padding:18px 22px}}@media print{nav,button{display:none}.layout{display:block;padding:0}body{background:white;font-size:11pt}header{padding:0 0 12pt}h2{break-before:auto;font-size:23pt}table{display:table;font-size:9pt}th,td{padding:7pt;min-width:0}img{max-height:500px}a{color:inherit}pre{white-space:pre-wrap}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
'''
html = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BenBen — ambitious branch specification</title><style>' + css + '</style><body><header><strong>BENBEN / PRODUCT + BUILD SPECIFICATION</strong><span>04 NOV 2026 · ASTRA + CLAUDE</span><button onclick="window.print()">Print / save PDF</button></header><div class="layout"><nav aria-label="Contents"><div class="caption">THE BUILD PLAN</div>' + nav + '</nav><main>' + body + '</main></div><footer>Canonical source: SPEC.md · Proposed implementation, with an explicit baseline ledger · Images embedded in this HTML for portability.</footer></body></html>'
(ROOT / 'SPEC.html').write_text(html)
image_count = len(re.findall('src="data:', body))
print(f'Rendered {len(links)} sections; {len(html):,} bytes; embedded {image_count} images.')
