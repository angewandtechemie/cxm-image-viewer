# 補正(ガンマ/コントラスト/シャープ)決定的検証: 合成映像でLUT値・GL一致・unsharp過調整・PNG焼き込みを確認
import json, asyncio, math, urllib.request, websockets

def wsu():
    tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
    return [t for t in tabs if t['type']=='page' and '8642' in t['url']][0]['webSocketDebuggerUrl']

def js_tone(v, gamma, con):  # 0-255値へのLUT適用(JS/GL共通の期待値、JS Math.round準拠)
    x = (pow(v/255.0, 1.0/gamma) - 0.5) * con + 0.5
    return int(max(0.0, min(255.0, x*255.0)) + 0.5)

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
    async def poll_x(n=12):  # detached asyncの結果をwindow.__x経由で受け取る(awaitPromise不使用)
        for _ in range(n):
            await asyncio.sleep(0.7)
            v = await ev("window.__x===undefined?null:JSON.stringify(window.__x)")
            if v is not None: return json.loads(v)
        return 'TIMEOUT'
    await cmd('Page.enable'); await cmd('Page.bringToFront')
    await cmd('Emulation.setDeviceMetricsOverride', width=1600, height=900, deviceScaleFactor=1, mobile=False)
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v=tone2')
    for _ in range(20):
        await asyncio.sleep(1)
        if await ev("!!window.setTone"): break
    print('app loaded:', await ev("APP_VER"))
    # カメラ起動(start()非同期)を先に完了させ、その後に合成ストリームへ差し替える(競合回避)
    for _ in range(15):
        await asyncio.sleep(1)
        if await ev("video.videoWidth > 0"): break
    # 合成映像: 全体gray100 + (400..600,200..400)にgray200矩形(エッジ検証用)
    await ev("""
      (() => {
        const c = document.createElement('canvas'); c.width=900; c.height=600;
        const g = c.getContext('2d');
        g.fillStyle='rgb(100,100,100)'; g.fillRect(0,0,900,600);
        g.fillStyle='rgb(200,200,200)'; g.fillRect(400,200,200,200);
        video.srcObject = c.captureStream(30); video.play();
      })(); 'synth'
    """)
    for _ in range(15):
        await asyncio.sleep(1)
        if await ev("video.videoWidth === 900"): break
    print('synth video:', await ev("video.videoWidth + 'x' + video.videoHeight"))
    px = lambda x,y: f"(()=>{{const d=frameData().data;const j=({y}*900+{x})*4;return [d[j],d[j+1],d[j+2]];}})()"
    # 0) 補正OFFの基準値
    await ev("setTone(1,1,0)")
    print('base gray100:', await ev(px(100,100)), '(期待100)')
    # 1) ガンマLUT(frameData経路)
    await ev("setTone(2,1,0)")
    exp = round(js_tone(100, 2, 1))
    print('gamma2 gray100:', await ev(px(100,100)), f'(期待{exp})')
    # 2) コントラストLUT
    await ev("setTone(1,2,0)")
    exp = round(js_tone(100, 1, 2))
    print('contrast2 gray100:', await ev(px(100,100)), f'(期待{exp})')
    # 3) GL表示とJS LUTの一致(gamma2+contrast1.5)
    await ev("setTone(2,1.5,0)")
    await asyncio.sleep(0.7)
    await ev("window.__x=undefined; setTone(2,1.5,0)")
    await asyncio.sleep(0.7)
    await ev("""(async()=>{
      await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
      const c=document.createElement('canvas'); c.width=fx.width; c.height=fx.height;
      const g=c.getContext('2d'); g.drawImage(fx,0,0);
      const d=g.getImageData(100,100,1,1).data;
      window.__x=[d[0],d[1],d[2],fx.width,fx.height];
    })(); 'kicked'""")
    print('GL fx pixel:', await poll_x(), f'(期待≈{js_tone(100,2,1.5)})')
    # 4) シャープ過調整(frameData): 矩形左境界399/400で 80/220
    await ev("setTone(1,1,1)")
    print('sharp left(399,300):', await ev(px(399,300)), '(期待80)')
    print('sharp right(400,300):', await ev(px(400,300)), '(期待220)')
    # 5) GL側シャープも同カーネル
    await asyncio.sleep(0.7)
    await ev("""(async()=>{
      await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
      const c=document.createElement('canvas'); c.width=fx.width; c.height=fx.height;
      const g=c.getContext('2d'); g.drawImage(fx,0,0);
      const a=g.getImageData(399,300,1,1).data, b=g.getImageData(400,300,1,1).data;
      window.__x=[a[0],b[0]];
    })(); 'kicked'""")
    print('GL sharp L/R:', await poll_x(), '(期待≈80/220)')
    # 6) PNG焼き込み: shot(S)の映像のみPNGにも補正が載る
    await ev("""
      window.__pngs=[];
      const _tb=HTMLCanvasElement.prototype.toBlob;
      HTMLCanvasElement.prototype.toBlob=function(cb,...a){return _tb.call(this,b=>{window.__pngs.push(b);if(cb)cb(b);},...a);};
      'hooked'
    """)
    await ev("setTone(2,1,0)")
    await ev("document.getElementById('shot').click(); 'shot'")
    await asyncio.sleep(1.5)
    await ev("""(async()=>{
      const b=window.__pngs[0]; if(!b){window.__x='no png';return;}
      const bmp=await createImageBitmap(b);
      const c=document.createElement('canvas'); c.width=bmp.width; c.height=bmp.height;
      const g=c.getContext('2d'); g.drawImage(bmp,0,0);
      const d=g.getImageData(100,100,1,1).data;
      window.__x=[d[0],d[1],d[2],bmp.width,bmp.height];
    })(); 'kicked'""")
    print('snapshot pixel:', await poll_x(15), f'(期待≈{js_tone(100,2,1)})')
    # 7) UI: メニュー開閉と.on状態、リセット
    await ev("document.getElementById('tonebtn').click(); 'open'")
    print('menu display:', await ev("getComputedStyle(document.getElementById('tonemenu')).display"), '(期待flex)')
    print('btn on:', await ev("document.getElementById('tonebtn').classList.contains('on')"))
    print('after reset:', await ev("document.getElementById('toneset').click(); JSON.stringify([tone, document.getElementById('tonebtn').classList.contains('on'), localStorage.getItem('tone')])"))
    # 後片付け
    await ev("document.body.click(); setTone(1,1,0); 'cleanup'")
    await cmd('Emulation.clearDeviceMetricsOverride')
    await ws.close()

asyncio.run(main())
