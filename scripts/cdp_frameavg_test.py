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
    # toneはidentity+avg0から開始(localStorage汚染除去)
    await cmd('Runtime.evaluate', expression="localStorage.setItem('tone', JSON.stringify({gamma:1,contrast:1,sharp:0,noise:0,avg:0}))")
    await cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v='+str(int(time.time())))
    for _ in range(20):
        await asyncio.sleep(1)
        if await ev("!!window.frameData && !!window.srcAvgCanvas") is True: break
    if await ev("!!window.frameData") is not True:
        print('FAIL: アプリ読み込み失敗'); return
    # rAF停止(test側でrenderGLを1回ずつ呼ぶ)
    await ev("window.__raf0 = window.requestAnimationFrame; window.requestAnimationFrame = () => 0; video.requestVideoFrameCallback = () => 0;")
    for _ in range(15):
        await asyncio.sleep(1)
        if await ev("video.videoWidth > 0") is True: break
    async def vidpx():
        return await ev("""(() => { const c=document.createElement('canvas'); c.width=800; c.height=600;
          const g=c.getContext('2d'); g.drawImage(video,0,0); return g.getImageData(400,300,1,1).data[0]; })()""")
    # カメラのstart()完了まで待ってから合成ストリームへ差し替え(カメラ再確保に負けないよう再試行)
    await asyncio.sleep(3)
    for attempt in range(4):
        await ev("""(() => {
          const c = document.createElement('canvas'); c.width=800; c.height=600;
          window.__c=c; window.__g=c.getContext('2d');
          window.__fill = (v) => { const g=window.__g; g.fillStyle='rgb('+v+','+v+','+v+')'; g.fillRect(0,0,800,600); };
          window.__g.fillStyle='rgb(100,100,100)'; window.__g.fillRect(0,0,800,600);
          video.srcObject = c.captureStream(30); video.play();
        })(); 'synth'""")
        for _ in range(10):
            await asyncio.sleep(1)
            if await ev("video.videoWidth === 800") is True: break
        await asyncio.sleep(2)
        if await ev("video.videoWidth === 800") is True and await vidpx()==100:
            break
        print('   synth差し替え再試行', attempt+1)
    async def wait_vid(v):
        last=None
        for _ in range(30):
            x = await vidpx()
            if x==v: return True
            last=x
            await asyncio.sleep(0.1)
        print('   wait_vid(%d) last=%r' % (v,last))
        return False
    async def set_avg(a):
        # UI経由: setToneが累積リセットし、同一呼び出し内のrenderGLがクリーンコピーを書く
        await ev("$('tavg').value='"+str(a)+"'; $('tavg').onchange();")
        await asyncio.sleep(0.2)
    async def accum_px():
        v = await ev("frameData().data[(300*800+400)*4]")
        if isinstance(v,str): print('   accum_px raw:', v[:200])
        return v
    def near(a,b,tol=1): return abs(a-b)<=tol

    # 合成100で安定 → avg=2開始 = 現在フレームのクリーンコピー
    ok('合成100安定', await wait_vid(100))
    await set_avg(2)
    v = await accum_px()
    ok('開始=クリーンコピー(100)', near(v,100), v)

    # 250へ → 1render = 100+(250-100)/2 = 175
    await ev("window.__fill(250); 'd250'")
    ok('250フレーム到着', await wait_vid(250))
    await ev("renderGL(); 'r'")
    v = await accum_px()
    ok('x2 1render(175)', near(v,175), v)

    # 交互切替(0/250) x8 → 125±1収束
    vals=[]
    for i in range(8):
        target = 0 if i%2==0 else 250
        await ev("window.__fill("+str(target)+"); 'd"+str(target)+"'")
        await wait_vid(target)
        await ev("renderGL(); 'r'")
        vals.append(await accum_px())
    print('   交互切替系列:', vals)
    # α=1/2交互の2周期定常状態: low=83, high=167 (i偶=0目標→low)
    ok('交互切替収束(83/167±1)', near(vals[-1],167,1) and near(vals[-2],83,1), vals[-2:])

    # 非対称パターン: 上半分250/下半分0 → クリーンコピーで上下反転なし(向き検証)
    await ev("""(() => { const g=window.__g;
      g.fillStyle='rgb(250,250,250)'; g.fillRect(0,0,800,300);
      g.fillStyle='rgb(0,0,0)'; g.fillRect(0,300,800,300); })(); 'pattern'""")
    for _ in range(30):
        t0 = await ev("""(() => { const c=document.createElement('canvas'); c.width=800; c.height=600;
          const g=c.getContext('2d'); g.drawImage(video,0,0); return g.getImageData(400,100,1,1).data[0]; })()""")
        if t0==250: break
        await asyncio.sleep(0.1)
    await set_avg(4)  # 係数変更=累積リセット→パターンがクリーンコピーされる
    top = await ev("frameData().data[(100*800+400)*4]")
    bot = await ev("frameData().data[(500*800+400)*4]")
    ok('上下反転なし', top>200 and bot<50, (top,bot))

    # GL表示と解析値の一致(±3)
    glv = await ev("""(() => { const c=document.createElement('canvas'); c.width=fx.width; c.height=fx.height;
      const g=c.getContext('2d'); g.drawImage(fx,0,0);
      return g.getImageData(Math.round(fx.width/2),Math.round(fx.height/2),1,1).data[0]; })()""")
    an = await accum_px()
    ok('GL表示=解析値(±3)', abs(glv-an)<=3, (glv,an))

    # 永続化・UI状態
    st = await ev("""(() => { const t=JSON.parse(localStorage.getItem('tone')||'{}');
      return {avg:t.avg, sel:$('tavg').value, on:$('tonebtn').classList.contains('on')}; })()""")
    ok('avg=4永続化+UI', st.get('avg')==4 and st.get('sel')=='4' and st.get('on'), st)

    # 条件JSON(conditionsData)にavg
    raw = await ev("JSON.stringify(conditionsData().tone)")
    try:
        cd = json.loads(raw or '{}')
    except Exception:
        cd = None
    ok('条件JSONにavg', isinstance(cd,dict) and cd.get('avg')==4, raw)

    # avg=0で累積解除(即時パススルー)
    await set_avg(0)
    await ev("window.__fill(30); 'd30'")
    await wait_vid(30)
    await ev("renderGL(); 'r'")
    v = await accum_px()
    ok('avg解除で30即反映', near(v,30), v)

    # 後始末
    await ev("""(() => {
      localStorage.setItem('tone', JSON.stringify({gamma:1,contrast:1,sharp:0,noise:0,avg:0}));
      window.requestAnimationFrame = window.__raf0;
      (async()=>{await start();})();
    })(); 'restore'""")
    await asyncio.sleep(3)
    print('ALL PASS' if not results else 'FAILURES: '+str(results))
    await ws.close()
asyncio.run(main())
