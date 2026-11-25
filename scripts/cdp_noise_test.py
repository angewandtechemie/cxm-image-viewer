# ノイズ低減(中央値/ガウシアン)決定的検証: JS側は既知ピクセルで厳密値、GL側は同一値(±3)、粒子誤検出除去、UI同期
import json, asyncio, urllib.request, websockets

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
    async def jspx(x, y):  # 解析経路(drawSrcToned)の画素値
        return await ev(f"""(() => {{
          const c=document.createElement('canvas'); c.width=video.videoWidth; c.height=video.videoHeight;
          const g=c.getContext('2d'); drawSrcToned(g,c.width,c.height);
          return g.getImageData({x},{y},1,1).data[0]; }})()""")
    async def glpx(x, y):  # 表示GL(fx)の画素値(動画座標→fx座標へスケール)
        await ev(f"""(async()=>{{
          const c=document.createElement('canvas'); c.width=fx.width; c.height=fx.height;
          const g=c.getContext('2d'); g.drawImage(fx,0,0);
          const sx=fx.width/video.videoWidth, sy=fx.height/video.videoHeight;
          window.__x=[...g.getImageData(Math.round({x}*sx),Math.round({y}*sy),1,1).data];
        }})(); 'k'""")
        return await poll_x()
    await cmd('Page.enable'); await cmd('Page.bringToFront')
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v=noise1')
    for _ in range(20):
        await asyncio.sleep(1)
        if await ev("!!window.drawSrcToned"): break
    print('app loaded:', await ev("APP_VER"))
    # カメラ起動(start()非同期)を先に完了させ、その後に合成ストリームへ差し替える(競合回避)
    for _ in range(15):
        await asyncio.sleep(1)
        if await ev("video.videoWidth > 0"): break
    print('camera up:', await ev("video.videoWidth"))
    # 合成: 灰100背景、(400,300)に単一白画素、(600,100,80x80)白矩形の中央(640,140)に単一黒画素
    await ev("""
      (() => {
        const c = document.createElement('canvas'); c.width=800; c.height=600;
        const g = c.getContext('2d');
        g.fillStyle='rgb(100,100,100)'; g.fillRect(0,0,800,600);
        g.fillStyle='#fff'; g.fillRect(400,300,1,1);
        g.fillRect(600,100,80,80);
        g.fillStyle='#000'; g.fillRect(640,140,1,1);
        video.srcObject = c.captureStream(30); video.play();
        window.__synth = true;
      })(); 'synth'
    """)
    for _ in range(10):
        await asyncio.sleep(1)
        if await ev("video.videoWidth === 800"): break
    print('synth:', await ev("video.videoWidth+'x'+video.videoHeight"), 'fx:', await ev("fx.width+'x'+fx.height"))
    print('--- ベースライン(noise=0) ---')
    print('単一白:', await jspx(400,300), '(期待255)  矩形内黒:', await jspx(640,140), '(期待0)')
    print('--- ガウシアン: 3x3加重[121/2442/121]/16の厳密値 ---')
    await ev("$('n2').click(); tone.noise")
    checks = [((400,300),139,'中心 (12*100+4*255)/16=138.75→139'),
              ((400,299),119,'上隣 (14*100+2*255)/16=119.375→119'),
              ((399,299),110,'斜め (15*100+255)/16=109.69→110')]
    for (x,y),exp,note in checks:
        got = await jspx(x,y)
        print(f'  ({x},{y})={got} 期待{exp} {note}', 'OK' if abs(got-exp)<=1 else 'NG')
    print('--- 中央値: 単一外れ値の除去 ---')
    await ev("$('n1').click(); tone.noise")
    w = await jspx(400,300); b = await jspx(640,140)
    print(f'  単一白→{w}(期待100) 矩形内黒→{b}(期待255)', 'OK' if w==100 and b==255 else 'NG')
    print('  矩形内(620,120)=', await jspx(620,120), '(期待255: 中央値は塊を保つ)')
    print('--- GL表示側との一致(中央値) ---')
    await asyncio.sleep(1.5)  # setTone→applyFilters→rAFレンダリング1フレーム待つ
    g1 = await glpx(400,300); g2 = await glpx(620,120); g3 = await glpx(100,500)
    print(f'  GL単一白={g1[0]}(期待≈100) GL矩形内={g2[0]}(期待≈255) GL背景={g3[0]}(期待≈100)',
          'OK' if abs(g1[0]-100)<=3 and abs(g2[0]-255)<=3 and abs(g3[0]-100)<=3 else 'NG')
    print('--- GL表示側との一致(ガウシアン) ---')
    await ev("$('n2').click(); tone.noise")
    await asyncio.sleep(1.5)
    g4 = await glpx(400,300)
    print(f'  GL単一白近傍領域={g4[0]} (JS値139と±4以内ならOK)', 'OK' if abs(g4[0]-139)<=4 else 'NG')
    print('--- 粒子誤検出低減: 2x2白斑12個、minArea=2 ---')
    await ev("""
      (() => {
        const c = document.createElement('canvas'); c.width=800; c.height=600;
        const g = c.getContext('2d');
        g.fillStyle='#000'; g.fillRect(0,0,800,600);
        g.fillStyle='#fff';
        for (let i=0;i<12;i++) g.fillRect(100+i*50, 200+(i%3)*100, 2, 2);
        video.srcObject = c.captureStream(30); video.play();
      })(); 'synth2'
    """)
    await asyncio.sleep(2)
    await ev("""
      (() => {
        document.getElementById('m-part').click();
        thr=128; polarity='light'; minArea=2; bgRad=0; wtrOn=false; cirMin=0;
        areas=[{pts:[{x:0,y:0},{x:800,y:0},{x:800,y:600},{x:0,y:600}],key:curKey()}];
      })(); 'setup'
    """)
    print('  noise=0 n:', await ev("setTone(1,1,0,0); areaStats(); areaComps.length"), '(期待12)')
    print('  中央値 n:', await ev("setTone(1,1,0,1); areaStats(); areaComps.length"), '(期待0)')
    print('  ガウシアン n:', await ev("setTone(1,1,0,2); areaStats(); areaComps.length"),
          '(期待12: 2x2の各画素は加重8/16×255=127.5→128が閾値128以上で残る。単一画素なら16/16×255→16で消える)')
    print('--- UI・永続化 ---')
    print('  tonebtn.on:', await ev("$('n1').click(); $('tonebtn').classList.contains('on')"), '(期待True)')
    print('  localStorage:', await ev("JSON.parse(localStorage.getItem('tone')).noise"), '(期待1)')
    print('  n1/n2ボタンon表示:', await ev("$('n1').classList.contains('on')&&!$('n2').classList.contains('on')"), '(期待True)')
    print('  reset:', await ev("$('toneset').click(); JSON.stringify({n:tone.noise,on:$('tonebtn').classList.contains('on')})"), '(期待{n:0,on:false})')
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
    await ws.close()

asyncio.run(main())
