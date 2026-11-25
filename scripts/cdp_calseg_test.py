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
        if 'exceptionDetails' in res: return 'JS-ERR '+json.dumps(res['exceptionDetails'])[:250]
        return res.get('result',{}).get('value')
    async def click(x,y):
        for t in ('mousePressed','mouseReleased'):
            await cmd('Input.dispatchMouseEvent', type=t, x=x, y=y, button='left', clickCount=1)
    async def shot(name):
        msg = await cmd('Page.captureScreenshot', format='jpeg', quality=90)
        d = msg.get('result',{}).get('data')
        if d: open('W:/hermes/cache/scratch/'+name,'wb').write(base64.b64decode(d)); print('saved',name)
    await cmd('Page.enable')
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html')
    for _ in range(20):
        await asyncio.sleep(1)
        if await ev("video.videoWidth"): break
    await asyncio.sleep(1)
    # 較正線を合成で作る
    r = json.loads(await ev("JSON.stringify((()=>{const b=video.getBoundingClientRect();return {x:b.x+b.width/2-150,y:b.y+b.height/2}})())"))
    await ev("window.prompt=()=>'10'; setMode('cal')")
    await click(r['x'], r['y']); await asyncio.sleep(0.4)
    await click(r['x']+300, r['y']); await asyncio.sleep(0.7)
    print('calSeg persisted:', await ev("!!localStorage.getItem('micro-calseg')"))
    print('calSeg key ok:', await ev("calSeg && calSeg.key===curKey()"))
    await shot('calseg_on.jpg')
    await ev("document.getElementById('calshow').click()")
    await asyncio.sleep(0.5)
    print('calSegOn now:', await ev("calSegOn"))
    await shot('calseg_off.jpg')
    await ev("document.getElementById('calshow').click()")  # 戻す
    await ws.close()

asyncio.run(main())
