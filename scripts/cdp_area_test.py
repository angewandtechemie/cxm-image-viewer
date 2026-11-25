# 領域測定(2値化カウント)のCDP検証
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
    async def ev(e):
        msg = await cmd('Runtime.evaluate', expression=e, returnByValue=True)
        res = msg.get('result',{})
        if 'exceptionDetails' in res: return 'JS-ERR '+json.dumps(res['exceptionDetails'])[:400]
        return res.get('result',{}).get('value')
    async def shot(name):
        msg = await cmd('Page.captureScreenshot', format='jpeg', quality=90)
        d = msg.get('result',{}).get('data')
        if d: open('W:/hermes/cache/scratch/'+name,'wb').write(base64.b64decode(d)); print('saved',name)
    await cmd('Page.enable')
    await cmd('Page.bringToFront')
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v=area1')
    for _ in range(25):
        await asyncio.sleep(1)
        if await ev("video.videoWidth"): break
    await asyncio.sleep(1)
    print('ui:', await ev("JSON.stringify({btn:!!document.getElementById('m-area'),panel:!!document.getElementById('areapanel'),thr:!!document.getElementById('thr')})"))
    # 領域モードへ
    print('mode:', await ev("document.getElementById('m-area').click(); mode"))
    # 合成ROI(中央矩形)を注入して統計
    print('stats1:', await ev("""
      areas = [{pts:[{x:1200,y:700},{x:2600,y:700},{x:2600,y:1500},{x:1200,y:1500}], key:curKey()}];
      areaStats(); $('areaStats').textContent
    """))
    print('comps:', await ev("JSON.stringify(areaComps.slice(0,3).map(o=>({cx:Math.round(o.cx),cy:Math.round(o.cy),area:o.areaPx})))"), 'n=', await ev("areaComps.length"))
    await shot('area_rect.jpg')
    # 閾値を上げて成分が減ることを確認
    print('thr200 stats:', await ev("""
      thr=200; $('thr').value=200; $('thrv').textContent='200'; areaStats(); areaComps.length
    """))
    # 暗画素極性
    print('dark n:', await ev("""
      polarity='dark'; areaStats(); areaComps.length
    """))
    await shot('area_dark.jpg')
    # クリーンアップ
    print('clean:', await ev("document.getElementById('m-clear').click(); document.getElementById('m-dist').click(); mode + ' areas=' + areas.length + ' stats=' + $('areaStats').textContent.slice(0,20)"))
    await ws.close()

asyncio.run(main())
