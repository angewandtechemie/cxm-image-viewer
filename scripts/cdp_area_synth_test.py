# 領域測定アルゴリズム決定的検証: 既知の円5個を合成映像に差し替え count/面積/比率を照合
import json, asyncio, urllib.request, websockets

def wsu():
    tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
    return [t for t in tabs if t['type']=='page' and '8642' in t['url']][0]['webSocketDebuggerUrl']

EXP = {  # 円の半径(px) -> 期待面積(px²)
    30: 2827.4, 20: 1256.6, 25: 1963.5, 15: 706.9, 40: 5026.5}

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
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v=area2')
    for _ in range(25):
        await asyncio.sleep(1)
        if await ev("video.videoWidth"): break
    # 合成映像に差替え(4K黒背景に白い円5個、ROI内と外にまたがる配置)
    await ev("""
      (() => {
        const c = document.createElement('canvas'); c.width=3840; c.height=2160;
        const g = c.getContext('2d');
        g.fillStyle='#000'; g.fillRect(0,0,3840,2160);
        g.fillStyle='#fff';
        for (const [x,y,r] of [[500,500,30],[900,800,20],[700,1200,25],[1300,600,15],[1100,1000,40]]) {
          g.beginPath(); g.arc(x,y,r,0,7); g.fill();
        }
        video.srcObject = c.captureStream(30); video.play();
        window.__synth = true;
      })(); 'synth'
    """)
    await asyncio.sleep(2)
    print('vvid:', await ev("video.videoWidth + 'x' + video.videoHeight"), 'synth:', await ev("!!window.__synth"))
    # 粒子解析モード(areaStatsはmode='part'でのみ動作)、全画像ROI、明るい画素、閾値128、最小50
    print('mode:', await ev("document.getElementById('m-part').click(); mode"))
    print('stats:', await ev("""
      thr=128; polarity='light'; minArea=50;
      areas=[{pts:[{x:0,y:0},{x:3840,y:0},{x:3840,y:2160},{x:0,y:2160}],key:curKey()}];
      areaStats(); $('areaStats').textContent
    """))
    comps = await ev("JSON.stringify(areaComps.map(o=>({cx:Math.round(o.cx),cy:Math.round(o.cy),a:o.areaPx})))")
    got = json.loads(comps)
    print('comps n=%d' % len(got))
    exp_sorted = sorted(EXP.values(), reverse=True)
    got_sorted = sorted([o['a'] for o in got], reverse=True)
    ok_count = len(got) == 5
    print('count 5 expected:', ok_count)
    for e, g in zip(exp_sorted, got_sorted):
        err = abs(g - e) / e * 100
        print(f'  area exp={e:.0f} got={g} err={err:.1f}%')
    # 部分ROI: 円2個だけを囲む矩形 -> count=2, 領域比=Σ円/ROI
    print('partial:', await ev("""
      areas=[{pts:[{x:400,y:400},{x:1000,y:400},{x:1000,y:900},{x:400,y:900}],key:curKey()}];
      areaStats(); $('areaStats').textContent
    """))
    exp_ratio = (2827.4+1256.6)/ (600*500) * 100
    print(f'  (期待: カウント2, 領域比≈{exp_ratio:.1f}%)')
    # 最小面積フィルタ: minArea=1500 -> 円3個のみ
    print('min1500 n:', await ev("""
      minArea=1500; areas=[{pts:[{x:0,y:0},{x:3840,y:0},{x:3840,y:2160},{x:0,y:2160}],key:curKey()}];
      areaStats(); areaComps.length
    """), '(期待3)')
    # 後片付け: 実カメラ再開
    await ev("""
      areas=[]; minArea=+(localStorage.getItem('area min')||50);
      document.getElementById('m-dist').click();
      (async()=>{await start();})(); 'restore'
    """)
    for _ in range(10):
        await asyncio.sleep(2)
        v = await ev("video.videoWidth")
        if v: break
    print('camera restored:', v)
    await ws.close()

asyncio.run(main())
