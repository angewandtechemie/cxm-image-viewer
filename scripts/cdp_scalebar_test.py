import json, asyncio, base64, urllib.request, websockets

def wsu():
    tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
    return [t for t in tabs if t['type']=='page' and '8642' in t['url']][0]['webSocketDebuggerUrl']

async def main():
    ws = await websockets.connect(wsu(), max_size=3*10**7); mid = 0
    async def cmd(m, **p):
        nonlocal mid; mid += 1
        await ws.send(json.dumps({'id': mid, 'method': m, 'params': p}))
        while True:
            r = json.loads(await ws.recv())
            if r.get('id') == mid: return r
    async def ev(e):
        msg = await cmd('Runtime.evaluate', expression=e, returnByValue=True)
        res = msg.get('result', {})
        if 'exceptionDetails' in res: return 'JS-ERR ' + json.dumps(res['exceptionDetails'])[:250]
        return res.get('result', {}).get('value')
    async def shot(name):
        msg = await cmd('Page.captureScreenshot', format='jpeg', quality=90)
        d = msg.get('result', {}).get('data')
        if d:
            open('W:/hermes/cache/scratch/'+name,'wb').write(base64.b64decode(d))
            print('saved', name)
    await cmd('Page.enable')
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html')
    for _ in range(20):
        await asyncio.sleep(1)
        if await ev("video.videoWidth"): break
    await asyncio.sleep(1)
    print('cal:', await ev("JSON.stringify(calMap)"))
    print('scale bar expected mm:', await ev("(mmPerPx()?fmtLen(niceScaleMm(mmPerPx())):'no cal')"))
    await shot('scale_on.jpg')
    await ev("document.getElementById('scale').click()")
    await asyncio.sleep(0.5)
    print('scaleBarOn now:', await ev("scaleBarOn"))
    await shot('scale_off.jpg')
    await ev("document.getElementById('scale').click()")  # 戻す
    await asyncio.sleep(0.5)
    print('scaleBarOn restored:', await ev("scaleBarOn"))
    await ws.close()

asyncio.run(main())
