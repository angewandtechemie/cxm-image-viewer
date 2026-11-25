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
                return r
    async def ev(expr):
        msg = await cmd('Runtime.evaluate', expression=expr, returnByValue=True)
        res = msg.get('result', {})
        if 'exceptionDetails' in res:
            return 'JS-ERR: ' + json.dumps(res['exceptionDetails'])[:300]
        return res.get('result', {}).get('value')
    async def click(x, y):
        for t in ('mousePressed','mouseReleased'):
            await cmd('Input.dispatchMouseEvent', type=t, x=x, y=y, button='left', clickCount=1)
    await cmd('Page.enable'); await cmd('Runtime.enable')
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html')
    for _ in range(20):
        await asyncio.sleep(1)
        if await ev("video.videoWidth"): break
    print('video ready, native:', await ev("video.videoWidth+'x'+video.videoHeight"))
    # 画面上のvideo矩形の中央付近で、100px水平の2点クリック(校正モード)
    r = await ev("JSON.stringify((()=>{const b=video.getBoundingClientRect();return {x:b.x+b.width/2-50,y:b.y+b.height/2}})())")
    import json as _j; r = _j.loads(r)
    # prompt対策: window.promptをオーバーライドして10mm固定で返す
    await ev("window.prompt=()=> '10'; setMode('cal')")
    await click(r['x'], r['y']); await asyncio.sleep(0.4)
    await click(r['x']+100, r['y']); await asyncio.sleep(0.6)
    print('calMap:', await ev("JSON.stringify(calMap)"))
    print('auto->dist:', await ev("mode"))
    print('calSeg set:', await ev("!!calSeg"))
    # キーボード(物理キーコード)で校正→測定への切替が効くか
    for t in ('keyDown','keyUp'):
        await cmd('Input.dispatchKeyEvent', type=t, key='c', code='KeyC', windowsVirtualKeyCode=67)
    await asyncio.sleep(0.3)
    print('after KeyC, mode:', await ev("mode"))
    for t in ('keyDown','keyUp'):
        await cmd('Input.dispatchKeyEvent', type=t, key='m', code='KeyM', windowsVirtualKeyCode=77)
    await asyncio.sleep(0.3)
    print('after KeyM, mode:', await ev("mode"))
    await ev("setMode('dist')")
    await click(r['x']+10, r['y']+30); await asyncio.sleep(0.4)
    await click(r['x']+90, r['y']+30); await asyncio.sleep(0.6)
    print('meas:', await ev("JSON.stringify(meas.map(m=>({mm:m.mm})))"))
    print('status:', await ev("document.getElementById('status').textContent"))
    # 回転90°でラインが残るか(座標変換の整合)
    await ev("$('rot').click()")
    await asyncio.sleep(0.5)
    shot = await cmd('Page.captureScreenshot', format='jpeg', quality=85)
    data = shot.get('result', {}).get('data')
    if not data:
        print('screenshot failed:', json.dumps(shot)[:200])
    else:
        open('W:/hermes/cache/scratch/meas_test.jpg','wb').write(base64.b64decode(data))
        print('shot saved')
    await ev("$('rot').click(); $('rot').click(); $('rot').click()")
    await ws.close()

asyncio.run(main())
