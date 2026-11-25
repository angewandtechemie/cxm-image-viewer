# 撮影/解析を含めて撮影の検証: 両ボタンでPNG生成、bake=trueのみ解析描画が焼き込まれることを画素比較で確認
import json, asyncio, base64, urllib.request, websockets

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
    async def ev(e, awaitp=False):
        msg = await cmd('Runtime.evaluate', expression=e, returnByValue=True, awaitPromise=awaitp)
        res = msg.get('result',{})
        if 'exceptionDetails' in res: return 'JS-ERR '+json.dumps(res['exceptionDetails'])[:300]
        return res.get('result',{}).get('value')
    await cmd('Page.enable'); await cmd('Page.bringToFront')
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v=cap2')
    for _ in range(25):
        await asyncio.sleep(1)
        if await ev("video.videoWidth"): break
    await asyncio.sleep(1)
    # ヘッダー配置: shot/shot2が1行目右、m-dist/lplot/m-areaが2行目右
    print('row placement:', await ev("""JSON.stringify(['shot','shot2','m-dist','lplot','m-area'].map(i=>{
      const b=document.getElementById(i), row=b.closest('.hrow');
      return {i, row:[...document.querySelectorAll('.hrow')].indexOf(row)+1,
              x:Math.round(b.getBoundingClientRect().left), fits:b.scrollWidth<=b.clientWidth+1};}))"""))
    print('labels:', await ev("JSON.stringify(['shot','shot2','m-area'].map(i=>document.getElementById(i).innerText.replace(/\\n/g,'|')))"))
    # toBlobフックで生成PNGを2枚捕捉
    await ev("""
      window.__pngs=[];
      const _tb=HTMLCanvasElement.prototype.toBlob;
      HTMLCanvasElement.prototype.toBlob=function(cb,...a){
        return _tb.call(this, b=>{ window.__pngs.push(b); if(cb)cb(b); }, ...a);
      };
      'hooked'
    """)
    # 解析要素として測定線を1本注入
    await ev("meas=[{a:{x:800,y:800},b:{x:2800,y:800},mm:14.89}]; 'meas injected'")
    await ev("document.getElementById('shot').click(); 'plain'")
    await asyncio.sleep(1)
    await ev("document.getElementById('shot2').click(); 'baked'")
    await asyncio.sleep(1)
    print('n pngs:', await ev("window.__pngs.length"))
    cmp_js = """(async () => {
      const [b1, b2] = window.__pngs;
      if (!b1 || !b2) return 'missing';
      const load = async b => {
        const bmp = await createImageBitmap(b);
        const c = document.createElement('canvas'); c.width = bmp.width; c.height = bmp.height;
        c.getContext('2d').drawImage(bmp, 0, 0);
        return c.getContext('2d').getImageData(0, 0, bmp.width, bmp.height).data;
      };
      const d1 = await load(b1), d2 = await load(b2);
      let diff = 0;
      for (let i = 0; i < d1.length; i += 4)
        if (Math.abs(d1[i]-d2[i]) + Math.abs(d1[i+1]-d2[i+1]) + Math.abs(d1[i+2]-d2[i+2]) > 30) diff++;
      return JSON.stringify({bytes:[b1.size, b2.size], diffPixels:diff, total:d1.length/4});
    })()"""
    print('plain vs baked:', await ev(cmp_js, True))
    # 逆順: 解析なしが先にbake=falseを証明するため、撮影線なしでもbake=trueはスケールバー差分が出るか(calMap必須)
    print('cal present:', (await ev("JSON.stringify(calMap)"))[:80])
    await ev("meas=[]; drawOverlay(); 'clean'")
    await ws.close()

asyncio.run(main())
