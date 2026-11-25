# 粒子形状ディスクリプタ決定的検証: 既知の円/軸平行楥円/45°回転楥円でAR・長短軸・円形度・重心とCSV列を確認
import json, asyncio, math, urllib.request, websockets

def wsu():
    tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
    return [t for t in tabs if t['type']=='page' and '8642' in t['url']][0]['webSocketDebuggerUrl']

async def main():
    ws = await websockets.connect(wsu(), max_size=3*10**7); mid = 0
    async def cmd(m, **p):
        nonlocal mid; mid += 1
        await ws.send(json.dumps({'id':mid,'method':m,'params':p}))
        while True:
            r = json.loads(await ws.recv())
            if r.get('id')==mid: return r
    async def ev(e):
        msg = await cmd('Runtime.evaluate', expression=e, returnByValue=True)
        res = msg.get('result',{})
        if 'exceptionDetails' in res: return 'JS-ERR '+json.dumps(res['exceptionDetails'])[:400]
        return res.get('result',{}).get('value')
    async def poll_x(n=12):
        for _ in range(n):
            await asyncio.sleep(0.7)
            v = await ev("window.__x===undefined?null:JSON.stringify(window.__x)")
            if v is not None: return json.loads(v)
        return 'TIMEOUT'
    await cmd('Page.enable'); await cmd('Page.bringToFront')
    await cmd('Emulation.setDeviceMetricsOverride', width=1600, height=900, deviceScaleFactor=1, mobile=False)
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v=desc1')
    for _ in range(20):
        await asyncio.sleep(1)
        if await ev("!!window.areaStats"): break
    print('app loaded:', await ev("APP_VER"))
    # 合成: 円r=50@(200,200), 楕円a=100,b=40@(600,200), 45°回転楕円a=80,b=30@(400,420)
    await ev("""
      (() => {
        const c = document.createElement('canvas'); c.width=900; c.height=600;
        const g = c.getContext('2d');
        g.fillStyle='#000'; g.fillRect(0,0,900,600);
        g.fillStyle='#fff';
        g.beginPath(); g.arc(200,200,50,0,7); g.fill();
        g.beginPath(); g.ellipse(600,200,100,40,0,0,7); g.fill();
        g.beginPath(); g.ellipse(400,420,80,30,Math.PI/4,0,7); g.fill();
        video.srcObject = c.captureStream(30); video.play();
      })(); 'synth'
    """)
    for _ in range(15):
        await asyncio.sleep(1)
        if await ev("video.videoWidth"): break
    print('synth video:', await ev("video.videoWidth + 'x' + video.videoHeight"))
    # 粒子解析モード、全ROI、閾値128、明、最小50、フィルタなし
    print('mode:', await ev("document.getElementById('m-part').click(); mode"))
    stats = await ev("""
      (() => {
        thr=128; polarity='light'; minArea=50; bgRad=0; wtrOn=false; cirMin=0;
        areas=[{pts:[{x:0,y:0},{x:900,y:0},{x:900,y:600},{x:0,y:600}],key:curKey()}];
        areaStats();
        return JSON.stringify(areaComps.map(o=>({cx:Math.round(o.cx),cy:Math.round(o.cy),
          dEq:+o.dEqPx.toFixed(1),circ:+(o.circ*100).toFixed(1),ar:+o.ar.toFixed(2),
          major:+o.majorPx.toFixed(1),minor:+o.minorPx.toFixed(1)})));
      })()
    """)
    got = json.loads(stats)
    print(f'components n={len(got)} (期待3)')
    # 面積順(大→小): 楕円1(πab=12566) > 回転楕円2(πab=7540) > 円3(7854)... 実際は 楕円1>円>楕円2
    for o in got: print(' ', o)
    def near(a, b, tol): return abs(a-b) <= tol
    # 重心で識別
    byc = {(o['cx'],o['cy']): o for o in got}
    def find(x, y, tol=6):
        for o in got:
            if abs(o['cx']-x) <= tol and abs(o['cy']-y) <= tol: return o
        return None
    c1 = find(200,200); e1 = find(600,200); e2 = find(400,420)
    print('円@(200,200):', c1 and near(c1['ar'],1.0,0.06) and near(c1['dEq'],100,3) and 55<c1['circ']<70,
          '(AR≈1.0, dEq≈100, circ≈62%: 4連結デジタル周≈8rのため連続値1.0にはならない)')
    print('楕円a100b40:', e1 and near(e1['ar'],2.5,0.15) and near(e1['major'],200,6) and near(e1['minor'],80,6),
          '(AR≈2.5, 200/80)')
    print('45°楕円a80b30:', e2 and near(e2['ar'],8/3,0.18) and near(e2['major'],160,6) and near(e2['minor'],60,6),
          '(AR≈2.67, 160/60 — 回転不変)')
    # 円形度フィルタの回帰: cirMin=50で41%の回転楕円のみ除外→2個、99で全除外
    print('cirMin50 n:', await ev("cirMin=50; areaStats(); areaComps.length"), '(期待2)')
    print('cirMin99 n:', await ev("cirMin=99; areaStats(); areaComps.length"), '(期待0)')
    print('cirMin off:', await ev("cirMin=0; areaStats(); areaComps.length"), '(期待3)')
    # CSV: downloadCSVのblobを捕捉して列を確認
    await ev("""
      window.__csvs=[];
      const _cre=URL.createObjectURL.bind(URL);
      URL.createObjectURL=function(b){ try{ if(b.type&&b.type.indexOf('text/csv')===0) window.__csvs.push(b);}catch(e){} return _cre(b); };
      'hooked'
    """)
    await ev("outputAnalysisCSVs(); 'csv out'")
    await asyncio.sleep(1)
    await ev("""(async()=>{
      const b=window.__csvs.find(x=>true);
      if(!b){window.__x='no csv';return;}
      const t=await b.text();
      window.__x=t.split('\\n');
    })(); 'kicked'""")
    csv = await poll_x(10)
    print('CSV head:')
    if isinstance(csv, list):
        for ln in csv[:4]: print('  ', ln[:200])
        cols = csv[1] if len(csv)>1 else ''
        print('CSV columns ok:', all(k in cols for k in ['circularity_%','aspect_ratio','major_px','minor_px']), '(期待True)')
        print('CSV rows ok:', len(csv) >= 5, '(期待True: ヘッダ2+粒子3行)')
    # パネルのディスクリプタ表
    print('panel has table:', await ev("document.getElementById('partStats').textContent.includes('ディスクリプタ')"), '(期待True)')
    # 後片付け
    await ev("""(()=>{
      areas=[]; areaComps=[];
      thr=+(localStorage.getItem('area thr')||128); minArea=+(localStorage.getItem('area min')||50);
      cirMin=+(localStorage.getItem('area circ')||0);
      document.getElementById('m-dist').click();
      (async()=>{await start();})(); 'restore'
    })()""")
    for _ in range(8):
        await asyncio.sleep(2)
        if await ev("video.videoWidth"): break
    print('camera restored:', await ev("video.videoWidth"))
    await cmd('Emulation.clearDeviceMetricsOverride')
    await ws.close()

asyncio.run(main())
