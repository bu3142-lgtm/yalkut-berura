"""Проверка слоя «Ялкут Йосеф» во всех главах: абзацы, сноски (каждая открывается и показывает свой текст), вёрстка. Аргумент: устройство."""
import sys,json,re
from playwright.sync_api import sync_playwright
dev=sys.argv[1];SITE='/home/claude/newsite/';URL='http://localhost:8767/index.html'
idx=json.load(open(SITE+'yalkut/index.json',encoding='utf-8'))
fails=[];stats=dict(chapters=0,paragraphs=0,notes=0)
with sync_playwright() as p:
    b=p.chromium.launch();c=b.new_context(**p.devices[dev],service_workers='block');pg=c.new_page()
    errs=[];pg.on('pageerror',lambda e:errs.append(str(e)));pg.on('console',lambda m:errs.append(m.text) if m.type=='error' else None)
    for ch,ids in idx.items():
        blocks=[json.load(open(SITE+f'yalkut/{i}.json',encoding='utf-8')) for i in ids]
        exp_p=sum(len(x['paragraphs']) for x in blocks);exp_n=[n for x in blocks for n in x['notes']]
        try:
            pg.goto(f'{URL}?chapter={ch}&layer=yj');pg.wait_for_function('document.querySelectorAll(".yj-para").length>0',timeout=8000)
            got_p=pg.evaluate('document.querySelectorAll(".yj-para").length');got_n=pg.evaluate('document.querySelectorAll("button.yn").length')
            if got_p!=exp_p: fails.append((ch,f'абзацев {got_p}≠{exp_p}'))
            if got_n!=len(exp_n): fails.append((ch,f'сносок {got_n}≠{len(exp_n)}'))
            txt=pg.inner_text('#yalkutPage')
            if re.search(r'undefined|\[object|\{\{|\}\}|NaN',txt): fails.append((ch,'мусор в тексте'))
            if not pg.is_visible('#layerTabs'): fails.append((ch,'нет вкладок'))
            if pg.evaluate('document.documentElement.scrollWidth>innerWidth+1'): fails.append((ch,'гориз. прокрутка'))
            if pg.evaluate('[...document.querySelectorAll(".yj-para")].some(e=>e.innerText.trim().length<3)'): fails.append((ch,'пустой абзац'))
            if pg.evaluate('/\\bБог(а|у|ом|е)?\\b|\\bГосподь\\b/.test(document.getElementById("yalkutPage").innerText)'): fails.append((ch,'остался «Бог/Господь»'))
            # все сноски: открыть и сравнить с JSON
            res=pg.evaluate('''()=>{const out=[];const ns=yj.notes;for(let i=0;i<ns.length;i++){openYalkutNote(ns[i].i,ns[i].block);out.push(document.getElementById("yalkutNoteContent").innerText.replace(/\\u00ad/g,"").trim())}document.getElementById("yalkutDialog").close();return out}''')
            bad=[i+1 for i,(r,e) in enumerate(zip(res,exp_n)) if re.sub(r'\s+',' ',r)!=re.sub(r'\s+',' ',e).strip()]
            if bad or len(res)!=len(exp_n): fails.append((ch,f'сноски не совпали {bad[:5]}'))
            stats['chapters']+=1;stats['paragraphs']+=got_p;stats['notes']+=len(res)
        except Exception as e: fails.append((ch,'исключение '+str(e)[:80]))
    # главы без слоя: вкладок нет
    for ch in (2,41,43,451):
        pg.goto(f'{URL}?chapter={ch}');pg.wait_for_timeout(700)
        if pg.is_visible('#layerTabs') != (str(ch) in idx): fails.append((ch,'вкладки не по индексу'))
    b.close()
print(dev,stats,'ошибок',len(fails),fails[:12],'js-ошибок',errs[:3])
