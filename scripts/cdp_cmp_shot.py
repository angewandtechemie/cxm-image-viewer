import json, asyncio, time, urllib.request, websockets, base64, pathlib
def wsu():
    tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
    return [t for t in tabs if t['type']=='page' and '8642' in t['url']][0]['webSocketDebuggerUrl']
async def main():
    ws = await websockets.connect(wsu(), max_size=8*10**7); mid=0
    async def cmd(m, **p):
        nonlocal mid; mid+=1
        await ws.send(json.dumps({'id':mid,'method':m,'params':p}))
        while True:
            r=json.loads(await ws.recv())
            if r.get('id')==mid: return r
    async def ev(e):
        msg=await cmd('Runtime.evaluate', expression=e, returnByValue=True)
        return msg.get('result',{}).get('result',{}).get('value')
    await cmd('Page.enable')
    await cmd('Emulation.setDeviceMetricsOverride', width=1600, height=900, deviceScaleFactor=1, mobile=False)
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v='+str(int(time.time())))
    for _ in range(20):
        await asyncio.sleep(1)
        if await ev("!!window.setCmp") is True: break
    for _ in range(15):
        await asyncio.sleep(1)
        if await ev("video.videoWidth > 0") is True: break
    print('camera:', await ev("video.videoWidth+'x'+video.videoHeight"))
    await ev("$('cmpbtn').click();")
    await asyncio.sleep(0.4)
    await ev("cmpCapture();")
    await asyncio.sleep(2.5)
    shot = await cmd('Page.captureScreenshot', format='png')
    out = pathlib.Path('W:/hermes/apps/microscope-viewer/scripts/cmp_real_v14.png')
    out.write_bytes(base64.b64decode(shot['result']['data']))
    print('saved:', out)
    await ev("$('cmsoff').click(); $('cmpbtn').click();")  # メニュー閉じる
    await ws.close()
asyncio.run(main())
