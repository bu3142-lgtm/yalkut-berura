#!/usr/bin/env python3
"""Перенос блоков «Ялкут Йосеф» из yalkutIosef_all.html в yalkut/<id>.json + сверка с источником.
Единственное изменение текста — замена по решению автора: Бог→Б-г, Господь→Г-сподь (все падежи)."""
import re, json, html, sys, os
SRC, OUT = sys.argv[1], sys.argv[2]
ids = sys.argv[3:]
s = open(SRC, encoding='utf-8').read()
os.makedirs(OUT, exist_ok=True)
SUBS = [(re.compile(r'\bБог(а|у|ом|е)?\b'), lambda m: 'Б-г' + (m.group(1) or '')),
        (re.compile(r'\bГосподь\b'), lambda m: 'Г-сподь'),
        (re.compile(r'\bГоспод(а|у|ом|е|и|не|ень|ни|ний|нее)\b'), lambda m: 'Г-спод' + m.group(1))]
def divine(text, c):
    for rx, f in SUBS:
        text, n = rx.subn(f, text); c[0] += n
    return text
def text_nodes(htmlstr, c):
    return ''.join(p if p.startswith('<') else divine(p, c) for p in re.split(r'(<[^>]*>)', htmlstr))
NOTE = re.compile(r'<span class="note-marker" data-note="([^"]*)">(.*?)</span>', re.S)
YN = re.compile(r'<span class="yn" data-y="(\d+)">(.*?)</span>', re.S)

report = {}
for bid in ids:
    b = re.search(r'<section class="chapter-block"[^>]*id="yalkutIosef_%s">(.*?)</section>' % re.escape(bid), s, re.S).group(1)
    num = re.search(r'class="number">([^<]*)<', b).group(1)
    title = html.unescape(re.sub(r'<[^>]+>', '', re.search(r'class="title">(.*?)</div>', b, re.S).group(1))).strip()
    d = re.search(r'class="description">(.*?)</p>', b, re.S)
    desc = html.unescape(re.sub(r'<[^>]+>', '', d.group(1))).strip() if d else ''
    src = [(did, inner) for did, dt, inner in re.findall(r'<div class="wrapper" data-id="([^"]*)" data-title="([^"]*)"><p>(.*?)</p></div>', b, re.S) if did != 'блок']
    cnt = [0]; notes = []; paras = []
    for did, inner in src:
        def rep(m):
            notes.append(divine(html.unescape(m.group(1)), cnt))
            return '<span class="yn" data-y="%d">%s</span>' % (len(notes), m.group(2))
        conv = NOTE.sub(rep, inner)               # сноски -> yn (текст сноски вынесен в notes)
        paras.append({'n': int(did.split()[1]), 'html': text_nodes(conv, cnt)})
    # --- сверка: собрать обратно и сравнить с источником (после той же замены) ---
    bad = []
    for (did, inner), p in zip(src, paras):
        exp_notes = [divine(html.unescape(x), [0]) for x in NOTE.findall(inner) and [m[0] for m in NOTE.findall(inner)]]
        exp_html = text_nodes(NOTE.sub(lambda m: '<span class="yn">%s</span>' % m.group(2), inner), [0])
        got_html = YN.sub(lambda m: '<span class="yn">%s</span>' % m.group(2), p['html'])
        got_notes = [notes[int(i) - 1] for i in re.findall(r'data-y="(\d+)"', p['html'])]
        if exp_html != got_html or exp_notes != got_notes: bad.append(p['n'])
    order_ok = [int(d.split()[1]) for d, _ in src] == [p['n'] for p in paras]
    seq_ok = [int(x) for x in re.findall(r'data-y="(\d+)"', ''.join(p['html'] for p in paras))] == list(range(1, len(notes) + 1))
    report[bid] = dict(абзацев_в_источнике=len(src), абзацев_в_результате=len(paras),
                       сносок_в_источнике=sum(len(NOTE.findall(i)) for _, i in src), сносок_в_результате=len(notes),
                       текст_и_сноски_идентичны=not bad, расхождения=bad[:5], порядок_абзацев=order_ok, сноски_подряд=seq_ok,
                       замен_Б_г_Г_сподь=cnt[0])
    json.dump(dict(id=bid, number=num, title=title, description=desc, paragraphs=paras, notes=notes),
              open(os.path.join(OUT, bid + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(json.dumps(report, ensure_ascii=False, indent=1))
