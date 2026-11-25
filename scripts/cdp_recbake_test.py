# -*- coding: utf-8 -*-
# v1.9検証: 解析結果の動画インポーズ(recBake)
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
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v=recbake1')
    for _ in range(30):
        await asyncio.sleep(1)
        if await ev("!!window.bakeAnalysisDraw && !!window.recBakeDraw"): break
    print('app:', await ev("APP_VER"))
    vw = 0
    for _ in range(20):
        await asyncio.sleep(1)
        vw = await ev("video.videoWidth") or 0
        if vw: break
    chk('カメラ起動', bool(vw), f'videoWidth={vw}')
    if not vw:
        print('status:', await ev("status.textContent")); return
    # 構文健全性: 既存の撮影bakeも生きていること
    chk('snapshotCanvas健在', await ev("typeof snapshotCanvas==='function' && typeof snapshot==='function'"))
    # 較正+測定線+スケールバーONの状態を作る
    await ev("""(() => { const k = curKey(); calMap[k] = 0.01;
      meas = [{ a: { x: srcW()*0.3, y: srcH()*0.3 }, b: { x: srcW()*0.7, y: srcH()*0.7 },
                mm: 0.01*Math.hypot(srcW()*0.4, srcH()*0.4), key: k }];
      scaleBarOn = true; $('scale').classList.add('on');
      return { W: srcW(), H: srcH() }; })()""")
    # MediaRecorderラッパ+DLフック
    await ev("""(() => { const _MR = window.MediaRecorder;
      window.MediaRecorder = class extends _MR { constructor(s, o) { super(s, o);
        try { window.__recIsCam = (s === stream); window.__recIsComp = (recComp && s === recComp.captureStream ? window.__compStream === s : false); } catch(e){}
        } };
      const _click = HTMLAnchorElement.prototype.click;
      HTMLAnchorElement.prototype.click = function() {
        if (this.href && this.href.startsWith('blob:')) window.__dl = { name: this.download };
        return _click.apply(this, arguments); };
      return 'wrapped'; })()""")
    # ---- recBake ON(既定)で録画: recCompに測定線(緑)とスケールバー(白)が描かれていること ----
    chk('recBake既定ON', await ev("recBake === true && $('recbake').classList.contains('on')"))
    await ev("$('recdelay').value='0'; $('reclen').value='0'; window.__dl=null; window.__recIsCam=null; void 0")
    await ev("$('rec').click(); void 0")
    await asyncio.sleep(2.5)
    comp = await ev("""(() => {
      if (!recComp || !recComp.width) return { err: 'no recComp' };
      const d = recComp.getContext('2d').getImageData(0, 0, recComp.width, recComp.height).data;
      let green = 0, whiteBR = 0;
      const W = recComp.width, H = recComp.height;
      for (let i = 0; i < d.length; i += 4) {
        const r = d[i], g = d[i+1], b = d[i+2];
        if (g > 180 && r < 140 && b > 60 && b < 180) green++;
      }
      // 右下25%×15%領域の白(スケールバー)
      for (let y = Math.floor(H*0.85); y < H; y++) for (let x = Math.floor(W*0.75); x < W; x++) {
        const i = (y*W+x)*4; if (d[i]>200 && d[i+1]>200 && d[i+2]>200) whiteBR++;
      }
      return { cw: W, ch: H, green, whiteBR, frames: fpsCount };
    })()""")
    isCam = await ev("window.__recIsCam")
    print('comp:', comp, '| isCam:', isCam)
    chk('録画ソース=合成canvas(カメラでない)', isCam is False, str(isCam))
    chk('動画に測定線がインポーズ(緑画素)', comp.get('green', 0) > 200, str(comp))
    chk('動画にスケールバーがインポーズ(右下白)', comp.get('whiteBR', 0) > 100, str(comp))
    await ev("$('rec').click(); void 0")
    await asyncio.sleep(2.0)
    dl = await ev("window.__dl ? JSON.stringify(window.__dl) : null")
    chk('WebM保存', dl and '動画.webm' in str(json.loads(dl).get('name','')), str(dl))
    # ---- recBake OFF: 従来動作(カメラストリーム直接)。tone補正が残っているとfx録画になるので既定へ戻す。 ----
    await ev("""(() => { tone = { gamma: 1, contrast: 1, sharp: 0, noise: 0, avg: 0, wb: [1,1,1] };
      localStorage.setItem('tone', JSON.stringify(tone)); syncToneUI();
      chan='all'; localStorage.setItem('channel','all'); applyFilters(); setEdgeMode();
      return fxNeeded(); })()""")
    await ev("$('recbake').click(); void 0")
    chk('recBake OFF切替', await ev("recBake === false && !$('recbake').classList.contains('on')"))
    await ev("window.__dl=null; window.__recIsCam=null; $('rec').click(); void 0")
    await asyncio.sleep(2.0)
    isCam2 = await ev("window.__recIsCam")
    await ev("$('rec').click(); void 0")
    await asyncio.sleep(2.0)
    chk('OFF時はカメラストリーム録画', isCam2 is True, str(isCam2))
    # 後始末
    await ev("$('recbake').click(); meas = []; delete calMap[curKey()]; drawOverlay(); void 0")
    print(f'== OK={ok} NG={ng} ==')

asyncio.run(main())
