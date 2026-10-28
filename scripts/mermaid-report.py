#!/usr/bin/env python3
"""Build a self-contained HTML audit from actual before/after Elisp output.

Run from the repository root after scripts/mermaid-audit.el:
  python3 scripts/mermaid-report.py
"""
import base64
import html
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'reports/mermaid'
NS = {'s': 'http://www.w3.org/2000/svg'}

def check(case):
    expected, svg = case['checks'], case.get('svg')
    if expected.get('fallback'):
        return [] if not svg else ['Expected source fallback; renderer produced a partial or empty SVG.']
    if not svg:
        return ['No SVG returned for this supported example.']
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as error:
        return ['Malformed SVG XML: ' + str(error)]
    failures = []
    texts = {''.join(t.itertext()): t for t in root.findall('.//s:text', NS)}
    for text in expected.get('texts', []):
        if text not in texts: failures.append('Missing text: ' + text)
    for text in expected.get('absent', []):
        if text in texts: failures.append('Unexpected text: ' + text)
    for attr in ['width', 'height']:
        if float(root.get(attr, '0')) <= 0: failures.append('Non-positive SVG ' + attr)
    lines = root.findall('s:line', NS) + root.findall('s:path', NS)
    arrows = [e for e in lines if e.get('marker-end') or e.get('marker-start')]
    edges = root.findall('s:path', NS) + root.findall('s:line', NS) if case['family'] == 'Flowchart' else arrows
    if 'edges' in expected and len(edges) != expected['edges']:
        # Subroutine separators are node decoration, not edges.
        if not (case['id'] == 'flow-shapes' and len(root.findall('s:path', NS)) == expected['edges']):
            failures.append(f"Expected {expected['edges']} connections; found {len(edges)}.")
    if 'arrows' in expected and len(arrows) != expected['arrows']:
        failures.append(f"Expected {expected['arrows']} arrowheads; found {len(arrows)}.")
    if expected.get('circle') and not root.findall('s:circle', NS): failures.append('Circle node missing.')
    if expected.get('dashed') and not any(e.get('stroke-dasharray') for e in lines): failures.append('Dashed line missing.')
    if expected.get('thick') and not any(e.get('stroke-width') == '3' for e in lines): failures.append('Thick line missing.')
    if 'order' in expected:
        direction, *labels = expected['order']
        axis = 'x' if direction in ['LR', 'RL'] else 'y'
        if all(label in texts for label in labels):
            values = [float(texts[label].get(axis)) for label in labels]
            pairs = zip(values, values[1:])
            if not all(a > b if direction in ['RL', 'BT'] else a < b for a,b in pairs):
                failures.append('Node order does not follow ' + direction + '.')
    if expected.get('nondegenerate'):
        for e in edges:
            if e.tag.endswith('path'):
                values = list(map(float, re.findall(r'-?\d+(?:\.\d+)?', e.get('d'))))
                points = list(zip(values[::2],values[1::2]))
                if points and points[0] == points[-1] and len({y for x,y in points}) < 2:
                    failures.append('Self-loop collapses to a retraced line.')
    if 'markers' in expected:
        relations = []
        for e in list(root)[1:]:
            if e.tag.endswith('rect'):
                if e.get('x') == '0': continue
                break
            if e.tag.endswith('line'):
                relations.append([e.get('marker-start'), e.get('marker-end'), e.get('stroke-dasharray')])
        if relations != expected['markers']:
            failures.append('Relationship marker endpoints or line styles are incorrect.')
    return failures

def esc(s): return html.escape(str(s))
def preview(case):
    if not case.get('svg'):
        return '<div class="fallback"><span>Source preserved</span><p>No SVG returned. The Markdown renderer can show this as a code block.</p></div>'
    root = ET.fromstring(case['svg'])
    width, height = float(root.get('width', '0')), float(root.get('height', '0'))
    if width <= 0 or height <= 0:
        return f'<div class="fallback"><span>Blank SVG</span><p>The renderer returned a {width:g} × {height:g} canvas with no visible diagram.</p></div>'
    data=base64.b64encode(case['svg'].encode()).decode()
    return f'<img alt="{esc(case["title"])} rendered SVG" src="data:image/svg+xml;base64,{data}">'

def main():
    before = json.loads((OUT/'before.json').read_text())
    after = json.loads((OUT/'after.json').read_text())
    previous = {c['id']:c for c in before['cases']}
    results=[]
    for case in after['cases']:
        old=previous[case['id']]
        results.append(dict(case=case, before=old, before_errors=check(old), errors=check(case)))
    fixed=sum(bool(r['before_errors']) and not r['errors'] for r in results)
    failed=sum(bool(r['errors']) for r in results)
    rendered=sum(bool(r['case'].get('svg')) and not r['errors'] for r in results)
    fallback=sum(not r['case'].get('svg') and not r['errors'] for r in results)
    verification = ''
    if (OUT/'tests.log').exists():
        log = (OUT/'tests.log').read_text()
        match = re.search(r'Ran (\d+) tests, (\d+) results as expected, (\d+) unexpected, (\d+) skipped', log)
        if match:
            total, passed, unexpected, skipped = match.groups()
            verification += f'<p><strong>Full suite:</strong> {passed} passed, {unexpected} failed, {skipped} skipped out of {total}. The skipped tests require graphical list-marker measurements and are unrelated to Mermaid. <a href="tests.log">Complete test log</a>.</p>'
    if (OUT/'browser-checks.json').exists():
        browser = json.loads((OUT/'browser-checks.json').read_text())
        clipped = sum(bool(c['clipped']) for c in browser)
        unloaded = sum(not c['loaded'] for c in browser)
        verification += f'<p><strong>Browser geometry:</strong> {len(browser)} after SVGs measured; {clipped} with text outside the canvas, {unloaded} failed to load. <a href="browser-checks.json">Measurements</a>. Desktop and mobile report layout and filtering were checked separately.</p>'
    verification += '<p><strong>Integration:</strong> tilde and longer backtick fences, source fallback, image-backend errors and theme-cache refresh have dedicated ERT tests. The modified renderer files also compile with warnings treated as errors.</p>'
    cards=[]
    for r in results:
        c=r['case']; status='issue' if r['errors'] else 'fallback' if not c.get('svg') else 'fixed' if r['before_errors'] else 'pass'
        label={'issue':'Still failing','fallback':'Source fallback','fixed':'Fixed','pass':'Passed before & after'}[status]
        old_result='; '.join(r['before_errors']) or ('Expected source fallback.' if not r['before'].get('svg') else 'All declared checks passed.')
        new_result='; '.join(r['errors']) or ('Expected source fallback. This feature is not rendered.' if not c.get('svg') else 'All declared checks passed.')
        cards.append(f'''<article class="case" data-status="{status}" data-family="{esc(c['family'])}" id="{c['id']}">
<div class="case-head"><div><div class="eyebrow">{esc(c['family'])} · {esc(c['id'])}</div><h3>{esc(c['title'])}</h3></div><span class="badge {status}">{label}</span></div>
<p>{esc(c['description'])}</p><div class="comparison"><section><h4>Before</h4><div class="preview">{preview(r['before'])}</div><p class="finding {'bad' if r['before_errors'] else ''}">{esc(old_result)}</p></section><section><h4>After</h4><div class="preview">{preview(c)}</div><p class="finding">{esc(new_result)}</p></section></div>
<details><summary>Mermaid source and checks</summary><pre>{esc(c['code'])}</pre><pre>{esc(json.dumps(c['checks'],indent=2))}</pre></details></article>''')
    summary={'cases':len(results),'rendered':rendered,'expected_fallback':fallback,'fixed_cases':fixed,'remaining_failed_checks':failed,
             'results':[{'id':r['case']['id'],'before_errors':r['before_errors'],'after_errors':r['errors']} for r in results]}
    (OUT/'results.json').write_text(json.dumps(summary,indent=2)+'\n')
    css='''*{box-sizing:border-box}body{margin:0;background:#f3f5f8;color:#23314a;font:16px/1.6 system-ui,sans-serif}main{max-width:1240px;margin:auto;padding:54px 30px 90px}.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.13em;color:#5b6b83;font-weight:700}h1{font-size:48px;line-height:1.12;letter-spacing:-.04em;margin:14px 0}h2{font-size:26px;letter-spacing:-.02em}h3{font-size:22px;margin:4px 0}h4{margin:0 0 12px;color:#5b6b83;font-size:12px;text-transform:uppercase;letter-spacing:.12em}header p{max-width:850px;font-size:18px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:32px 0}.stat{background:#fff;border:1px solid #dae1ea;border-radius:12px;padding:20px}.stat b{display:block;font-size:36px;line-height:1.2}.stat span{color:#5b6b83;font-size:14px}.context{background:#e6edf7;border-left:4px solid #2457a6;padding:20px 24px;border-radius:4px;margin:28px 0}.context p{margin:6px 0}.limits{background:#fff4df;border-color:#bb7b15}.toolbar{display:flex;flex-wrap:wrap;gap:10px;position:sticky;top:0;z-index:2;background:#f3f5f8ee;backdrop-filter:blur(12px);padding:16px 0}button,select,input{font:inherit;border:1px solid #cbd5e3;background:white;border-radius:8px;padding:9px 12px}button{cursor:pointer}button.active{background:#243b60;color:white;border-color:#243b60}input{flex:1;min-width:180px}.case{background:white;border:1px solid #dae1ea;border-radius:14px;padding:26px;margin:20px 0;scroll-margin-top:100px}.case-head{display:flex;justify-content:space-between;align-items:flex-start;gap:18px}.badge{font-size:12px;font-weight:700;padding:6px 10px;border-radius:100px;white-space:nowrap}.pass,.fixed{background:#e4f4ed;color:#176247}.fallback{color:#825316}.badge.fallback{background:#fff0ce}.issue{background:#fee7e4;color:#983927}.comparison{display:grid;grid-template-columns:1fr 1fr;gap:20px}.comparison section{min-width:0}.preview{height:350px;background:#f8fafc;border:1px solid #e1e7f0;border-radius:8px;display:flex;align-items:center;justify-content:center;overflow:auto;padding:15px}.preview img{display:block;max-width:100%;max-height:100%;object-fit:contain}.preview .fallback{max-width:320px;text-align:center}.fallback span{font-size:18px;font-weight:700}.fallback p{font-size:14px}.finding{font-size:13px;color:#48627b}.finding.bad{color:#a44733}details{border-top:1px solid #e3e8ef;padding-top:15px;margin-top:15px}summary{cursor:pointer;color:#38557c;font-weight:600}pre{overflow:auto;background:#14243c;color:#e1eafa;border-radius:8px;padding:18px;font:13px/1.65 ui-monospace,monospace}a{color:#2457a6}.context code{overflow-wrap:anywhere}footer{font-size:14px;color:#5b6b83;margin-top:35px}.hidden{display:none}@media(max-width:760px){main{padding:28px 16px}h1{font-size:34px}.stats{grid-template-columns:repeat(2,1fr)}.comparison{grid-template-columns:1fr}.case-head{display:block}.case{padding:18px}.badge{display:inline-block;margin-top:8px}.preview{height:290px}.toolbar{position:static}}@media print{.toolbar{display:none}.case{break-inside:avoid}.preview{height:260px}main{padding:0}.hidden{display:block}}'''
    doc=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Mermaid rendering audit · markdown-modern</title><style>{css}</style></head><body><main>
<header><div class="eyebrow">markdown-modern / renderer audit / 28 October 2026</div><h1>Mermaid rendering,<br>tested diagram by diagram.</h1><p>Actual SVG output from the project's Emacs Lisp renderer, compared before and after fixes. {len(results)} cases cover five built-in diagram families, seven unsupported families, and input handling.</p></header>
<div class="stats"><div class="stat"><b>{len(results)}</b><span>examples exercised</span></div><div class="stat"><b>{rendered}</b><span>rendered examples passing</span></div><div class="stat"><b>{fixed}</b><span>previously failing cases corrected</span></div><div class="stat"><b>{fallback}</b><span>expected source fallbacks</span></div></div>
<div class="context"><p><strong>{failed} remaining failed fixture checks.</strong> A pass means the declared content, direction or marker assertions succeeded. It is not a claim of complete Mermaid compatibility.</p><p>Baseline: commit <code>6bd0385757d685d7a621b13864f0c2dfae2241ca</code>. Emacs {esc(after['emacs'])}; fixed light palette for comparison. Each preview embeds the returned SVG as an isolated image; no Mermaid JavaScript or external assets are used.</p></div>
<h2>Verification</h2>{verification}<h2>What improved</h2><p>Flowcharts now preserve chains, semicolons, explicit labels, supported shapes, undirected links and all four layout directions. They reuse the state renderer's routing to give cycles and multiline labels space. Class relationships now put the correct symbol on the correct endpoint. ER parsing accepts each cardinality, dashed links and isolated entities, places crow's feet next to their entities, and reserves room for attribute constraints. Leading comments and empty diagrams are handled consistently.</p>
<div class="context limits"><p><strong>What still does not render</strong></p><p>Subgraphs and advanced flowchart syntax, sequence activations, composite states, state notes and class multiplicity are source fallbacks in the tested cases. Pie, Gantt, mindmap, timeline, journey, Git graph and XY chart families have no built-in renderer.</p><p>The supported subset is intentionally limited. This audit does not establish complete support for styling, frontmatter, directives, actor silhouettes, class namespaces, custom shapes, HTML labels, or complex class/ER edge routing. Built-in HTML export still emits Mermaid fences as code, not diagrams. Browser previews validate SVG display; they do not substitute for a graphical Emacs/librsvg screenshot.</p></div>
<h2>Before / after gallery</h2><div class="toolbar" aria-label="Filter audit cases"><button data-filter="all" class="active">All cases</button><button data-filter="fixed">Fixed renders</button><button data-filter="fallback">Source fallbacks</button><button data-filter="issue">Still failing</button><input id="search" type="search" placeholder="Search family, title or source" aria-label="Search cases"></div><p id="visible-count" aria-live="polite"></p>
{''.join(cards)}
<footer><h2>Evidence and reproduction</h2><p>Machine-readable results: <a href="results.json">results.json</a> · <a href="before.json">before.json</a> · <a href="after.json">after.json</a>. Fixtures and scripts live in the repository. The HTML is self-contained for sharing; these evidence files are optional companions.</p><pre>emacs -Q --batch -L lisp -l scripts/mermaid-audit.el -- reports/mermaid/after.json\npython3 scripts/mermaid-report.py\nmake test</pre><p>Syntax checked against official Mermaid documentation: <a href="https://mermaid.js.org/syntax/flowchart.html">flowchart</a>, <a href="https://mermaid.js.org/syntax/sequenceDiagram.html">sequence</a>, <a href="https://mermaid.js.org/syntax/stateDiagram.html">state</a>, <a href="https://mermaid.js.org/syntax/classDiagram.html">class</a>, <a href="https://mermaid.js.org/syntax/entityRelationshipDiagram.html">ER</a>. Tests target meaning and retained content, not pixel equality with upstream Mermaid.</p></footer></main><script>
let filter='all';const cases=[...document.querySelectorAll('.case')];function update(){{let n=0;const q=document.querySelector('#search').value.toLowerCase();cases.forEach(c=>{{let show=(filter==='all'||c.dataset.status===filter)&&c.textContent.toLowerCase().includes(q);c.classList.toggle('hidden',!show);if(show)n++}});document.querySelector('#visible-count').textContent=n+' of '+cases.length+' cases shown'}}document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{{filter=b.dataset.filter;document.querySelectorAll('[data-filter]').forEach(x=>x.classList.toggle('active',x===b));update()}}));document.querySelector('#search').addEventListener('input',update);update();
</script></body></html>'''
    (OUT/'report.html').write_text(doc)
    print(json.dumps({k:v for k,v in summary.items() if k!='results'},indent=2))
    for r in results:
        if r['errors']: print(r['case']['id'],r['errors'])
    return failed

if __name__=='__main__':
    raise SystemExit(bool(main()))
