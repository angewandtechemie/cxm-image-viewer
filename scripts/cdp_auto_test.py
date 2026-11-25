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
        if await ev("!!window.autoTone") is True: break
    if await ev("!!window.autoTone") is not True:
        print('FAIL: アプリ読み込み失敗'); return
    hh = await ev("[...document.querySelectorAll('.hrow')].map(r=>Math.round(r.getBoundingClientRect().height))")
    ok('1600pxでヘッダー2行', isinstance(hh,list) and len(hh)==2 and all(h<120 for h in hh), hh)
    # tonemenu最上部に全自動補正ボタン
    top = await ev("(() => { const m=document.getElementById('tonemenu'); m.style.display='flex'; const c=m.children[0]; m.style.display='none'; return {id:c.id, txt:c.textContent}; })()")
    ok('全自動補正ボタンがメニュー最上部', isinstance(top,dict) and top.get('id')=='toneauto', top)
    await ev("window.__raf0 = window.requestAnimationFrame; window.requestAnimationFrame = () => 0; video.requestVideoFrameCallback = () => 0;")
    for _ in range(15):
        await asyncio.sleep(1)
        if await ev("video.videoWidth > 0") is True: break
    async def vidpx(x=400, y=300):
        return await ev("""(() => { const c=document.createElement('canvas'); c.width=800; c.height=600;
          const g=c.getContext('2d'); g.drawImage(video,0,0); const d=g.getImageData(%d,%d,1,1).data; return [d[0],d[1],d[2]]; })()""" % (x,y))
    async def wait_vid(v, x=400, y=300):
        for _ in range(60):
            p = await vidpx(x,y)
            if p[0]==v and p[1]==v and p[2]==v: return True
            await asyncio.sleep(0.1)
        print('   wait_vid last=%r' % (p,))
        return False
    # 合成ストリーム(ノイズ生成ヘルダつき)
    await asyncio.sleep(3)
    for attempt in range(4):
        await ev("""(() => {
          const c = document.createElement('canvas'); c.width=800; c.height=600;
          window.__c=c; window.__g=c.getContext('2d');
          window.__fill = (v) => { const g=window.__g; g.fillStyle='rgb('+v+','+v+','+v+')'; g.fillRect(0,0,800,600); };
          window.__fillRGB = (r,g,b) => { const gg=window.__g; gg.fillStyle='rgb('+r+','+g+','+b+')'; gg.fillRect(0,0,800,600); };
          window.__fillNoise = (base, amp) => {  // 一様な暗い基調+iidノイズ(生成後は静止)
            const im=window.__g.createImageData(800,600), d=im.data;
            for(let i=0;i<d.length;i+=4){ const v=Math.max(0,Math.min(255,base+(Math.random()*2-1)*amp)); d[i]=d[i+1]=d[i+2]=v; d[i+3]=255; }
            window.__g.putImageData(im,0,0);
          };
          window.__fill(100);
          video.srcObject = c.captureStream(30); video.play();
        })(); 'synth'""")
        for _ in range(10):
            await asyncio.sleep(1)
            if await ev("video.videoWidth === 800") is True: break
        await asyncio.sleep(2)
        if await ev("video.videoWidth === 800") is True and await vidpx()==[100,100,100]:
            break
        print('   synth差し替え再試行', attempt+1)
    ok('合成100安定', await wait_vid(100))
    async def tonestate():
        return await ev("""(() => { const t=JSON.parse(localStorage.getItem('tone'));
          return {g:t.gamma,c:t.contrast,n:t.noise,a:t.avg,wb:t.wb}; })()""")
    def near(a,b,tol): return abs(a-b)<=tol

    # ケースA: 暗い+高ノイズ(60±25) → ガンマ>1、中央値/ガウシアンon、静止なのでフレーム平均on
    await ev("window.__fillNoise(60,25); 'noise'")
    arrived=False
    for _ in range(60):
        p=await vidpx()
        if 35<=p[0]<=85: arrived=True; break
        await asyncio.sleep(0.1)
    ok('ノイズフレーム到着(35-85範囲)', arrived)
    await ev("autoTone(); 'autoA'")
    await asyncio.sleep(1.5)
    st = await tonestate()
    ok('A: ガンマ持ち上げ(1.4-2.0)', 1.4<=st['g']<=2.0, st['g'])
    ok('A: ノイズ低減on(2)', st['n']==2, st['n'])
    ok('A: 静止+高ノイズ→フレーム平均8', st['a']==8, st['a'])
    ok('A: WBは中立のまま', all(near(v,1,0.02) for v in st['wb']), st['wb'])
    ok('A: コントラスト1.0-1.5', 1.0<=st['c']<=1.5, st['c'])
    # GL表示と解析値の一致(ノイズ低減後・LUT後の同一画素)
    cmpv = await ev("""(() => { const c=document.createElement('canvas'); c.width=fx.width; c.height=fx.height;
      const g=c.getContext('2d'); g.drawImage(fx,0,0);
      const gp=g.getImageData(Math.round(fx.width/2),Math.round(fx.height/2),1,1).data;
      const d=frameData().data; const i=(300*800+400)*4;
      return [gp[0]-d[i],gp[1]-d[i+1],gp[2]-d[i+2]]; })()""")
    ok('A: GL表示=解析値(±3)', all(abs(v)<=3 for v in cmpv), cmpv)

    # ケースB: 偏色フラット(200,150,100) → WB自動、ガンマ<1、ノイズ/平均off
    await ev("window.__fillRGB(200,150,100); 'cast'")
    got=False
    for _ in range(60):
        p=await vidpx()
        if p==[200,150,100]: got=True; break
        await asyncio.sleep(0.1)
    ok('偏色フレーム到着(実)', got)
    await ev("autoTone(); 'autoB'")
    await asyncio.sleep(1.5)
    st = await tonestate()
    ok('B: WBゲイン(0.75,1,1.5)±0.03', near(st['wb'][0],0.75,0.03) and near(st['wb'][1],1,0.03) and near(st['wb'][2],1.5,0.03), st['wb'])
    ok('B: 明るい→ガンマ<1', st['g']<1.0, st['g'])
    ok('B: ノイズ0・平均0', st['n']==0 and st['a']==0, (st['n'],st['a']))

    # ケースC: 高輝度フラット220 → ガンマ<1、他off
    await ev("window.__fill(220); 'bright'")
    ok('220フレーム到着', await wait_vid(220))
    await ev("autoTone(); 'autoC'")
    await asyncio.sleep(1.5)
    st = await tonestate()
    ok('C: ガンマ<1・ノイズ0・平均0', st['g']<1.0 and st['n']==0 and st['a']==0, st)

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
