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
    await cmd('Runtime.evaluate', expression="localStorage.removeItem('cmp thr')")
    await cmd('Emulation.setDeviceMetricsOverride', width=1600, height=900, deviceScaleFactor=1, mobile=False)
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v='+str(int(time.time())))
    for _ in range(20):
        await asyncio.sleep(1)
        if await ev("!!window.cmpCapture && !!window.cmpDraw") is True: break
    if await ev("!!window.cmpCapture") is not True:
        print('FAIL: アプリ読み込み失敗'); return
    # ヘッダー2行(1600px)確認
    hh = await ev("[...document.querySelectorAll('.hrow')].map(r=>Math.round(r.getBoundingClientRect().height))")
    ok('1600pxでヘッダー2行', isinstance(hh,list) and len(hh)==2 and all(h<120 for h in hh), hh)
    # rAF/rVFC停止(テストがcmpDraw/cmpDiffを直接駆動)
    await ev("window.__raf0 = window.requestAnimationFrame; window.requestAnimationFrame = () => 0; video.requestVideoFrameCallback = () => 0;")
    for _ in range(15):
        await asyncio.sleep(1)
        if await ev("video.videoWidth > 0") is True: break
    async def vidpx():
        return await ev("""(() => { const c=document.createElement('canvas'); c.width=800; c.height=600;
          const g=c.getContext('2d'); g.drawImage(video,0,0); return g.getImageData(400,300,1,1).data[0]; })()""")
    async def wait_vid(v, x=400, y=300):
        for _ in range(60):
            xx = await ev("""(() => { const c=document.createElement('canvas'); c.width=800; c.height=600;
              const g=c.getContext('2d'); g.drawImage(video,0,0); return g.getImageData(%d,%d,1,1).data[0]; })()""" % (x,y))
            if xx==v: return True
            await asyncio.sleep(0.1)
        return False
    # 合成ストリーム(カメラstart完了待ちのうえ差し替え、再試行付き)
    await asyncio.sleep(3)
    for attempt in range(4):
        await ev("""(() => {
          const c = document.createElement('canvas'); c.width=800; c.height=600;
          window.__c=c; window.__g=c.getContext('2d');
          window.__fill = (v) => { const g=window.__g; g.fillStyle='rgb('+v+','+v+','+v+')'; g.fillRect(0,0,800,600); };
          window.__rect = () => { const g=window.__g; g.fillStyle='rgb(255,255,255)'; g.fillRect(100,100,200,200); };
          window.__g.fillStyle='rgb(100,100,100)'; window.__g.fillRect(0,0,800,600);
          video.srcObject = c.captureStream(30); video.play();
        })(); 'synth'""")
        for _ in range(10):
            await asyncio.sleep(1)
            if await ev("video.videoWidth === 800") is True: break
        await asyncio.sleep(2)
        if await ev("video.videoWidth === 800") is True and await vidpx()==100:
            break
        print('   synth差し替え再試行', attempt+1)
    ok('合成100安定', await wait_vid(100))

    # メニュー開閉(ボタンクリック→項目確認→外側クリックで閉)
    await ev("$('cmpbtn').click();")
    disp = await ev("$('cmpmenu').style.display")
    items = await ev("[...$('cmpmenu').querySelectorAll('button')].map(b=>b.id)")
    ok('cmpmenu表示', disp=='flex', disp)
    ok('menu項目', 'cmpcap' in items and 'cmsoff' in items, items)
    await ev("""(() => { const ev2=new PointerEvent('pointerdown',{bubbles:true}); document.body.dispatchEvent(ev2); })();""")
    ok('外側クリックで閉', await ev("$('cmpmenu').style.display")=='none')

    # 基準固定(ボタン経由)
    await ev("$('cmpcap').click();")
    st = await ev("JSON.stringify({on:cmpOn, disp:$('cmpcv').style.display, btn:$('cmpbtn').classList.contains('on'), refW:cmpRefW})")
    ok('固定開始', '"on":true' in st and '"block"' in st and '"refW":800' in st, st)

    # 同一フレーム → 差分0
    await ev("cmpDiff(); 'd'")
    c0 = await ev("cmpCount")
    ok('同一フレーム差分0', c0==0, c0)

    # 全面150 → 全ブロック差分(800/16=50 × ceil(600/16)=38 = 1900)
    await ev("window.__fill(150); 'd150'")
    ok('150フレーム到着', await wait_vid(150))
    await ev("cmpDiff(); 'd'")
    c1 = await ev("cmpCount")
    ok('全面変化=全ブロック検出', c1>=1890, c1)
    await ev("window.__fill(100); 'd100'")
    ok('100復帰', await wait_vid(100))
    await ev("cmpDiff(); 'd'")
    ok('復帰後差分0', await ev("cmpCount")==0)

    # 部分変化: (100,100)-(300,300)に白矩形 → マークは矩形周辺のみ
    await ev("window.__rect(); 'rect'")
    ok('矩形フレーム到着', await wait_vid(255, 200, 200))
    await ev("cmpDiff(); 'd'")
    c2 = await ev("cmpCount")
    bb = await ev("(() => { let x1=1e9,y1=1e9,x2=-1,y2=-1; for(const m of cmpMarks){x1=Math.min(x1,m.x);y1=Math.min(y1,m.y);x2=Math.max(x2,m.x);y2=Math.max(y2,m.y);} return {x1,y1,x2,y2}; })()")
    # 矩形と交差するブロック: x,yブロック6..19 → 最大196、理論156+境界
    ok('部分差分の件数範囲', 100<=c2<=210, c2)
    ok('マークは矩形周辺のみ', bb['x1']>=96 and bb['x2']<=304 and bb['y1']>=96 and bb['y2']<=304, bb)

    # 閾値200 → 差分155は検出されない
    await ev("$('cmthr').value='200'; $('cmthr').oninput(); cmpDiff(); 't'")
    ok('閾値200で0件', await ev("cmpCount")==0, await ev("cmpCount"))
    ok('閾値永続化', await ev("localStorage.getItem('cmp thr')")=='200')
    await ev("$('cmthr').value='40'; $('cmthr').oninput(); cmpDiff(); 't'")
    ok('閾値40で再検出', await ev("cmpCount")>100)

    # 比較ビューの描画確認(左=Reference/右=Sampleの配置+仕切り+マーク画素)
    await ev("window.__fill(100); 'd100'")
    ok('100復帰(再基準)', await wait_vid(100))
    await ev("cmpCapture(); 'recap'")  # 基準=100で取り直し
    await ev("window.__fill(150); 'd150'")
    if not await wait_vid(150):
        await ev("window.__fill(151); 'd151'")  # 配信が止まった場合再トリガ
        ok('150フレーム到着(再トリガ)', await wait_vid(151, 400, 300))
    else:
        ok('150フレーム到着', True)
    await ev("$('cmthr').value='255'; $('cmthr').oninput(); cmpDiff(); cmpDraw(); 'draw-clean'")
    px = await ev("""(() => { const cv=$('cmpcv'); const g=cv.getContext('2d');
      const W=cv.width,H=cv.height,half=Math.floor(W/2);
      const L=g.getImageData(Math.floor(half/2),Math.floor(H/2),1,1).data;
      const R=g.getImageData(Math.floor(half+half/2),Math.floor(H/2),1,1).data;
      const sep=g.getImageData(half,Math.floor(H/2),1,1).data;
      return {L:L[0],R:R[0],sepG:sep[1]}; })()""")
    ok('左=Reference(100)/右=Sample(150)+仕切り', abs(px['L']-100)<=1 and abs(px['R']-150)<=2 and px['sepG']>80, px)
    # マーク画素(矩形中心対応位置)にマゼンタ
    await ev("$('cmthr').value='40'; $('cmthr').oninput(); cmpDiff(); cmpDraw(); 'draw-marks'")
    mk = await ev("""(() => { const cv=$('cmpcv'); const g=cv.getContext('2d');
      const W=cv.width,H=cv.height,half=Math.floor(W/2);
      const iw=800,ih=600,s=Math.min((half-4)/iw,(H-24)/ih),ox=2+(half-4-iw*s)/2,oy=12+(H-24-ih*s)/2;
      const d=g.getImageData(Math.floor(ox+97*s),Math.floor(oy+97*s),1,1).data;
      return {r:d[0],g:d[1],b:d[2]}; })()""")
    ok('差分マーク描画(マゼンタ)', mk['r']>150 and mk['b']>150 and mk['g']<100, mk)

    # スクリーンショット(視覚確認用)
    import base64
    try:
        shot = await asyncio.wait_for(cmd('Page.captureScreenshot', format='png'), 30)
        open('W:/hermes/apps/microscope-viewer/scripts/cmp_view.png','wb').write(base64.b64decode(shot['result']['data']))
        print('   screenshot: scripts/cmp_view.png')
    except Exception as e2:
        print('   screenshot skip:', e2)

    # 比較終了
    await ev("$('cmsoff').click();")
    st2 = await ev("JSON.stringify({on:cmpOn, disp:$('cmpcv').style.display, btn:$('cmpbtn').classList.contains('on')})")
    ok('比較終了', '"on":false' in st2 and '"none"' in st2 and '"btn":false' in st2, st2)

    # 解像度変更での自動終了(合成→別サイズ)
    await ev("$('cmpcap').click();")
    await ev("""(() => { const c=document.createElement('canvas'); c.width=640; c.height=480;
      const g=c.getContext('2d'); g.fillStyle='rgb(100,100,100)'; g.fillRect(0,0,640,480);
      video.srcObject=c.captureStream(30); video.play(); })(); 'resize'""")
    for _ in range(10):
        await asyncio.sleep(1)
        if await ev("video.videoWidth === 640") is True: break
    await ev("cmpDraw(); 'd'")
    ok('ソースサイズ変更で自動終了', await ev("cmpOn") is False)

    # 後始末
    await ev("""(() => {
      localStorage.removeItem('cmp thr');
      window.requestAnimationFrame = window.__raf0;
      (async()=>{await start();})();
    })(); 'restore'""")
    await asyncio.sleep(3)
    print('ALL PASS' if not results else 'FAILURES: '+str(results))
    await ws.close()
asyncio.run(main())
