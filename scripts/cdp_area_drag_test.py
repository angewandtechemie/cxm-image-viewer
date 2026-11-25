# ROI頂点ドラッグ編集のCDP検証: 矩形の1頂点をドラッグし、pts更新と統計面積の自己整合を確認
import json, asyncio, re, urllib.request, websockets

def wsu():
    tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
    return [t for t in tabs if t['type']=='page' and '8642' in t['url']][0]['webSocketDebuggerUrl']

def shoelace(pts):
    s2 = 0
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        s2 += a['x'] * b['y'] - b['x'] * a['y']
    return abs(s2) / 2

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
    async def mouse(t, x, y, btn='left'):
        buttons = 1 if t != 'mouseReleased' and btn=='left' else (0 if t=='mouseReleased' else 1)
        await cmd('Input.dispatchMouseEvent', type=t, x=x, y=y, button=btn, clickCount=1, buttons=buttons)
    await cmd('Page.enable')
    await cmd('Page.bringToFront')
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v=drag1')
    for _ in range(25):
        await asyncio.sleep(1)
        if await ev("video.videoWidth"): break
    await asyncio.sleep(1)
    await ev("document.getElementById('m-area').click()")
    await ev("""
      areas=[{pts:[{x:1200,y:700},{x:2600,y:700},{x:2600,y:1500},{x:1200,y:1500}],key:curKey()}];
      areaStats(); 'injected'
    """)
    print('before:', (await ev("$('areaStats').textContent")) .splitlines()[0])
    # 頂点2(2600,1500)のビューポート座標
    xy = json.loads(await ev("""
      (()=>{const s=toStagePt(2600,1500), r=$('stage').getBoundingClientRect();
           return JSON.stringify({x:r.left+s.x, y:r.top+s.y});})()
    """))
    print('vertex client pos:', xy)
    await mouse('mousePressed', xy['x'], xy['y'])
    print('dragging started:', await ev("JSON.stringify(!!dragPt)"))
    for dx, dy in [(50, 30), (100, 60), (150, 90), (200, 120)]:
        await mouse('mouseMoved', xy['x'] + dx, xy['y'] + dy)
        await asyncio.sleep(0.05)
    await mouse('mouseReleased', xy['x'] + 200, xy['y'] + 120)
    pts = json.loads(await ev("JSON.stringify(areas[0].pts)"))
    text = await ev("$('areaStats').textContent")
    print('after:', text.splitlines()[0])
    print('npts:', len(pts), '(期待4)', 'moved:', pts[2])
    exp = shoelace(pts)
    m = re.search(r'ROI: ([\d.]+) px', text)
    got = float(m.group(1))
    print(f'shoelace(pts)={exp:.0f} panel={got:.0f} match={abs(exp-got)<max(50,exp*1e-4)}')
    await ev("document.getElementById('m-clear').click(); document.getElementById('m-dist').click(); 'clean'")
    await ws.close()

asyncio.run(main())
