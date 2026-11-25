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
        if 'exceptionDetails' in res: return 'JS-ERR '+json.dumps(res['exceptionDetails'])[:300]
        return res.get('result',{}).get('value')
    async def shot(name):
        msg = await cmd('Page.captureScreenshot', format='jpeg', quality=90)
        d = msg.get('result',{}).get('data')
        if d: open('W:/hermes/cache/scratch/'+name,'wb').write(base64.b64decode(d)); print('saved',name)
    await cmd('Page.enable')
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html')
    for _ in range(25):
        await asyncio.sleep(1)
        if await ev("video.videoWidth"): break
    await asyncio.sleep(1)
    calp = await ev("JSON.stringify(calMap)")
    print('cal present:', (calp or '')[:90])
    print('grid options:', await ev("JSON.stringify([...document.getElementById('gridstep').options].map(o=>o.textContent))"))
    print('auto mm:', await ev("autoGridMm(mmPerPx())"))
    # グリッドON + auto
    await ev("if(!gridOn)document.getElementById('grid').click(); document.getElementById('gridstep').value='auto'; drawOverlay(); 'ok'")
    await asyncio.sleep(0.5)
    await shot('grid_auto.jpg')
    # 1mm格子に明示変更
    await ev("document.getElementById('gridstep').value='1'; drawOverlay(); 'ok'")
    await asyncio.sleep(0.5)
    print('step now:', await ev("$('gridstep').value"))
    await shot('grid_1mm.jpg')
    # pxモードに戻して消す(デフォルト状態へ)
    await ev("localStorage.removeItem('grid step'); document.getElementById('gridstep').value='auto'; if(gridOn)document.getElementById('grid').click(); 'clean'")
    await ws.close()

asyncio.run(main())
