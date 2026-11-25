# -*- coding: utf-8 -*-
# インターバル撮影の2形式(画像/タイムラプス動画・30fps固定・60分→n秒短縮)のE2E検証
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
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v=tl1')
    for _ in range(20):
        await asyncio.sleep(1)
        if await ev("!!window.talParams"): break
    print('app loaded:', await ev("APP_VER"))
    # 合成映像
    await ev("""(() => { const c=document.createElement('canvas'); c.width=800; c.height=600;
      const g=c.getContext('2d'); g.fillStyle='rgb(100,100,100)'; g.fillRect(0,0,800,600);
      video.srcObject=c.captureStream(30); video.play(); })(); 'synth'""")
    for _ in range(15):
        await asyncio.sleep(1)
        if await ev("video.videoWidth===800"): break
    # 1) 既定値: 60分→60秒 = 60倍速・T=2秒・1800枠
    t = json.loads(await ev("JSON.stringify(talParams())"))
    chk('既定: 60倍速', abs(t['x']-60) < 1e-9, t)
    chk('既定: T=2秒', abs(t['T']-2) < 1e-9, t)
    chk('既定: 1800枠', t['frames'] == 1800, t)
    chk('talinfo表示', '60倍速' in str(await ev("$('talinfo').textContent")), await ev("$('talinfo').textContent"))
    # 1c) 数値自由入力: number入力に値を入れてtalInfoが追随する
    itype = await ev("JSON.stringify(['tintv','tincnt','taltotal','taln'].map(i=>$(i).type))")
    chk('4項目ともnumber入力', json.loads(itype) == ['number']*4, itype)
    await ev("$('taltotal').value='30'; $('taln').value='60'; talInfo(); 'in1'")
    chk('入力追随(30分→60秒=30倍速)', '30倍速' in str(await ev("$('talinfo').textContent")), await ev("$('talinfo').textContent"))
    await ev("$('taltotal').value='7'; $('taln').value='13'; talInfo(); 'in2'")
    x7 = 7*60/13
    chk('任意値7分→13秒', f'{round(x7)}倍速' in str(await ev("$('talinfo').textContent")), await ev("$('talinfo').textContent"))
    # 1d) 表記: 「n秒ごとにm枚撮影」「60分を60秒に短縮」
    txt = await ev("$('tincmenu').innerText")
    chk('画像間隔の文表記', 'ごとに' in txt and '撮影' in txt, txt[:120])
    chk('タイムラプスの文表記', 'を' in txt and 'に短縮' in txt, txt[:200])
    # 2) 10分→10秒 = 60倍速(同じ)、10分→120秒=5倍速→T下限1秒
    await ev("$('taltotal').value='10'; $('taln').value='120'; talInfo(); 'cfg'")
    t = json.loads(await ev("JSON.stringify(talParams())"))
    chk('10分→120秒: 5倍速', abs(t['x']-5) < 1e-9, t)
    chk('T下限1秒', abs(t['T']-1) < 1e-9, t)
    # 3) タイムラプス実行: 10分→10秒(T=2秒)で開始、3枠で手動停止→合成
    await ev("$('taltotal').value='10'; $('taln').value='10'; 'cfg2'")
    await ev("$('talbtn').click(); 'start'")
    st = str(await ev("status.textContent"))
    chk('開始メッセージに倍速・30fps', '60倍速' in st and '30fps' in st, st)
    await asyncio.sleep(5)  # t=0,2,4で3枠
    await ev("$('talbtn').click(); 'stop'")
    for _ in range(20):
        await asyncio.sleep(1)
        st = str(await ev("status.textContent"))
        if '保存しました' in st or '失敗' in st: break
    chk('合成完了メッセージ', 'タイムラプス動画(3フレーム' in st and '30fps' in st, st)
    chk('ボタン消灯', await ev("!document.getElementById('tincbtn').classList.contains('on') && !$('talbtn').classList.contains('on')"))
    # 4) 画像間隔撮影の独立ボタン回帰: 開始→停止
    await ev("$('tintv').value='5'; $('tincnt').value='10'; 'cfg3'")
    st = str(await ev("$('tinc').click(); status.textContent"))  # fps表示で上書きされるため同一evaluateで読む
    chk('画像モード開始メッセージ', '画像保存' in st, st)
    await ev("$('tinc').click(); 'stop2'")
    print(f'--- {ok} PASS / {ng} NG')

asyncio.run(main())
