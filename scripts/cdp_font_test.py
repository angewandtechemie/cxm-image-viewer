# -*- coding: utf-8 -*-
# オーバーレイ/焼き込みのフォントサイズ統一検証(OFS=13px、焼き込み=fs=max(14,幅/60))
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
    await cmd('Page.enable')
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v=font1')
    for _ in range(25):
        await asyncio.sleep(1)
        if await ev("video.videoWidth"): break
    print('video:', await ev("video.videoWidth+'x'+video.videoHeight"))
    chk('OFS=13', await ev("OFS") == 13, await ev("OFS"))
    # 較正と表示項目を全ONに
    await ev("calMap[curKey()]=0.01; localStorage.setItem('micro-cal',JSON.stringify(calMap)); $('sampname').value='FONT-TEST'; drawOverlay(); 'ok'")
    await asyncio.sleep(0.5)
    # 1) live: overlay ctxのfontセッタで全フォント収集
    fonts = await ev("""(() => {
      const octx = overlay.getContext('2d');
      const proto = CanvasRenderingContext2D.prototype;
      const desc = Object.getOwnPropertyDescriptor(proto, 'font');
      const seen = new Set();
      Object.defineProperty(octx, 'font', { configurable: true,
        get: () => desc.get.call(octx), set: v => { seen.add(v); desc.set.call(octx, v); } });
      drawOverlay();
      delete octx.font;
      return JSON.stringify([...seen]);
    })()""")
    fl = json.loads(fonts)
    live_ok = all(f == '13px monospace' for f in fl) and len(fl) >= 1
    chk('live overlayは13pxのみ', live_ok, str(fl))
    # 2) 焼き込み: snapshotCanvas中の全font収集
    await ev("""(() => { window.__bake = null;
      const proto = CanvasRenderingContext2D.prototype;
      const desc = Object.getOwnPropertyDescriptor(proto, 'font');
      const seen = new Set();
      Object.defineProperty(proto, 'font', { configurable: true,
        get: function(){ return desc.get.call(this); },
        set: function(v){ if (this.canvas.width >= 320) seen.add(v); desc.set.call(this, v); } });
      let c = null, err = null;
      (async () => {
        try { c = await snapshotCanvas(true, true); } catch(e) { err = String(e); }
        Object.defineProperty(proto, 'font', desc);
        const tr = { w: video.videoWidth, h: video.videoHeight };
        window.__bake = JSON.stringify({ fonts: [...seen], err, w: c ? c.width : 0, expect: Math.max(14, Math.round(tr.w/60)) });
      })();
      return 'started';
    })()""")
    for _ in range(30):
        await asyncio.sleep(1)
        bake = await ev("window.__bake")
        if bake: break
    b = json.loads(bake)
    print('bake fonts:', b['fonts'], 'expect fs=', b['expect'], 'err:', b['err'])
    exp = f"{b['expect']}px monospace"
    bf = [f for f in b['fonts'] if 'monospace' in f]
    chk('焼き込みは単一サイズ(fs)', b['err'] is None and bf and all(f == exp for f in bf), str(bf))
    # 3) drawScaleBarへ渡るfs実引数(live=OFS / bake=fs)
    await ev("""(() => { window.__caps = null; const caps = [];
      const _dsb = drawScaleBar;
      drawScaleBar = function(ctx, mpp, barFn, x2, y2, fs, info) { caps.push(fs); return _dsb(ctx, mpp, barFn, x2, y2, fs, info); };
      drawOverlay();
      (async () => { await snapshotCanvas(true, false); drawScaleBar = _dsb; window.__caps = JSON.stringify(caps); })();
      return 'started';
    })()""")
    for _ in range(30):
        await asyncio.sleep(1)
        caps = await ev("window.__caps")
        if caps: break
    cl = json.loads(caps)
    expfs = b['expect']
    chk('drawScaleBar: live=13, bake=fs', cl == [13, expfs], str(cl))
    print(f'--- {ok} PASS / {ng} NG')

asyncio.run(main())
