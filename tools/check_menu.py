"""Клик по каждой кнопке меню: открывается нужная глава; нет undefined; нет горизонтальной прокрутки. Аргументы: устройство sw|nosw"""
import sys,re
from playwright.sync_api import sync_playwright
dev,mode=sys.argv[1],sys.argv[2]
URL='http://localhost:8767/index.html'
import json;IDX=json.load(open('/home/claude/newsite/yalkut/index.json'));fails=[];n=0
with sync_playwright() as p:
    b=p.chromium.launch();c=b.new_context(**p.devices[dev],service_workers='allow' if mode=='sw' else 'block');pg=c.new_page()
    errs=[];pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(URL);pg.wait_for_timeout(1500)
    if mode=='sw': pg.reload();pg.wait_for_timeout(1500)
    chapters=pg.evaluate('[...document.querySelectorAll("[data-chapter]")].map(b=>Number(b.dataset.chapter))')
    # порядок в меню строго по возрастанию внутри разделов
    for ch in chapters:
        n+=1
        try:
            pg.evaluate('document.getElementById("homePage")&&0')
            if not pg.evaluate('document.getElementById("sidebar").classList.contains("open")'): pg.click('#menuBtn')
            pg.wait_for_timeout(60)
            pg.evaluate(f'document.querySelector(\'[data-chapter="{ch}"]\').scrollIntoView({{block:"center"}})')
            pg.click(f'[data-chapter="{ch}"]',timeout=5000)
            try: pg.wait_for_function(f'document.getElementById("chapterCrumb").textContent.trim()==="{ch}"',timeout=8000)
            except Exception: pass
            want=str(ch) in IDX
            try: pg.wait_for_function(f'!document.getElementById("layerTabs").hidden==={str(want).lower()}',timeout=8000)
            except Exception: pass
            crumb=pg.inner_text('#chapterCrumb').strip()
            txt=pg.inner_text('#chapterPage')
            if crumb!=str(ch): fails.append((ch,'crumb '+crumb))
            elif 'undefined' in txt or '[object' in txt or '{{' in txt: fails.append((ch,'undefined/маркер'))
            elif len(pg.inner_text('#reader').strip())<50: fails.append((ch,'пустой пункт'))
            elif pg.evaluate('document.documentElement.scrollWidth>innerWidth+1'): fails.append((ch,'гориз. прокрутка'))
            elif (str(ch) in IDX)!=pg.is_visible('#layerTabs'): fails.append((ch,'вкладки слоя'))
        except Exception as e: fails.append((ch,'исключение '+str(e)[:60]))
    b.close()
print(dev,mode,'глав',n,'ошибок',len(fails),fails[:10],'js-ошибок',errs[:3])
