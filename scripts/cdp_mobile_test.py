# -*- coding: utf-8 -*-
# CxM Mobile(スマホ版)のE2E検証: 線分/角度/較正/差異/タイムラプス/レイアウト
import json, asyncio, urllib.request, websockets

def wsu():
    tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
    return [t for t in tabs if t['type']=='page'][0]['webSocketDebuggerUrl']

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
    # スマホ相当ビューポート(390x844)+タッチ
    await cmd('Emulation.setDeviceMetricsOverride', width=390, height=844, deviceScaleFactor=2, mobile=True)
    await cmd('Emulation.setTouchEmulationEnabled', enabled=True)
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/cxm-mobile.html?m=2')
    for _ in range(25):
        await asyncio.sleep(1)
        if await ev("!!window.setMode && !!window.talParams"): break
    chk('アプリ読込', 'v1.0' in str(await ev("APP_VER")), await ev("APP_VER"))
    # promptは自動応答(較正で'10'mm)
    await ev("window.prompt = () => '10'; void 0")
    # カメラ起動待ち
    cam = False
    for _ in range(15):
        if (await ev("video.videoWidth || (fileimg.naturalWidth||0)")): cam = True; break
        await asyncio.sleep(1)
    chk('映像ソース起動', cam, await ev("video.videoWidth"))
    # タブレイアウト: 4ボタンが1行・幅390以内
    lay = await ev("""(() => {
      const bs = ['m-seg','m-ang','m-cmp','m-tal'].map(i=>document.getElementById(i).getBoundingClientRect());
      return JSON.stringify({tops:[...new Set(bs.map(b=>Math.round(b.top)))],
        right: Math.round(Math.max(...bs.map(b=>b.right))),
        minH: Math.min(...bs.map(b=>Math.round(b.height)))});
    })()""")
    lay = json.loads(lay)
    chk('タブ4個1行', len(lay['tops'])==1 and lay['right']<=390, lay)
    chk('タブ高さ>=56px', lay['minH']>=56, lay)
    # タッチ操作ヘルパ(pointerdown)
    async def tap(x, y):
        await ev(f"""(() => {{ const r = stage.getBoundingClientRect();
          stage.dispatchEvent(new PointerEvent('pointerdown', {{bubbles:true,
            clientX: r.left+{x}, clientY: r.top+{y}}})); }})()""")
    # --- 線分測定(px) ---
    await tap(80, 100); await tap(280, 100)
    chk('線分1件', await ev("segs.length") == 1, await ev("segs.length"))
    chk('結果=px表示', 'px' in str(await ev("$('res').textContent")), await ev("$('res').textContent"))
    # --- 較正 ---
    await ev("$('calbtn').click(); void 0")
    chk('較正モード入', await ev("calActive") is True)
    await tap(50, 400); await tap(250, 400)  # 画面200px(=画像200/s px) = 10mm
    await asyncio.sleep(0.5)
    exp = await ev("10 / (200 / vfit().s)")
    got = await ev("mmPerPx()")
    chk('較正完了', got is not None and abs(got - exp) < 1e-9, f'got={got} exp={exp}')
    chk('較正localStorage', 'cxmm-cal' in str(await ev("JSON.stringify(Object.keys(localStorage))")))
    # --- 線分(mm追随) ---
    await tap(80, 150); await tap(280, 150)
    chk('線分mm表示', 'mm' in str(await ev("$('res').textContent")), await ev("$('res').textContent"))
    # --- 角度測定 ---
    await ev("$('m-ang').click(); void 0")
    chk('角度モード', await ev("mode") == 'ang')
    await tap(100, 300); await tap(200, 300); await tap(200, 150)  # 90度
    chk('角度1件', await ev("angles.length") == 1, await ev("angles.length"))
    chk('角度=90°', '90.00' in str(await ev("$('res').textContent")), await ev("$('res').textContent"))
    # --- 戻す/全消去 ---
    await ev("$('clr').click(); void 0")
    chk('全消去', await ev("segs.length + angles.length") == 0)
    # --- 差異検出 ---
    await ev("$('m-cmp').click(); void 0")
    await ev("$('cmpcap').click(); void 0")
    await asyncio.sleep(0.5)
    chk('差異: 基準固定', await ev("cmpOn && cmpRef && cmpRef.width>0") is True, await ev("cmpRef && cmpRef.width"))
    chk('差異: cmpcv表示', await ev("getComputedStyle(cmpcv).display") == 'block', await ev("getComputedStyle(cmpcv).display"))
    px = await ev("""(() => { const d = cmpcv.getContext('2d').getImageData(0, 0, cmpcv.width, cmpcv.height/2).data;
      let n=0; for (let i=3;i<d.length;i+=4) if (d[i]>0) n++; return n; })()""")
    chk('差異: 上半にReference描画', (px or 0) > 50000, px)  # 390x~219のcontain描画≈85kpx
    await ev("$('cmsoff').click(); void 0")
    chk('差異: 終了', await ev("cmpOn") is False)
    # --- タイムラプス ---
    await ev("$('m-tal').click(); void 0")
    await ev("""$('taltotal').value='1'; $('taln').value='60';
      $('taltotal').dispatchEvent(new Event('input')); void 0""")
    chk('TL情報', '倍速' in str(await ev("$('talinfo').textContent")), await ev("$('talinfo').textContent"))
    await ev("$('talbtn').click(); void 0")
    chk('TL開始', await ev("talRun") is True)
    await asyncio.sleep(3.5)
    ncap = await ev("talFrames.length")
    chk('TL撮影進行(>=3枠)', (ncap or 0) >= 3, ncap)
    await ev("$('talbtn').click(); void 0")  # 早期停止→合成
    toasts = []
    for _ in range(20):
        await asyncio.sleep(1)
        t = str(await ev("$('toast').textContent"))
        if '保存' in t or '共有' in t or '失敗' in t: toasts.append(t); break
    chk('TL合成完了', any('失敗' not in t for t in toasts), toasts)
    chk('TL停止状態', await ev("talRun") is False)
    # --- 画像保存 ---
    await ev("$('m-seg').click(); void 0")
    await tap(80, 100); await tap(280, 100)
    await ev("$('saveimg').click(); void 0")
    done = False
    for _ in range(10):
        await asyncio.sleep(1)
        t = str(await ev("$('toast').textContent"))
        if '保存' in t or '共有' in t: done = True; break
    chk('画像保存(焼き込み)', done, t)
    print(f'== {ok} PASS / {ng} NG ==')

asyncio.run(main())
