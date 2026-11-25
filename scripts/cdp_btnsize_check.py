# -*- coding: utf-8 -*-
# 撮影/動画/間隔撮影ボタンの同サイズ化と1600pxヘッダー2行の検証
import json, asyncio, urllib.request, websockets

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
        if 'exceptionDetails' in res: return 'JS-ERR '+json.dumps(res['exceptionDetails'])[:400]
        return res.get('result',{}).get('value')
    await cmd('Page.enable'); await cmd('Page.bringToFront')
    await cmd('Emulation.setDeviceMetricsOverride', width=1600, height=900, deviceScaleFactor=1, mobile=False)
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v=btnsize')
    for _ in range(20):
        await asyncio.sleep(1)
        if await ev("!!window.tincToggle"): break
    print('app loaded:', await ev("APP_VER"))
    print('btn sizes:', await ev("""JSON.stringify(['shot','recbtn','tincbtn'].map(id=>{
      const r=document.getElementById(id).getBoundingClientRect();
      return [id, Math.round(r.width), Math.round(r.height)];}))"""), '(期待 3つとも同一サイズ)')
    print('row tops:', await ev("""JSON.stringify([...document.querySelectorAll('.hrow')].map(r=>
      [...r.children].map(c=>Math.round(c.getBoundingClientRect().top))))"""),
      '(各行のtop値が2種以内=行内折返しなし)')
    print('row right edges:', await ev("""JSON.stringify([...document.querySelectorAll('.hrow')].map(r=>
      Math.round(Math.max(...[...r.children].map(c=>c.getBoundingClientRect().right)))))"""),
      '(期待 各値<=1600)')
    print('hrow count:', await ev("document.querySelectorAll('.hrow').length"), '(期待2)')
    # 間隔撮影トグルの同期(ヘッダーボタン開始→tinc停止表示→ヘッダー停止で終了)
    await ev("""(() => { const c=document.createElement('canvas'); c.width=800; c.height=600;
      const g=c.getContext('2d'); g.fillStyle='rgb(100,100,100)'; g.fillRect(0,0,800,600);
      video.srcObject=c.captureStream(30); video.play(); })(); 'synth'""")
    for _ in range(15):
        await asyncio.sleep(1)
        if await ev("video.videoWidth===800"): break
    await ev("$('tintv').value='5'; $('tincnt').value='10'; 'cfg'")
    # インターバルボタン=メニュー開閉(設定はメニュー内)、開始/停止はメニュー内の独立ボタン
    await ev("document.getElementById('tincbtn').click(); 'menu'")
    print('tincmenu open:', await ev("getComputedStyle(document.getElementById('tincmenu')).display"), '(期待flex)')
    await ev("$('tinc').click(); 'start'")
    print('tincbtn .on:', await ev("document.getElementById('tincbtn').classList.contains('on')"), '(期待True)')
    print('tinc label:', await ev("$('tinc').textContent"), '(期待 ⏹ 停止..に相当)')
    await asyncio.sleep(1)
    await ev("$('tinc').click(); 'stop'")
    print('tincbtn off:', await ev("document.getElementById('tincbtn').classList.contains('on')"), '(期待False)')
    await cmd('Emulation.clearDeviceMetricsOverride')

asyncio.run(main())
