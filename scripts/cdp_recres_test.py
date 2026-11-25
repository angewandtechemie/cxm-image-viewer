# -*- coding: utf-8 -*-
# v1.7検証: (1)解像度対応一覧の実測 (2)画像演算表示を反映した録画
import json, asyncio, urllib.request, websockets

def wsu():
    for _ in range(20):
        try:
            tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
            pages = [t for t in tabs if t['type']=='page' and '8642' in t['url']]
            if pages: return pages[0]['webSocketDebuggerUrl']
        except Exception: pass
        yield_me = True; import time; time.sleep(1)
    raise RuntimeError('no CDP page tab')

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
    # 既に同じURLのページ: 再読込で新コードを確実に読む
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v=recres2')
    for _ in range(30):
        await asyncio.sleep(1)
        if await ev("!!window.probeResolutions && document.getElementById('resbtn')"): break
    print('app:', await ev("APP_VER"))
    # カメラ起動待ち(H1612=3840x2160)
    vw = 0
    for _ in range(20):
        await asyncio.sleep(1)
        vw = await ev("video.videoWidth") or 0
        if vw: break
    cur = await ev("JSON.stringify(stream.getVideoTracks()[0].getSettings())")
    cur = json.loads(cur) if cur else {}
    CW, CH = cur.get('width'), cur.get('height')
    print('camera:', cur.get('label'), f'{CW}x{CH}')
    chk('カメラ起動', bool(CW), str(cur))
    if not CW:
        print('status:', await ev("status.textContent")); return

    # ---- (1) 解像度実測(detached実行→poll) ----
    await ev("""(() => { window.__probe = null;
      probeResolutions(true).then(r => window.__probe = {done:true, list:r});
      return 'kicked'; })()""")
    probe = None
    for _ in range(60):
        await asyncio.sleep(2)
        probe = await ev("window.__probe ? JSON.stringify(window.__probe) : null")
        if probe: break
    probe = json.loads(probe) if probe else {}
    lst = probe.get('list') or []
    print('probe list:', lst)
    chk('一覧取得', bool(lst), str(probe)[:200])
    chk('現在modeを含む', f'{CW}x{CH}' in lst, f'cur={CW}x{CH}')
    chk('小さいmodeを含む', any(v in lst for v in ('640x480','320x240')))
    chk('全項目がw>=320', all(int(v.split('x')[0]) >= 320 for v in lst))
    await asyncio.sleep(2)
    chk('解像度復元', (await ev("video.videoWidth")) == CW, await ev("video.videoWidth"))
    # メニューが実測一覧になっている
    await ev("$('resbtn').click(); 'open'")
    await asyncio.sleep(0.5)
    items = await ev("""JSON.stringify([...$('resmenu').children].map(b=>b.textContent))""")
    items = json.loads(items) if items else []
    print('menu items:', items)
    chk('メニュー=実測一覧+再照会', all(v.replace('x','×') in items for v in lst) and any('再照会' in i for i in items), str(items))
    await ev("document.body.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true})); void 0")
    await asyncio.sleep(0.3)

    # ---- (2) 画像演算表示を反映した録画 ----
    # MediaRecorderのソーストラックlabel記録+ダウンロード発火フック(blob: hrefの<a>.click)
    await ev("""(() => { const _MR = window.MediaRecorder;
      window.MediaRecorder = class extends _MR {
        constructor(s, o) { super(s, o);
          try { window.__recTrack = s.getVideoTracks()[0].label; window.__recIsCam = (s === stream); } catch(e) { window.__recTrack = 'ERR'; }
        } };
      const _click = HTMLAnchorElement.prototype.click;
      HTMLAnchorElement.prototype.click = function() {
        if (this.href && this.href.startsWith('blob:')) window.__dl = { name: this.download };
        return _click.apply(this, arguments); };
      return 'wrapped'; })()""")
    camLabel = await ev("stream.getVideoTracks()[0].label")
    # v1.9以降recBake既定ON(合成canvas録画)なので、v1.7経路の検証ここではOFFにする
    await ev("recBake = false; localStorage.setItem('rec bake','0'); void 0")
    # 素のRGBではカメラストリームを録る(補正も既定にリセットしてfxNeeded=falseを確保)
    await ev("""(() => { tone = { gamma: 1, contrast: 1, sharp: 0, noise: 0, avg: 0, wb: [1,1,1] };
      localStorage.setItem('tone', JSON.stringify(tone)); syncToneUI();
      chan='all'; localStorage.setItem('channel','all'); applyFilters(); setEdgeMode();
      return fxNeeded(); })()""")
    await ev("$('reclen').value='0'; $('recdelay').value='0'; void 0")  # 遅延0(既定3sだと取消クリックと衝突する)
    await ev("window.__recTrack=null; window.__recIsCam=null; window.__dl=null; $('rec').click(); void 0")
    await asyncio.sleep(2.0)
    rgbTrack = await ev("window.__recTrack"); rgbIsCam = await ev("window.__recIsCam")
    await ev("$('rec').click(); void 0")  # 停止
    await asyncio.sleep(2.0)
    rgbDl = await ev("window.__dl ? JSON.stringify(window.__dl) : null")
    print('RGB rec track:', rgbTrack, '| isCam:', rgbIsCam, '| dl:', rgbDl)
    chk('RGB録画=カメラストリーム', rgbIsCam is True and str(rgbTrack) == str(camLabel), f'track={rgbTrack} cam={camLabel}')
    chk('RGB録画WebM保存', rgbDl and '動画.webm' in str(json.loads(rgbDl).get('name','')), str(rgbDl))
    # exg(B-R+G系)表示ではfx canvasを録る
    await ev("chan='exg'; localStorage.setItem('channel','exg'); setEdgeMode(); void 0")
    await asyncio.sleep(1.0)
    chk('fx表示中', await ev("fx.style.display === 'block' && fx.width > 0"), await ev("[fx.style.display, fx.width]"))
    await ev("window.__recTrack=null; window.__recIsCam=null; window.__dl=null; $('rec').click(); void 0")
    await asyncio.sleep(2.5)
    exgTrack = await ev("window.__recTrack"); exgIsCam = await ev("window.__recIsCam")
    await ev("$('rec').click(); void 0")
    await asyncio.sleep(2.5)
    exgDl = await ev("window.__dl ? JSON.stringify(window.__dl) : null")
    print('exg rec track:', exgTrack, '| isCam:', exgIsCam, '| dl:', exgDl)
    # fx canvasのtrackはカメラと別(label不一致・isCam=false)
    chk('exg録画=fxキャンバス(カメラ以外)', exgIsCam is False and str(exgTrack) != str(camLabel), f'track={exgTrack!r} cam={camLabel!r}')
    chk('exg録画WebM保存', exgDl and '動画.webm' in str(json.loads(exgDl).get('name','')), str(exgDl))
    # 後始末: RGBに戻しrecBake既定(ON)へ戻す
    await ev("chan='all'; localStorage.setItem('channel','all'); setEdgeMode(); recBake = true; localStorage.setItem('rec bake','1'); void 0")
    print(f'== OK={ok} NG={ng} ==')

asyncio.run(main())
