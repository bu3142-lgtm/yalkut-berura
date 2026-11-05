#!/usr/bin/env python3
"""После sync.py и build_all.py: проверки, версия кэша, отчёт docs/last-sync.md. Запуск: python3 tools/finish.py <папка сайта>"""
import re, os, json, glob, hashlib, datetime, sys
SITE = sys.argv[1]
rd = lambda p: open(os.path.join(SITE, p), encoding='utf-8').read()
res = json.load(open(f'{SITE}/.sync-result.json')); os.remove(f'{SITE}/.sync-result.json')
app, idx, sw = rd('app.js'), rd('index.html'), rd('sw.js')
chap = {int(k): v for k, v in re.findall(r'(\d+):"(content\d*\.json)"', re.search(r'const chapterFiles=\{.*?\};', app, re.S).group(0))}
menu = {int(x) for x in re.findall(r'class="chapter-nav" data-chapter="(\d+)"', idx)}
errs = []
if set(chap) != menu: errs.append(f'меню и chapterFiles не совпадают: {sorted(set(chap) ^ menu)}')
for n, f in chap.items():
    if not os.path.exists(f'{SITE}/{f}') or json.load(open(f'{SITE}/{f}', encoding='utf-8')).get('chapter') != n: errs.append(f'глава {n}: файл {f}')
base = re.findall(r"'([^']*)'", re.search(r'const BASE=\[(.*?)\];', sw, re.S).group(1))
for u in base:
    if not os.path.exists(os.path.join(SITE, u.split('?')[0])) and u != './': errs.append('нет файла из sw.js: ' + u)
yi = json.load(open(f'{SITE}/yalkut/index.json', encoding='utf-8')) if os.path.exists(f'{SITE}/yalkut/index.json') else {}
for k, ids in yi.items():
    if int(k) not in chap: errs.append(f'Ялкут: симан {k} отсутствует на сайте')
    for i in ids:
        if not os.path.exists(f'{SITE}/yalkut/{i}.json'): errs.append(f'нет yalkut/{i}.json')
if errs: print('\n'.join(errs)); sys.exit(1)
# версия кэша = хэш содержимого всего, что кэшируется
h = hashlib.sha1()
for u in base:
    p = os.path.join(SITE, u.split('?')[0])
    if os.path.isfile(p): h.update(open(p, 'rb').read())
h.update(re.sub(r"const CACHE='[^']*';", '', sw).encode()[:0])
sw2 = re.sub(r"const CACHE='mb-yj-v(\d+)[^']*';", lambda m: f"const CACHE='mb-yj-v{m.group(1)}-{h.hexdigest()[:8]}';", sw, count=1)
open(f'{SITE}/sw.js', 'w', encoding='utf-8', newline='').write(sw2)
no_yj = sorted(n for n in chap if str(n) not in yi)
lines = [f'# Последняя синхронизация с оригиналом', '', datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'), '',
         f'- Глав на сайте: {len(chap)}; со слоем «Ялкут Йосеф»: {len(chap) - len(no_yj)}']
for t, k in (('Добавлено', 'added'), ('Изменено', 'changed')):
    v = sorted(res[k]); lines.append(f'- {t} глав: ' + (', '.join(f'{n} ({"есть Ялкут Йосеф" if str(n) in yi else "без Ялкут Йосеф"})' for n in v) or '—'))
lines.append('- Удалено файлов: ' + (', '.join(res['removed']) or '—'))
if res['code_changed']: lines.append('- ВНИМАНИЕ: изменился код/оформление оригинала (см. docs/ORIGINAL_CODE_CHANGED.md)')
lines += ['', 'Главы без слоя «Ялкут Йосеф»: ' + ', '.join(map(str, no_yj))]
if res['added'] or res['changed'] or res['removed'] or res['code_changed'] or not os.path.exists(f'{SITE}/docs/last-sync.md'):
    open(f'{SITE}/docs/last-sync.md', 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
