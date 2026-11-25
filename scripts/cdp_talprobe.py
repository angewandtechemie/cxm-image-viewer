# -*- coding: utf-8 -*-
# tincmenu内のセレクトが実クリックで操作できるか(メニューが開いたままか)の検証
import json, asyncio, urllib.request, websockets

def wsu():
    tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
    return [t for t in tabs if t['type']=='page' and '8642' in t['url']][0]['webSocketDebuggerUrl']

async def main():
    ws = await websockets.connect(wsu(), max_size=3*10**7); mid=0
    async def cmd(m,**p):
        nonlocal mid; mid+=1
        await ws.send(json.dumps({'id':mid,'method':m,'params':p}))
        while True:
            r=json.loads(await ws.recv())
            if r.get('id')==mid: return r
    async def ev(e):
        msg=await cmd('Runtime.evaluate',expression=e,returnByValue=True)
        res=msg.get('result',{})
        if 'exceptionDetails' in res: return 'JS-ERR '+json.dumps(res['exceptionDetails'])[:300]
        return res.get('result',{}).get('value')
    await cmd('Page.enable'); await cmd('Page.bringToFront')
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v=tal5')
    for _ in range(15):
        await asyncio.sleep(1)
        if await ev("!!window.talParams"): break
    await ev("$('tincbtn').click(); 'open'")
    await asyncio.sleep(1)
    print('open:', await ev("getComputedStyle($('tincmenu')).display"))
    pos = json.loads(await ev("(() => { const r=$('taltotal').getBoundingClientRect(); return JSON.stringify([r.x+r.width/2, r.y+r.height/2]); })()"))
    x,y = pos
    await cmd('Input.dispatchMouseEvent', type='mousePressed', x=x, y=y, button='left', clickCount=1)
    await cmd('Input.dispatchMouseEvent', type='mouseReleased', x=x, y=y, button='left', clickCount=1)
    await asyncio.sleep(0.6)
    print('after select click, menu:', await ev("getComputedStyle($('tincmenu')).display"),
          'activeEl:', await ev("document.activeElement.id"))
    import base64
    shot = await cmd('Page.captureScreenshot', format='png', fromSurface=True,
        clip={'x':max(0,x-260),'y':max(0,y-160),'width':640,'height':420,'scale':2})
    open('W:/hermes/cache/scratch/talpopup.png','wb').write(base64.b64decode(shot['result']['data']))
    print('shot saved')

asyncio.run(main())
