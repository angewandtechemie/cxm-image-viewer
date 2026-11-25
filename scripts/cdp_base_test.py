# -*- coding: utf-8 -*-
# 基礎表示メニュー(スケール/日時/ルーラー/サンプル名)のE2E検証
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
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v=base1')
    for _ in range(20):
        await asyncio.sleep(1)
        if await ev("!!window.openStaticMenu"): break
    print('app loaded:', await ev("APP_VER"))
    chk('ヘッダー2行', await ev("document.querySelectorAll('.hrow').length") == 2)
    chk('グループ見出し=表示項目の設定', '表示項目の設定' in str(await ev("[...document.querySelectorAll('.cap')].map(c=>c.textContent).join('|')")), await ev("[...document.querySelectorAll('.cap')].map(c=>c.textContent).join('|')"))
    print('row right edges:', await ev("""JSON.stringify([...document.querySelectorAll('.hrow')].map(r=>
      Math.round(Math.max(...[...r.children].map(c=>c.getBoundingClientRect().right)))))"""), '(期待 <=1600)')
    chk('基礎表示ボタン存在', await ev("!!document.getElementById('basebtn')"))
    chk('4トグルはbasemenu内', await ev("""['scale','tstamp','ruler','tsamp'].every(i=>
      document.getElementById('basemenu').contains(document.getElementById(i)))"""))
    # メニュー開閉
    await ev("$('basebtn').click(); 'open'")
    chk('メニュー開', await ev("getComputedStyle($('basemenu')).display") == 'flex')
    # トグル動作(メニューは開いたまま): ルーラーOFF→.on消灯→ON
    st0 = await ev("rulerOn")
    await ev("$('ruler').click(); void 0")
    chk('ルーラー反転', await ev("rulerOn") == (not st0))
    chk('ルーラーボタン.on追随', await ev("$('ruler').classList.contains('on')") == await ev("rulerOn"))
    await ev("$('ruler').click(); void 0")
    chk('ルーラー復帰', await ev("rulerOn") == st0)
    # 他トグルのON/OFF追随
    for bid, var in [('scale','scaleBarOn'), ('tstamp','tstampOn'), ('tsamp','tsampOn')]:
        s0 = await ev(var)
        await ev(f"$('{bid}').click(); void 0")
        s1 = await ev(f"{var} === {str(not s0).lower()} && $('{bid}').classList.contains('on') === {str(not s0).lower()}")
        await ev(f"$('{bid}').click(); void 0")
        chk(f'{bid} トグル追随', s1 is True)
    # メニュー内クリックでは閉じない
    chk('メニュー開いたまま', await ev("getComputedStyle($('basemenu')).display") == 'flex')
    # サンプル名入力が生効き(ステータス/焼き込み名)
    await ev("$('sampname').value='TEST-01'; $('sampname').dispatchEvent(new Event('input')); void 0")
    chk('サンプル名保持', 'TEST-01' in str(await ev("fileBase()")), await ev("fileBase()"))
    # 外側クリックで閉じる
    await ev("document.body.dispatchEvent(new PointerEvent('pointerdown', {bubbles:true})); void 0")
    await asyncio.sleep(0.3)
    chk('外側クリックで閉', await ev("getComputedStyle($('basemenu')).display") == 'none')
    # スケールバー(11-24〜): 主/副目盛り廃止、単一の塗りバー。厚み=旧副目盛り高さ(2*tickH*2/3)
    bar = await ev("""(() => {
      const c = document.createElement('canvas'); c.width = 420; c.height = 220;
      const ctx = c.getContext('2d');
      drawScaleBar(ctx, 0.01, () => 200, 400, 200, 28, []);  // fs=28で描く(コードはfs非依存)
      const d = ctx.getImageData(0, 0, 420, 220).data;
      const W = (x, y) => { const i = (y*420+x)*4; return d[i]>120 && d[i+1]>120 && d[i+2]>120; };
      let ly = -1, best = 0;
      for (let y = 0; y < 220; y++) { let n = 0; for (let x = 0; x < 420; x++) if (W(x,y)) n++; if (n > best) { best = n; ly = y; } }
      // バー行の連続白runと、バー行の厚さ(連続行)、バー上に独立目盛り列が無いことを取る
      let run = 0, maxrun = 0, x0 = -1, bx0 = -1;
      for (let x = 0; x < 420; x++) { if (W(x,ly)) { if (!run) x0 = x; run++; if (run>maxrun){maxrun=run;bx0=x0;} } else run = 0; }
      let th = 0;
      for (let y = ly; y >= 0 && W(bx0, y); y--) th++;
      for (let y = ly+1; y < 220 && W(bx0, y); y++) th++;
      let above = 0;  // バー上端より上に白列(旧目盛り)があれば検出
      for (let x = bx0; x < bx0+maxrun; x++) for (let y = 0; y < ly-th; y++) if (W(x,y)) { above++; break; }
      return JSON.stringify({ maxrun, th, above });
    })()""")
    import json as _j
    b = _j.loads(bar)
    print('bar:', b)
    chk('バー長≈200px', 195 <= b['maxrun'] <= 205, str(b))
    # fs=28: barH=max(8,19.6)*4/3=26.1 → 実測24-28px
    chk('バー厚み=旧副目盛高さ(24-28px@fs28)', 24 <= b['th'] <= 28, str(b['th']))
    chk('独立目盛りなし', b['above'] == 0, str(b['above']))
    await cmd('Emulation.clearDeviceMetricsOverride')
    print(f'--- {ok} PASS / {ng} NG')

asyncio.run(main())
