#!/usr/bin/env python3
"""Синхронизация главного текста с оригиналом (оригинал только читается).
Запуск: python3 tools/sync.py <папка клона оригинала> <папка этого сайта>
Что делает:
  1. копирует content*.json, перечисленные в chapterFiles оригинала (новые, изменённые), удаляет исчезнувшие;
  2. переносит меню глав (index.html) и строку chapterFiles / подсказку поиска (app.js) из оригинала;
  3. пересобирает список офлайн-файлов в sw.js и меняет версию кэша, если что-то изменилось;
  4. обновляет original-manifest.json и docs/last-sync.md;
  5. если изменился остальной код/оформление оригинала (не главы) — пишет docs/ORIGINAL_CODE_CHANGED.md.
Текст Мишны Бруры не редактируется: файлы глав копируются байт в байт.
"""
import re, os, sys, json, glob, hashlib, subprocess, shutil, datetime
ORIG, SITE = sys.argv[1], sys.argv[2]
def rd(p): return open(p, encoding='utf-8').read()
def wr(p, s): open(p, 'w', encoding='utf-8', newline='').write(s)
def sha(b): return hashlib.sha256(b).hexdigest()
CF = re.compile(r'const chapterFiles=\{.*?\};', re.S)
PH = re.compile(r"^.*\$\('#searchInput'\)\.placeholder=.*$", re.M)
def menu_span(h):
    a = h.index('<div class="side-caption section-caption">'); b = h.index('<nav class="seif-nav"')
    return a, b

o_app, o_idx = rd(f'{ORIG}/app.js'), rd(f'{ORIG}/index.html')
cf_m = CF.search(o_app); ph_m = PH.search(o_app)
assert cf_m and ph_m, 'в app.js оригинала не найдены chapterFiles / подсказка поиска — формат изменился'
chap = {int(k): v for k, v in re.findall(r'(\d+):"(content\d*\.json)"', cf_m.group(0))}
files = sorted(set(chap.values()))
# --- проверка глав оригинала
for n, f in chap.items():
    d = json.load(open(f'{ORIG}/{f}', encoding='utf-8'))
    assert d.get('chapter') == n, f'{f}: номер главы {d.get("chapter")} ≠ {n}'
mf_path = f'{SITE}/original-manifest.json'
old = json.load(open(mf_path, encoding='utf-8')) if os.path.exists(mf_path) else {'files': {}, 'code': {}}
new_files = {f: sha(open(f'{ORIG}/{f}', 'rb').read()) for f in files}
added = [f for f in files if f not in old['files']]
changed = [f for f in files if f in old['files'] and old['files'][f] != new_files[f]]
removed = [f for f in old['files'] if f not in new_files]
def chnum(f): return next(k for k, v in chap.items() if v == f)
# --- копирование глав
for f in added + changed: shutil.copyfile(f'{ORIG}/{f}', f'{SITE}/{f}')
for f in removed:
    if os.path.exists(f'{SITE}/{f}'): os.remove(f'{SITE}/{f}')
# --- меню, chapterFiles, подсказка поиска
s_idx, s_app = rd(f'{SITE}/index.html'), rd(f'{SITE}/app.js')
a, b = menu_span(o_idx); sa, sb = menu_span(s_idx)
s_idx = s_idx[:sa] + o_idx[a:b] + s_idx[sb:]
assert CF.search(s_app) and PH.search(s_app)
s_app = CF.sub(lambda m: cf_m.group(0), s_app, count=1)
s_app = PH.sub(lambda m: ph_m.group(0), s_app, count=1)
# --- исправление названий в меню: если в оригинале вместо названия попал текст закона ({{א}}-метки или слишком длинная строка),
#     берём название из файла главы (оригинал не меняем)
def fix_menu_titles(h):
    def rep(m):
        n, label, small = int(m.group(1)), m.group(2), m.group(3)
        if '{{' not in label and len(label) <= 200: return m.group(0)
        f = chap.get(n)
        if not f: return m.group(0)
        t = json.load(open(f'{SITE}/{f}', encoding='utf-8')).get('title', '').strip()
        return m.group(0) if not t else m.group(0).replace(label, t.replace('&', '&amp;').replace('<', '&lt;'), 1)
    return re.sub(r'<button class="chapter-nav" data-chapter="(\d+)"[^>]*><span>\d+</span><span>(.*?)(<small[^>]*>.*?</small>)?</span></button>', rep, h, flags=re.S)
s_idx = fix_menu_titles(s_idx)
wr(f'{SITE}/index.html', s_idx); wr(f'{SITE}/app.js', s_app)
# --- контроль остального кода оригинала
code = {}
for p in sorted(glob.glob(f'{ORIG}/**/*', recursive=True)):
    if os.path.isdir(p): continue
    r = os.path.relpath(p, ORIG)
    if re.fullmatch(r'content\d*\.json', r) or r.startswith('.git') or r in ('sw.js', 'README.md'): continue
    if r == 'index.html': data = (o_idx[:a] + o_idx[b:]).encode()
    elif r == 'app.js': data = PH.sub('', CF.sub('', o_app)).encode()
    else: data = open(p, 'rb').read()
    code[r] = sha(data)
code_changed = sorted(r for r in set(code) | set(old.get('code', {})) if old.get('code') and code.get(r) != old['code'].get(r))
note = f'{SITE}/docs/ORIGINAL_CODE_CHANGED.md'
if code_changed:
    wr(note, '# Изменился код или оформление оригинала\n\nГлавы и меню перенесены автоматически, но в оригинале изменились эти файлы '
       '(они сюда НЕ перенесены):\n\n' + ''.join(f'- {r}\n' for r in code_changed) +
       '\nНапишите Claude «обнови» — он аккуратно перенесёт изменения, не повредив слой «Ялкут Йосеф».\n')
elif os.path.exists(note) and old.get('code'):
    os.remove(note)
# --- sw.js
sw = rd(f'{SITE}/sw.js')
m = re.search(r'const BASE=\[(.*?)\];', sw, re.S)
items = re.findall(r"'([^']*)'", m.group(1))
keep = [u for u in items if not re.fullmatch(r'content\d*\.json', u) and not u.startswith('yalkut/')]
yj = sorted('yalkut/' + os.path.basename(p) for p in glob.glob(f'{SITE}/yalkut/*.json')) if os.path.isdir(f'{SITE}/yalkut') else []
base = keep + yj + files
sw = sw[:m.start(1)] + ','.join("'%s'" % u for u in base) + sw[m.end(1):]
wr(f'{SITE}/sw.js', sw)
# --- манифест оригинала
try: commit = subprocess.check_output(['git', '-C', ORIG, 'rev-parse', 'HEAD'], text=True).strip(); cdate = subprocess.check_output(['git', '-C', ORIG, 'log', '-1', '--format=%cI'], text=True).strip()
except Exception: commit = cdate = ''
mf = {'original_repo': 'bu3142-lgtm/mishna-berura', 'original_commit': commit, 'original_commit_date': cdate, 'files': new_files, 'code': code}
wr(mf_path, json.dumps(mf, ensure_ascii=False, indent=1) + '\n')
# итог для следующих шагов
json.dump({'added': [chnum(f) for f in added], 'changed': [chnum(f) for f in changed], 'removed': removed, 'code_changed': code_changed},
          open(f'{SITE}/.sync-result.json', 'w'))
print('добавлены главы:', sorted(chnum(f) for f in added) or '—')
print('изменены главы:', sorted(chnum(f) for f in changed) or '—')
print('удалены файлы:', removed or '—')
print('изменился код оригинала:', code_changed or '—')
