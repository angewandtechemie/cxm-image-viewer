# -*- coding: utf-8 -*-
# v1.8検証: 録画・タイムラプス中の進捗マーカー(画面左上ドット+経過/枚数+上端進行バー)
import json, asyncio, urllib.request, websockets

def wsu():
    tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
    return [t for t in tabs if t['type']=='page' and '8642' in t['url']][0]['webSocketDebuggerUrl']

ok = 0; ng = 0
def chk(name, cond, got=''):
    global ok, ng
    if cond: ok += 1; print(f'PASS {name}')
    else: ng += 1; print(f'NG   {name} | {got}')

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
    await cmd('Page.enable'); await cmd('Page.bringToFront')
    await cmd('Emulation.setDeviceMetricsOverride', width=1600, height=900, deviceScaleFactor=1, mobile=False)
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v=progr1')
    for _ in range(30):
        await asyncio.sleep(1)
        if await ev("!!window.drawProgressMark && document.getElementById('recbtn')"): break
    print('app:', await ev("APP_VER"))
    vw = 0
    for _ in range(20):
        await asyncio.sleep(1)
        vw = await ev("video.videoWidth") or 0
        if vw: break
    chk('カメラ起動', bool(vw), f'videoWidth={vw}')
    if not vw:
        print('status:', await ev("status.textContent")); return

    # オーバーレイ上の特定色画素を数える関数をページに注入
    await ev("""window.__count = (mode) => {
      const d = overlay.getContext('2d').getImageData(0,0,overlay.width,overlay.height).data;
      let n = 0;
      for (let i = 0; i < d.length; i += 4) {
        const r = d[i], g = d[i+1], b = d[i+2], a = d[i+3];
        if (a < 100) continue;
        if (mode === 'red' && r > 200 && g < 90 && b < 90) n++;
        if (mode === 'orange' && r > 200 && g > 140 && g < 220 && b < 80) n++;
      }
      return n; }; 'ok'""")
    base_red = await ev("window.__count('red')")
    base_or = await ev("window.__count('orange')")

    # ---- 録画中マーカー ----
    await ev("$('recdelay').value='0'; $('reclen').value='10'; void 0")
    await ev("$('rec').click(); void 0")
    await asyncio.sleep(2.5)
    st = await ev("rec ? rec.state : null")
    red1 = await ev("window.__count('red')")
    bar = await ev("""(() => {  // 映像上端5px帯の赤い進行バー画素
      const vr = video.getBoundingClientRect(), sr = stage.getBoundingClientRect();
      const x0 = Math.round(vr.left-sr.left), y0 = Math.round(vr.top-sr.top);
      const d = overlay.getContext('2d').getImageData(x0, y0, Math.round(vr.width), 5).data;
      let n = 0; for (let i = 0; i < d.length; i += 4) if (d[i]>200 && d[i+1]<90 && d[i+2]<90) n++;
      return n; })()""")
    print('rec state:', st, '| red px:', red1, '| topbar red px:', bar)
    chk('録画中: 赤マーカー出現', red1 > base_red + 30, f'{red1} vs {base_red}')
    chk('録画中: 上端進行バー(10s中2.5s→2%-40%)', 0 < bar, str(bar))
    await ev("$('rec').click(); void 0")  # 停止
    await asyncio.sleep(1.5)
    red2 = await ev("window.__count('red')")
    chk('停止後: マーカー消去', red2 <= base_red + 5, f'{red2} vs {base_red}')

    # ---- タイムラプス中マーカー ----
    await ev("$('taltotal').value='1'; $('taln').value='1'; talInfo(); void 0")  # 1分→1秒=30枠・間隔1s
    await ev("tincToggle('tl'); void 0")
    await asyncio.sleep(3.0)
    run = await ev("!!tincT")
    n1 = await ev("tincN")
    or1 = await ev("window.__count('orange')")
    print('tl running:', run, 'frames:', n1, 'orange px:', or1)
    chk('TL中: 橙マーカー出現', run and or1 > base_or + 30, f'run={run} or={or1} vs {base_or}')
    chk('TL進行: 撮影進行(>=2枠)', n1 >= 2, str(n1))
    await ev("tincStop(); void 0")
    await asyncio.sleep(1.0)
    or2 = await ev("window.__count('orange')")
    chk('TL停止後: マーカー消去', or2 <= base_or + 5, f'{or2} vs {base_or}')
    print(f'== OK={ok} NG={ng} ==')

asyncio.run(main())
