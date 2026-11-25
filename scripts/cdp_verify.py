import json, asyncio, base64, urllib.request, websockets

def get_page_ws():
    tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
    for t in tabs:
        if t['type']=='page' and '8642' in t['url']:
            return t['webSocketDebuggerUrl']
    raise SystemExit('page not found')

async def main():
    ws = await websockets.connect(get_page_ws(), max_size=3*10**7)
    mid = 0
    async def cmd(method, **params):
        nonlocal mid
        mid += 1
        await ws.send(json.dumps({'id': mid, 'method': method, 'params': params}))
        while True:
            r = json.loads(await ws.recv())
            if r.get('id') == mid:
                return r.get('result', r)
    async def ev(expr):
        r = await cmd('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=True)
        if 'result' in r and 'result' in r['result']:
            return r['result']['result'].get('value')
        return r
    await cmd('Page.enable'); await cmd('Runtime.enable')
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html')
    await asyncio.sleep(5)
    print('status bar:', await ev("document.getElementById('status').textContent"))
    print('track:', await ev("stream?JSON.stringify(stream.getVideoTracks()[0].getSettings()):'no stream'"))
    shot = await cmd('Page.captureScreenshot', format='jpeg', quality=85)
    if 'data' in shot:
        open('W:/hermes/cache/scratch/viewer_win.jpg','wb').write(base64.b64decode(shot['data']))
        print('screenshot saved')
    await ws.close()

asyncio.run(main())
