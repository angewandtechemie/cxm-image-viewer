# CxM: file mode + Otsu/Watershed/circularity/snapshot on loaded image
import json, socket, time, sys, pathlib

def ws_connect(url):
    import base64, os, struct
    from urllib.parse import urlparse
    u = urlparse(url); key = base64.b64encode(os.urandom(16)).decode()
    s = socket.create_connection((u.hostname, u.port), timeout=5); s.settimeout(30)
    hs = (f"GET {u.path or '/'} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\n"
          f"Origin: http://{u.hostname}:{u.port}\r\n"
          f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
          "Sec-WebSocket-Version: 13\r\n\r\n")
    s.sendall(hs.encode())
    buf = b""
    while b"\r\n\r\n" not in buf: buf += s.recv(4096)
    class WS:
        def __init__(self, sock, rb): self.s = sock; self.buf = rb
        def send(self, data):
            b = data.encode(); mask = os.urandom(4)
            pl = (128 | len(b) if len(b) < 126 else
                  (126, struct.pack('>H', len(b))) if len(b) < 65536 else
                  (126 + 2, struct.pack('>Q', len(b))))
            if isinstance(pl, tuple):
                hd = bytes([2, pl[0]]) + pl[1]
            else:
                hd = bytes([2, pl])
            self.s.sendall(hd + mask + bytes(x ^ mask[i % 4] for i, x in enumerate(b)))
        def recv(self):
            def rd(n):
                nonlocal self
                while len(self.buf) < n:
                    c = self.s.recv(65536)
                    if not c: raise OSError('closed')
                    self.buf += c
                out, self.buf = self.buf[:n], self.buf[n:]
                return out
            b0, b1 = rd(2); ln = b1 & 0x7f
            if ln == 126: ln = struct.unpack('>H', rd(2))[0]
            elif ln == 127: ln = struct.unpack('>Q', rd(8))[0]
            return rd(ln).decode('utf-8', 'replace')
    return WS(s, buf.split(b"\r\n\r\n", 1)[1])

class CDP:
    def __init__(self, ws): self.ws = ws; self.id = 0
    def cmd(self, method, **params):
        self.id += 1; i = self.id
        self.ws.send(json.dumps({'id': i, 'method': method, 'params': params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get('id') == i:
                if 'error' in m: raise RuntimeError(f"{method}: {m['error']}")
                return m.get('result', {})
    def ev(self, expr):
        r = self.cmd('Runtime.evaluate', expression=expr,
                     returnByValue=True, awaitPromise=True)
        if r.get('exceptionDetails'):
            raise RuntimeError('JS-ERR: ' + json.dumps(r['exceptionDetails'])[:400])
        return r.get('result', {}).get('value')

def urllib_open(u):
    import urllib.request
    with urllib.request.urlopen(u, timeout=5) as r: return r.read().decode()
ver = json.loads(urllib_open("http://127.0.0.1:9222/json/version"))
bws = CDP(ws_connect(ver['webSocketDebuggerUrl']))
tgt = bws.cmd('Target.createTarget', url='about:blank')
tid = tgt['targetId']
sess = bws.cmd('Target.attachToTarget', targetId=tid, flatten=True)['sessionId']
class Sess:
    def __init__(self, bws, sid): self.b = bws; self.sid = sid
    def cmd(self, method, **params):
        self.b.id += 1; i = self.b.id
        msg = {'id': i, 'method': method, 'params': params, 'sessionId': self.sid}
        self.b.ws.send(json.dumps(msg))
        while True:
            m = json.loads(self.b.ws.recv())
            if m.get('id') == i:
                if 'error' in m: raise RuntimeError(f"{method}: {m['error']}")
                return m.get('result', {})
    def ev(self, expr):
        r = self.cmd('Runtime.evaluate', expression=expr,
                     returnByValue=True, awaitPromise=True)
        if r.get('exceptionDetails'):
            raise RuntimeError('JS-ERR: ' + json.dumps(r['exceptionDetails'])[:400])
        return r.get('result', {}).get('value')
c = Sess(bws, sess)
c.cmd('Runtime.enable'); c.cmd('Page.enable'); c.cmd('DOM.enable')
c.cmd('Page.bringToFront')
c.cmd('Page.navigate', url='http://127.0.0.1:8642/app/index.html?v=filemode1')
time.sleep(7)
ok = c.ev("!!(document.querySelector('#modeLive')&&document.querySelector('#modeFile'))")
print('tabs exist:', ok)
r = None
for _ in range(24):
    time.sleep(3)
    r = c.ev("({vw:video.videoWidth, mode:mediaMode})")
    if r and r.get('vw'): break
print('live first:', r)

# build synthetic 1920x1080 file: gradient bg + 5 white circles (2 touching)
c.ev("""
(() => {
  const cv = document.createElement('canvas'); cv.width=1920; cv.height=1080;
  const g = cv.getContext('2d');
  const gr = g.createLinearGradient(0,0,1920,1080);
  gr.addColorStop(0,'#404040'); gr.addColorStop(1,'#5a5a5a');
  g.fillStyle = gr; g.fillRect(0,0,1920,1080);
  g.fillStyle = '#ffffff';
  for (const [x,y,r] of [[300,300,90],[800,300,90],[880,330,90],[1400,700,110],[500,800,60]]) {
    g.beginPath(); g.arc(x,y,r,0,7); g.fill();
  }
  cv.toBlob(b => {
    window.__synthFile = new File([b], 'synth.png', {type:'image/png'});
  });
  return true;
})()
""")
time.sleep(1)
c.ev("""
(() => {
  const dt = new DataTransfer(); dt.items.add(window.__synthFile);
  const inp = document.querySelector('#fileopen');
  inp.files = dt.files;
  inp.dispatchEvent(new Event('change', {bubbles:true}));
  return true;
})()
""")
time.sleep(2.5)
print('after load:', c.ev("({mode:mediaMode, iw:fi.naturalWidth, ih:fi.naturalHeight, vdisp:getComputedStyle(video).display, fdisp:getComputedStyle(fi).display, status:status.textContent})"))

# full-image ROI, binarize: touching circles => expect 4 comps before WS
c.ev("mode='area'; areas=[{pts:[{x:5,y:5},{x:1915,y:5},{x:1915,y:1075},{x:5,y:1075}],key:curKey()}]; livePts=[];")
c.ev("thr=140; polarity='light'; minArea=200; bgRad=0; wtrOn=false; cirMin=0; areaStats();")
time.sleep(0.5)
print('pre-WS comps (expect 4):', c.ev("({n:areaComps.length, thr:thr})"))

# Otsu auto threshold
c.ev("document.querySelector('#autothr').click();")
time.sleep(0.3)
print('otsu thr (expect ~130-200):', c.ev("({thr:thr, hasHist:!!areaStats.lastHist})"))

# Watershed split -> 5
c.ev("wtrOn=true; document.querySelector('#wtr').checked=true; areaStats();")
time.sleep(1.0)
print('WS comps (expect 5):', c.ev("({n:areaComps.length})"))

# circularity filter -> should drop real circles at strict 99%
c.ev("cirMin=99; areaStats();")
time.sleep(0.5)
print('strict circ (expect <5):', c.ev("({n:areaComps.length, rej:document.querySelector('#areaStats').textContent.includes('除外')})"))
c.ev("cirMin=0; wtrOn=false; document.querySelector('#wtr').checked=false; areaStats();")

# background correction on gradient must keep count stable
c.ev("bgRad=40; document.querySelector('#bgrad').value=40; areaStats();")
time.sleep(1.2)
print('bgcorr comps:', c.ev("({n:areaComps.length})"))

# line analysis on the file image
c.ev("""
lineSeg={a:{x:200,y:300},b:{x:400,y:300},key:curKey()};
sampleLine();
'ok';
""")
print('line sample ok (no throw):', True)

# snapshot from file: plain vs baked must differ
c.cmd('Runtime.evaluate', expression="""
(() => {
  window.__cap=[]; const _o=HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click=function(){
    const p=this.download; let d=0;
    const _b=HTMLAnchorElement.prototype;
    const r=new FileReader();
    this.href && fetch(this.href).then(x=>x.blob()).then(b=>{
      const f=new FileReader();
      f.onload=()=>window.__cap.push({p,size:b.size,head:f.result});
      f.readAsDataURL(b);
    });
  };
  return true;
})()
""")
c.ev("document.querySelector('#shot').click();")
time.sleep(0.8)
c.ev("document.querySelector('#shot2').click();")
time.sleep(1.2)
caps = c.ev("window.__cap.map(o=>({p:o.p,size:o.size,head:o.head.slice(0,30)}))")
print('file-mode captures:', caps)
same = c.ev("""(() => {
  if (window.__cap.length<2) return 'caps<2';
  return window.__cap[0].head===window.__cap[1].head;
})()""")
print('plain==baked (expect False):', same)

# back to live
c.ev("document.querySelector('#modeLive').click();")
time.sleep(6)
print('back live:', c.ev("({mode:mediaMode, vw:video.videoWidth, vdisp:getComputedStyle(video).display})"))

# header + area panel screenshot for visual check
b64 = c.cmd('Page.captureScreenshot', format='jpeg', quality=72)['data']
out = pathlib.Path(r"W:/hermes/cache/scratch/filemode_hdr.jpg")
out.write_bytes(__import__('base64').b64decode(b64))
print('shot:', str(out))
hdr = c.ev("""(() => {
  const fit = document.documentElement.scrollHeight <= innerHeight + 2;
  const btns = [...document.querySelectorAll('#controls button,#controls select,#controls input[type=number]')];
  const over = btns.filter(x => x.scrollWidth > x.clientWidth + 1)
    .map(x => (x.textContent || x.id).trim().slice(0, 16));
  const s1 = document.querySelector('#shot').getBoundingClientRect();
  const s2 = document.querySelector('#shot2').getBoundingClientRect();
  return {fit, page:[innerWidth,innerHeight], over,
    shot:[Math.round(s1.width),Math.round(s1.height)],
    shot2:[Math.round(s2.width),Math.round(s2.height)],
    hdrRows:[document.querySelector('header').getBoundingClientRect().height,
             document.querySelector('#controls').getBoundingClientRect().height]};
})()""")
print('layout:', hdr)
bws.cmd('Target.closeTarget', targetId=tid)
print('test tab closed')
