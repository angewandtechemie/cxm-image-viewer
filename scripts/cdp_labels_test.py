# ヘッダーラベル(ショートカット表記)表示確認: 収まりとラベル文字列
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
    await cmd('Page.enable'); await cmd('Page.bringToFront')
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v=labels1')
    for _ in range(25):
        await asyncio.sleep(1)
        if await ev("video.videoWidth"): break
    print('labels:', await ev("""JSON.stringify(['rot','m-cal','m-del','m-dist','shot','lplot','m-area'].map(i=>{
      const b=document.getElementById(i);
      return {i, text:b.innerText.replace(/\\n/g,'|'), fits:b.scrollWidth<=b.clientWidth+1};}))"""))
    msg = await cmd('Page.captureScreenshot', format='jpeg', quality=90)
    open('W:/hermes/cache/scratch/labels_shortcut.jpg','wb').write(base64.b64decode(msg['result']['data']))
    print('saved labels_shortcut.jpg')
    await ws.close()

asyncio.run(main())
