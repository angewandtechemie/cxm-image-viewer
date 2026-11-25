# 階層メニュー化(回転・倍率/グリッド)のE2E検証: ヘッダー2行維持、メニュー開閉、配線(rot/Rキー/grid/zoom/gridstep)動作
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
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v=menu1')
    for _ in range(20):
        await asyncio.sleep(1)
        if await ev("!!window.openStaticMenu"): break
    print('app loaded:', await ev("APP_VER"))
    # 合成映像(解像度選択肢生成のため)
    await ev("""
      (() => {
        const c = document.createElement('canvas'); c.width=900; c.height=600;
        const g = c.getContext('2d');
        g.fillStyle='rgb(100,100,100)'; g.fillRect(0,0,900,600);
        video.srcObject = c.captureStream(30); video.play();
      })(); 'synth'
    """)
    for _ in range(15):
        await asyncio.sleep(1)
        if await ev("video.videoWidth"): break
    print('synth video:', await ev("video.videoWidth + 'x' + video.videoHeight"))
    # 1) ヘッダーは物理2行のまま・折返しなし・ページスクロールなし
    print('hrow count:', await ev("document.querySelectorAll('.hrow').length"), '(期待2)')
    print('row wrap(offsetTop):', await ev("""JSON.stringify([...document.querySelectorAll('.hrow')].map(r=>{
      const kids=[...r.children].filter(k=>getComputedStyle(k).display!=='none');
      return new Set(kids.map(k=>k.offsetTop)).size;}))"""), '(各行期待1=折返しなし)')
    print('page fit:', await ev("document.documentElement.scrollHeight <= document.documentElement.clientHeight"))
    print('画面表示 group:', await ev("""(()=>{const g=[...document.querySelectorAll('.grp')].find(g=>{const c=g.querySelector('.cap');return c&&c.textContent==='画面表示';});
      return JSON.stringify([...g.querySelector('.row').children].map(c=>c.id));})()"""), '(期待 rotbtn,gridbtn,tonebtn — edgeはrotmenuへ移設11-24)')
    # 2) 回転・倍率メニュー: 開く→項目→回転2回→Rキー→倍率→閉じる
    await ev("document.getElementById('rotbtn').click(); 'open'")
    print('rotmenu display:', await ev("getComputedStyle(document.getElementById('rotmenu')).display"), '(期待flex)')
    print('rotmenu items:', await ev("JSON.stringify([...document.getElementById('rotmenu').querySelectorAll('button,select')].map(e=>e.id))"), "(期待 rot,mirror,zoom,edge)")
    await ev("document.getElementById('rot').click(); document.getElementById('rot').click(); 'rot x2'")
    print('rot after 2 clicks:', await ev("rot"), '(期待180)')
    await ev("document.getElementById('rot').textContent")
    await cmd('Input.dispatchKeyEvent', type='keyDown', code='KeyR', windowsVirtualKeyCode=82)
    await cmd('Input.dispatchKeyEvent', type='keyUp', code='KeyR', windowsVirtualKeyCode=82)
    print('rot after R key:', await ev("rot"), '(期待270)')
    print('rot label:', await ev("document.getElementById('rot').textContent"), "(期待'回転(R) 270°')")
    await ev("document.getElementById('mirror').click(); 'mirror'")
    print('mirrored:', await ev("mirrored"), '(期待True)')
    await ev("""(()=>{const z=document.getElementById('zoom');z.value='2';z.dispatchEvent(new Event('change'));})()""")
    print('zoom:', await ev("zoom"), '(期待2)')
    # エッジ検出トグル(rotmenu内、11-24移設): ON→.on→OFF。メニューは開いたまま
    await ev("document.getElementById('edge').click(); 'edge on'")
    print('edgeOn:', await ev("edgeOn"), '(期待True)')
    print('edge .on:', await ev("document.getElementById('edge').classList.contains('on')"), '(期待True)')
    await ev("document.getElementById('edge').click(); 'edge off'")
    print('edgeOn off:', await ev("edgeOn"), '(期待False)')
    # メニュー内操作で閉じない(回転ボタンは連打前提)
    print('rotmenu still open:', await ev("getComputedStyle(document.getElementById('rotmenu')).display"), '(期待flex)')
    # 3) グリッドメニュー: 開く→項目→グリッド表示ON→gridbtn .on→細かさ選択肢→色→外側クリックで閉
    # (メニュー切替は実ポインタ経路で確認: .click()はpointerdownを出さないため閉じる側は素イベントで検証ずみ)
    await ev("""(()=>{const b=document.getElementById('gridbtn');
      b.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));
      b.dispatchEvent(new PointerEvent('pointerup',{bubbles:true}));
      b.click();})()""", )
    print('gridmenu display:', await ev("getComputedStyle(document.getElementById('gridmenu')).display"), '(期待flex)')
    print('gridmenu items:', await ev("JSON.stringify([...document.getElementById('gridmenu').querySelectorAll('button,select,input')].map(e=>e.id))"), '(期待 grid,gridcolor,gridstep)')
    print('rotmenu closed by switch:', await ev("getComputedStyle(document.getElementById('rotmenu')).display"), '(期待none)')
    await ev("document.getElementById('grid').click(); 'grid on'")
    print('gridOn:', await ev("gridOn"), '(期待True)')
    print('gridbtn .on:', await ev("document.getElementById('gridbtn').classList.contains('on')"), '(期待True)')
    print('grid item .on:', await ev("document.getElementById('grid').classList.contains('on')"), '(期待True)')
    print('gridstep options:', await ev("document.getElementById('gridstep').options.length"), '(期待>=2)')
    await ev("""(()=>{const s=document.getElementById('gridstep');s.value='auto';s.dispatchEvent(new Event('change'));})()""")
    print('gridstep value:', await ev("$('gridstep').value"), '(期待auto)')
    # 4) 外側クリックで閉じる
    await ev("document.getElementById('stage').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true})); 'outside'")
    print('gridmenu after outside:', await ev("getComputedStyle(document.getElementById('gridmenu')).display"), '(期待none)')
    # 5) 後片付け
    await ev("""(()=>{
      gridOn=false; syncGridBtn(); drawOverlay();
      rot=0; mirrored=false; zoom=1;
      document.getElementById('rot').textContent='回転(R) 0°';
      document.getElementById('mirror').classList.remove('on');
      document.getElementById('zoom').value='1';
      applyTransform();
      const s=document.getElementById('gridstep'); s.value=localStorage.getItem('grid step')||'px';
      'restored';
    })()""")
    await cmd('Emulation.clearDeviceMetricsOverride')
    await ws.close()

asyncio.run(main())
