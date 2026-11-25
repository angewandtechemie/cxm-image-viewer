import json, asyncio, time, urllib.request, websockets
results=[]
def wsu():
    tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
    return [t for t in tabs if t['type']=='page' and '8642' in t['url']][0]['webSocketDebuggerUrl']
async def main():
    ws = await websockets.connect(wsu(), max_size=3*10**7); mid=0
    async def cmd(m, **p):
        nonlocal mid; mid+=1
        await ws.send(json.dumps({'id':mid,'method':m,'params':p}))
        while True:
            r=json.loads(await ws.recv())
            if r.get('id')==mid: return r
    async def ev(e):
        msg=await cmd('Runtime.evaluate', expression=e, returnByValue=True)
        res=msg.get('result',{})
        if 'exceptionDetails' in res: return 'JS-ERR '+json.dumps(res['exceptionDetails'])[:300]
        return res.get('result',{}).get('value')
    def ok(name, cond, detail=''):
        print(('OK  ' if cond else 'NG  ')+name+((' | '+str(detail)) if detail else ''))
        if not cond: results.append(name)

    await cmd('Page.enable')
    await cmd('Runtime.evaluate', expression="localStorage.setItem('tone', JSON.stringify({gamma:1,contrast:1,sharp:0,noise:0,avg:0,wb:[1,1,1]}))")
    await cmd('Emulation.setDeviceMetricsOverride', width=1600, height=900, deviceScaleFactor=1, mobile=False)
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v='+str(int(time.time())))
    for _ in range(20):
        await asyncio.sleep(1)
        if await ev("!!window.wbAuto && !!window.setWb") is True: break
    if await ev("!!window.wbAuto") is not True:
        print('FAIL: アプリ読み込み失敗'); return
    hh = await ev("[...document.querySelectorAll('.hrow')].map(r=>Math.round(r.getBoundingClientRect().height))")
    ok('1600pxでヘッダー2行', isinstance(hh,list) and len(hh)==2 and all(h<120 for h in hh), hh)
    await ev("window.__raf0 = window.requestAnimationFrame; window.requestAnimationFrame = () => 0; video.requestVideoFrameCallback = () => 0;")
    for _ in range(15):
        await asyncio.sleep(1)
        if await ev("video.videoWidth > 0") is True: break
    async def vidpx(x=400, y=300):
        return await ev("""(() => { const c=document.createElement('canvas'); c.width=800; c.height=600;
          const g=c.getContext('2d'); g.drawImage(video,0,0); const d=g.getImageData(%d,%d,1,1).data; return [d[0],d[1],d[2]]; })()""" % (x,y))
    async def wait_vid_rgb(rgb, x=400, y=300):
        for _ in range(60):
            p = await vidpx(x,y)
            if p==list(rgb): return True
            await asyncio.sleep(0.1)
        print('   wait_vid last=%r' % (p,))
        return False
    # 合成ストリーム(カメラ完了待ち+再試行)
    await asyncio.sleep(3)
    for attempt in range(4):
        await ev("""(() => {
          const c = document.createElement('canvas'); c.width=800; c.height=600;
          window.__c=c; window.__g=c.getContext('2d');
          window.__fillRGB = (r,g,b) => { const gg=window.__g; gg.fillStyle='rgb('+r+','+g+','+b+')'; gg.fillRect(0,0,800,600); };
          window.__g.fillStyle='rgb(200,100,100)'; window.__g.fillRect(0,0,800,600);
          video.srcObject = c.captureStream(30); video.play();
        })(); 'synth'""")
        for _ in range(10):
            await asyncio.sleep(1)
            if await ev("video.videoWidth === 800") is True: break
        await asyncio.sleep(2)
        if await ev("video.videoWidth === 800") is True and await vidpx()==[200,100,100]:
            break
        print('   synth差し替え再試行', attempt+1)
    ok('合成(200,100,100)安定', await wait_vid_rgb([200,100,100]))
    async def fxpx():
        return await ev("""(() => { const c=document.createElement('canvas'); c.width=fx.width; c.height=fx.height;
          const g=c.getContext('2d'); g.drawImage(fx,0,0);
          const d=g.getImageData(Math.round(fx.width/2),Math.round(fx.height/2),1,1).data; return [d[0],d[1],d[2]]; })()""")
    async def accumpx():
        return await ev("(() => { const d=frameData().data; const i=(300*800+400)*4; return [d[i],d[i+1],d[i+2]]; })()")
    def near3(a,b,tol=3): return all(abs(x-y)<=tol for x,y in zip(a,b))

    # 手動WB: (0.5,1,2) → (100,100,200)
    await ev("$('wbr').value='50'; $('wbr').oninput(); $('wbb').value='200'; $('wbb').oninput();")
    await asyncio.sleep(1.5)
    a = await accumpx()
    ok('解析側WB厳密(100,100,200)', a==[100,100,200], a)
    g = await fxpx()
    ok('GL表示=解析値(±3)', near3(g,a), (g,a))
    st = await ev("""(() => { const t=JSON.parse(localStorage.getItem('tone'));
      return {wb:t.wb, r:$('wbrv').textContent, b:$('wbbv').textContent, on:$('tonebtn').classList.contains('on')}; })()""")
    ok('WB永続化+UI', st['wb']==[0.5,1,2] and st['r']=='0.50' and st['b']=='2.00' and st['on'], st)
    cd = await ev("JSON.stringify(conditionsData().tone.wb)")
    ok('条件JSONにwb', json.loads(cd)==[0.5,1,2], cd)

    # 自動WB(グレイワールド): 偏色(200,150,100) → 平均揃え(150,150,150)
    await ev("$('wbr').value='100'; $('wbr').oninput(); $('wbb').value='100'; $('wbb').oninput();")  # ゲイン戻す
    await ev("window.__fillRGB(200,150,100); 'cast'")
    ok('偏色フレーム到着', await wait_vid_rgb([200,150,100]))
    await ev("wbAuto(); 'auto'")
    await asyncio.sleep(1.5)
    a = await accumpx()
    ok('自動WBで中立化(150±2)', near3(a,[150,150,150],2), a)
    gains = await ev("JSON.stringify(tone.wb)")
    print('   自動ゲイン:', gains)

    # リセットでwbも戻る
    await ev("$('toneset').click();")
    st2 = await ev("""(() => { const t=JSON.parse(localStorage.getItem('tone'));
      return {wb:t.wb, on:$('tonebtn').classList.contains('on')}; })()""")
    ok('リセットでwb=[1,1,1]', st2['wb']==[1,1,1] and not st2['on'], st2)
    await asyncio.sleep(1.5)
    a = await accumpx()
    ok('リセット後(200,150,100)復元', a==[200,150,100], a)

    # 後始末
    await ev("""(() => {
      localStorage.setItem('tone', JSON.stringify({gamma:1,contrast:1,sharp:0,noise:0,avg:0,wb:[1,1,1]}));
      window.requestAnimationFrame = window.__raf0;
      (async()=>{await start();})();
    })(); 'restore'""")
    await asyncio.sleep(3)
    print('ALL PASS' if not results else 'FAILURES: '+str(results))
    await ws.close()
asyncio.run(main())
