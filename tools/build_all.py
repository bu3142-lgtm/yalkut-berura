#!/usr/bin/env python3
"""Перенос «Ялкут Йосеф» из yalkutIosef_all.html в yalkut/*.json для всех глав, которые есть на сайте.
Запуск: python3 tools/build_all.py <yalkutIosef_all.html> <папка сайта>
Единственное изменение текста — решение автора: Бог→Б-г, Господь→Г-сподь (все падежи).
Для каждого блока: сверка числа абзацев и сносок, порядка, текста (независимо от разметки) и сносок."""
import re, json, html, sys, os, glob, collections, csv
SRC, SITE = sys.argv[1], sys.argv[2]
s = open(SRC, encoding='utf-8').read()
OUT = os.path.join(SITE, 'yalkut')
os.makedirs(OUT, exist_ok=True)
for f in glob.glob(os.path.join(OUT, '*.json')): os.remove(f)

SUBS = [(re.compile(r'\bБог(а|у|ом|е)?\b'), lambda m: 'Б-г' + (m.group(1) or '')),
        (re.compile(r'\bГосподь\b'), lambda m: 'Г-сподь'),
        (re.compile(r'\bГоспод(а|у|ом|е|и)\b'), lambda m: 'Г-спод' + m.group(1)),
        (re.compile(r'\bГосподн(\w*)\b'), lambda m: 'Г-сподн' + m.group(1)),
        (re.compile(r'\bГосподень\b'), lambda m: 'Г-сподень')]
def divine(text, c=None):
    for rx, f in SUBS:
        text, n = rx.subn(f, text)
        if c is not None: c[0] += n
    return text
def text_nodes(h, c):
    return ''.join(p if p.startswith('<') else divine(p, c) for p in re.split(r'(<[^>]*>)', h))
def plain(h): return html.unescape(re.sub(r'<[^>]+>', '', h))
NOTE = re.compile(r'<span class="note-marker" data-note="([^"]*)">(.*?)</span>', re.S)

# ---- какие главы есть на сайте ----
mb = set()
for f in glob.glob(os.path.join(SITE, 'content*.json')):
    m = re.fullmatch(r'content(\d*)\.json', os.path.basename(f))
    if m and m.group(1): mb.add(int(m.group(1)))
    elif m: mb.add(json.load(open(f, encoding='utf-8'))['chapter'])   # content.json
tomb = [m.start() for m in re.finditer(r'id="tom\d"', s)]
blocks = []
for m in re.finditer(r'<section class="chapter-block"[^>]*id="yalkutIosef_([^"]+)"[^>]*>(.*?)</section>', s, re.S):
    bid, b = m.group(1), m.group(2)
    num = re.search(r'class="number">([^<]*)<', b).group(1)
    title = html.unescape(re.sub(r'<[^>]+>', '', re.search(r'class="title">(.*?)</div>', b, re.S).group(1))).strip()
    d = re.search(r'class="description">(.*?)</p>', b, re.S)
    desc = html.unescape(re.sub(r'<[^>]+>', '', d.group(1))).strip() if d else ''
    t = re.match(r'Главы\s+([\d,\s–\-]+)', title)
    parts = bid.split('_')
    if t:
        tt = t.group(1).strip().rstrip(',')
        if re.search(r'[–\-]', tt) and ',' not in tt:
            a, z = [int(x) for x in re.split(r'\s*[–\-]\s*', tt)[:2]]; sims = list(range(a, z + 1))
        else: sims = [int(x) for x in re.findall(r'\d+', tt)]
        kind = 'combined'
    else:
        sims = [int(parts[0])]
        kind = 'plain' if len(parts) == 1 else ('continuation' if parts[1].startswith('v') else 'section')
    blocks.append(dict(id=bid, num=num, title=title, desc=desc, sims=sims, kind=kind, body=b, tom=sum(m.start() > t0 for t0 in tomb)))

report = []; index = collections.defaultdict(list); tot = collections.Counter(); left = collections.Counter(); left_ctx = collections.defaultdict(list)
skipped_service = []
for blk in blocks:
    if not set(blk['sims']) & mb: continue
    wr = re.findall(r'<div class="wrapper" data-id="([^"]*)" data-title="([^"]*)"><p([^>]*)>(.*?)</p></div>', blk['body'], re.S)
    if any(w[0] == 'блок' or w[2].strip() for w in wr): skipped_service.append(blk['id'])
    src = [(did, inner) for did, dt, pa, inner in wr if did != 'блок' and not pa.strip()]
    cnt = [0]; notes = []; paras = []
    for did, inner in src:
        def rep(mm):
            notes.append(divine(html.unescape(mm.group(1)), cnt))
            return '<span class="yn" data-y="%d">%s</span>' % (len(notes), mm.group(2))
        paras.append({'n': int(did.split()[1]), 'html': text_nodes(NOTE.sub(rep, inner), cnt)})
    # ---- сверка (независимо от разметки) ----
    bad = []
    for (did, inner), p in zip(src, paras):
        if plain(p['html']) != divine(plain(inner)): bad.append(('текст', p['n']))
        if p['n'] != int(did.split()[1]): bad.append(('порядок', p['n']))
    src_notes = [divine(html.unescape(x)) for _, i in src for x in [m_[0] for m_ in NOTE.findall(i)]]
    if src_notes != notes: bad.append(('сноски', 0))
    if [int(x) for x in re.findall(r'data-y="(\d+)"', ''.join(p['html'] for p in paras))] != list(range(1, len(notes) + 1)): bad.append(('нумерация сносок', 0))
    n_src_notes = sum(len(NOTE.findall(i)) for _, i in src)
    ok = not bad and len(paras) == len(src) and len(notes) == n_src_notes
    # остатки «Бог/Господь» после замены
    for p in paras:
        for w in re.findall(r'\b(?:Бог\w*|Господ\w*|бог\w*)\b', plain(p['html'])):
            left[w] += 1
    for n_ in notes:
        for w in re.findall(r'\b(?:Бог\w*|Господ\w*|бог\w*)\b', n_): left[w] += 1
    json.dump(dict(id=blk['id'], number=blk['num'], title=blk['title'], description=blk['desc'], kind=blk['kind'], sims=blk['sims'], paragraphs=paras, notes=notes),
              open(os.path.join(OUT, blk['id'] + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    for c in blk['sims']:
        if c in mb: index[c].append(blk['id'])
    tot['blocks'] += 1; tot['par_src'] += len(src); tot['par_out'] += len(paras); tot['notes_src'] += n_src_notes; tot['notes_out'] += len(notes); tot['replacements'] += cnt[0]; tot['bad_blocks'] += (not ok)
    report.append([blk['id'], blk['tom'], blk['kind'], ' '.join(map(str, blk['sims'])), len(src), len(paras), n_src_notes, len(notes), cnt[0], 'да' if ok else 'НЕТ: ' + str(bad[:3])])
json.dump({str(k): v for k, v in sorted(index.items())}, open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
with open(os.path.join(SITE, 'docs', '3_transfer_report.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f, delimiter=';'); w.writerow(['Блок', 'Том', 'Тип', 'Симаним', 'Абзацев в источнике', 'Абзацев в результате', 'Сносок в источнике', 'Сносок в результате', 'Замен Б-г/Г-сподь', 'Сверка пройдена']); w.writerows(report)
print(json.dumps(dict(tot), ensure_ascii=False)); print('глав сайта со слоем:', len(index), 'из', len(mb)); print('служебные блоки пропущены в:', skipped_service)
print('остатки (слова с «Бог/Господ» после замены):', dict(left))
print('главы сайта без материала:', sorted(mb - set(index)))
