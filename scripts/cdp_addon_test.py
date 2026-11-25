import json, asyncio, time, urllib.request, websockets
results=[]
def wsu():
    tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
    return [t for t in tabs if t['type']=='page' and '8642' in t['url']][0]['webSocketDebuggerUrl']
async def main():
    ws = await websockets.connect(wsu(), max_size=3*10**7); mid=0
    async def cmd(m, **p):
        nonlocal mid; mid+=1
        await ws.send(json.dumps({'id':mid,'method':m,'params':p}))
        while True:
            r=json.loads(await ws.recv())
            if r.get('id')==mid: return r
    async def ev(e):
        msg=await cmd('Runtime.evaluate', expression=e, returnByValue=True)
        res=msg.get('result',{})
        if 'exceptionDetails' in res: return 'JS-ERR '+json.dumps(res['exceptionDetails'])[:300]
        return res.get('result',{}).get('value')
    def ok(name, cond, detail=''):
        print(('OK  ' if cond else 'NG  ')+name+((' | '+str(detail)) if detail else ''))
        if not cond: results.append(name)

    await cmd('Page.enable')
    await cmd('Emulation.setDeviceMetricsOverride', width=1600, height=900, deviceScaleFactor=1, mobile=False)
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v='+str(int(time.time())))
    for _ in range(20):
        await asyncio.sleep(1)
        if await ev("!!window.focusMetric && !!window.makeReport && !!window.tincStop") is True: break
    if await ev("!!window.focusMetric") is not True:
        print('FAIL: アプリ読み込み失敗'); return
    hh = await ev("[...document.querySelectorAll('.hrow')].map(r=>Math.round(r.getBoundingClientRect().height))")
    ok('1600pxでヘッダー2行', isinstance(hh,list) and len(hh)==2 and all(h<120 for h in hh), hh)
    # メニュー配置(ポップアップ: ヘッダー行数に影響しない)
    menus = await ev("""(() => { const q=id=>!!document.getElementById(id);
      return {cmpfile:q('cmpfile'),tinc:q('tinc'),repexp:q('repexp'),segmode:q('segmode')}; })()""")
    ok('新規UI要素すべて存在', all(menus.values()), menus)
    await ev("window.__raf0 = window.requestAnimationFrame; window.requestAnimationFrame = () => 0; video.requestVideoFrameCallback = () => 0;")
    for _ in range(15):
        await asyncio.sleep(1)
        if await ev("video.videoWidth > 0") is True: break
    # 合成シーン: オリーブ背景+青円3(色相約225°)。F4用に市松も生成
    await asyncio.sleep(3)
    for attempt in range(4):
        await ev("""(() => {
          const c = document.createElement('canvas'); c.width=800; c.height=600;
          window.__c=c; window.__g=c.getContext('2d');
          window.__scene = (blur) => {
            const g=window.__g; g.filter = blur ? 'blur(6px)' : 'none';
            g.fillStyle='rgb(150,150,60)'; g.fillRect(0,0,800,600);
            g.fillStyle='rgb(60,90,200)';
            for (const [x,y,r] of [[150,150,30],[400,300,40],[650,450,50]]) {
              g.beginPath(); g.arc(x,y,r,0,7); g.fill();
            }
            g.filter='none';
          };
          window.__checker = (blur) => {
            const g=window.__g; g.filter = blur ? 'blur(6px)' : 'none';
            for(let y=0;y<600;y+=16)for(let x=0;x<800;x+=16){
              g.fillStyle=((x/16+y/16)%2)?'#fff':'#111'; g.fillRect(x,y,16,16);
            }
            g.filter='none';
          };
          window.__checker(false);
          video.srcObject = c.captureStream(30); video.play();
        })(); 'synth'""")
        for _ in range(10):
            await asyncio.sleep(1)
            if await ev("video.videoWidth === 800") is True: break
        await asyncio.sleep(2)
        if await ev("video.videoWidth === 800") is True: break
        print('   synth差し替え再試行', attempt+1)
    ok('合成ストリーム800x600', await ev("video.videoWidth === 800") is True)
    async def wait_frame():  # 現canvas内容のフレーム到着待ち(中心画素で判定)
        tgt = await ev("""(() => { const g=window.__g; const d=g.getImageData(400,300,1,1).data; return [d[0],d[1],d[2]]; })()""")
        for _ in range(60):
            p = await ev("""(() => { const c=document.createElement('canvas'); c.width=800; c.height=600;
              const g=c.getContext('2d'); g.drawImage(video,0,0); const d=g.getImageData(400,300,1,1).data; return [d[0],d[1],d[2]]; })()""")
            if all(abs(a-b)<=2 for a,b in zip(p,tgt)): return True
            await asyncio.sleep(0.1)
        print('   wait_frame last=%r target=%r' % (p,tgt))
        return False

    # ===== F4: フォーカス支援(鋭→ぼけで指標が下がる) =====
    await asyncio.sleep(1)
    ok('市松(鋭)フレーム到着', await wait_frame())
    fsharp = await ev("focusMetric()")
    await ev("window.__checker(true); 'blur'")
    ok('市松(ぼけ)フレーム到着', await wait_frame())
    fblur = await ev("focusMetric()")
    ok('F4: 鋭>ぼけ(3倍以上)', isinstance(fsharp,int) and isinstance(fblur,int) and fsharp >= fblur*3+10, (fsharp, fblur))
    bar = await ev("focusBar(100)")
    ok('F4: フォーカスバー生成', isinstance(bar,str) and len(bar)==9 and bar.count('▰')>0, bar)

    # ===== F2/F3: 粒子解析(色相区分)+統計サマリ =====
    await ev("window.__scene(false); 'scene'")
    ok('カラーシーンフレーム到着', await wait_frame())
    await ev("calMap={}; localStorage.setItem('micro-cal','{}');")  # 未較正=px表記で検証決定化
    await ev("document.getElementById('m-part').click();")
    await asyncio.sleep(0.5)
    # 輝度モード(閾値128明): 背景(輝度~134)が1成分になり青円は検出されない
    lumres = await ev("""(() => {
      segMode='lum'; thr=128; polarity='light'; minArea=50; bgRad=0; wtrOn=false; cirMin=0;
      areas=[{pts:[{x:0,y:0},{x:800,y:0},{x:800,y:600},{x:0,y:600}],key:curKey()}];
      areaStats();
      return JSON.stringify({n:areaComps.length, big:areaComps.length?Math.round(areaComps[0].areaPx):0});
    })()""")
    lr = json.loads(lumres)
    ok('F3対照: 輝度モードでは背景1成分', lr['n']==1 and lr['big']>400000, lr)
    # 色相モード: 青(h≈225)±40、彩度≥25 → 円3個
    hueres = await ev("""(() => {
      segMode='hue'; hueC=225; hueTol=40; satMin=25;
      areaStats();
      return JSON.stringify({n:areaComps.length, ds:areaComps.map(o=>+o.dEqPx.toFixed(1)).sort((a,b)=>a-b)});
    })()""")
    hr = json.loads(hueres)
    ok('F3: 色相区分で青円3個検出', hr['n']==3, hr)
    ok('F3: 粒径が設計値(60/80/100±6)', len(hr['ds'])==3 and all(abs(a-b)<=6 for a,b in zip(hr['ds'],[60,80,100])), hr['ds'])
    import re as _re
    stats_txt = await ev("$('partStats').textContent")
    m = _re.search(r'中央値\s*([\d.]+)\s*px', stats_txt or '')
    ok('F2: パネルに中央値・四分位', m is not None and 74<=float(m.group(1))<=86 and '四分位' in (stats_txt or '') and '円形度中央値' in (stats_txt or ''),
       (m.group(0) if m else None))
    await ev("segMode='lum'; areas=[]; areaComps=[];")

    # ===== F1: 比較モード Referenceファイル読み込み =====
    await ev("setCmp(false);")
    await ev("""(() => {
      const c=document.createElement('canvas'); c.width=400; c.height=300;
      const g=c.getContext('2d'); g.fillStyle='rgb(150,150,150)'; g.fillRect(0,0,400,300);
      const b64=c.toDataURL('image/png').split(',')[1];
      const bin=atob(b64), u8=new Uint8Array(bin.length);
      for(let i=0;i<bin.length;i++)u8[i]=bin.charCodeAt(i);
      const f=new File([u8],'ref.png',{type:'image/png'});
      const dt=new DataTransfer(); dt.items.add(f);
      const inp=document.getElementById('cmppicfile'); inp.files=dt.files;
      inp.dispatchEvent(new Event('change',{bubbles:true}));
    })(); 'reffile'""")
    refok=False
    for _ in range(30):
        await asyncio.sleep(0.2)
        st = await ev("""(() => ({on:cmpOn, w:cmpRefW, l0:cmpRefLum?Math.round(cmpRefLum[0]):-1}))()""")
        if st['on'] and st['w']==800: refok=True; break
    ok('F1: ファイルからReference設定(400x300→800x600に伸長)', refok and abs(st['l0']-150)<=2, st)
    await ev("setCmp(false);")

    # ===== F5: 間隔静止画 =====
    await ev("$('tintv').value='5'; $('tincnt').value='10'; $('tinc').click();")
    await asyncio.sleep(6.5)
    t1 = await ev("({n:tincN, on:!!tincT})")
    ok('F5: 5秒間隔で2枚以上撮影', t1['n']>=2 and t1['on'], t1)
    await ev("$('tinc').click();")
    t2 = await ev("({n:tincN, on:!!tincT, btn:$('tinc').textContent})")
    ok('F5: 停止でタイマー解除', not t2['on'] and t2['btn']=='画像間隔撮影を開始', t2)

    # ===== F6: レポート出力 =====
    html = await ev("""makeReport('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')""")
    ok('F6: HTMLレポート生成(セクション完備)',
       isinstance(html,str) and 'CxM Image レポート' in html and '解析結果' in html and '解析条件(JSON)' in html and 'data:image/png;base64' in html,
       len(html) if isinstance(html,str) else html)

    # 後始末
    await ev("""(() => { window.requestAnimationFrame = window.__raf0; (async()=>{await start();})(); })(); 'restore'""")
    await asyncio.sleep(3)
    print('ALL PASS' if not results else 'FAILURES: '+str(results))
    await ws.close()
asyncio.run(main())
