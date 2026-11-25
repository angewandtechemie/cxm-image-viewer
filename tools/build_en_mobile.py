# -*- coding: utf-8 -*-
# Build app/cxm-mobile-en.html from app/cxm-mobile.html (string-translation build).
# Keep this map in sync when editing the Japanese source. Run: py tools/build_en_mobile.py
import re, sys, pathlib

root = pathlib.Path(__file__).resolve().parent.parent
src = (root / 'app' / 'cxm-mobile.html').read_text(encoding='utf-8')

# ordered: longer/compound strings first
MAP = [
    # HTML comments & labels
    ('<!-- 測定系(線分・角度) -->', '<!-- measurement (segment/angle) -->'),
    ('<!-- 差異検出 -->', '<!-- difference detection -->'),
    ('<!-- タイムラプス -->', '<!-- time-lapse -->'),
    ('"カメラ切替"', '"Switch camera"'),
    ('"写真を読み込み"', '"Load photo"'),
    ('"既知の長さ2点タップ→実寸入力"', '"Tap 2 points of known length, enter real size"'),
    ('>起動中…<', '>Starting…<'),
    ('>📏 線分<', '>📏 Segment<'),
    ('>∠ 角度<', '>∠ Angle<'),
    ('>🔀 差異<', '>🔀 Diff<'),
    ('>⏱ タイムラプス<', '>⏱ Time-lapse<'),
    ('>現在を固定<', '>Freeze current<'),
    ('>基準を写真から<', '>Ref from photo<'),
    ('>画像保存<', '>Save image<'),
    ('>全消去<', '>Clear all<'),
    ('>戻す<', '>Undo<'),
    ('>終了<', '>End<'),
    ('>合計<', '>Total<'),
    ('>閾値<', '>Threshold<'),
    ('>較正<', '>Calibrate<'),
    ('>開始<', '>Start<'),
    ('>分を', '> min into'),
    ('>秒に短縮', '> seconds'),
    # JS comments
    ('// ---- タイムラプス ----', '// ---- time-lapse ----'),
    ('// ---- モード切替 ----', '// ---- mode switch ----'),
    ('// ---- 入力(pointerdown: マウス/タッチ共通) ----', '// ---- input (pointerdown: mouse/touch) ----'),
    ('// ---- 単位・フォーマット(デスクトップ版と同一) ----', '// ---- units & format (same as desktop) ----'),
    ('// ---- 差異検出(上下分割: 上=Reference / 下=Sample) ----', '// ---- difference detection (top=Reference / bottom=Sample) ----'),
    ('// ---- 座標変換(映像はcontain表示) ----', '// ---- coordinate mapping (contain fit) ----'),
    ('// ---- オーバーレイ ----', '// ---- overlay ----'),
    ('// ---- 結果テキスト ----', '// ---- results text ----'),
    ('// ---- 画像保存(結果焼き込み) ----', '// ---- save image (results baked in) ----'),
    ('// ---- カメラ・ファイル ----', '// ---- camera & files ----'),
    ('// オーバーレイ文字サイズ(スマホ向け)', '// overlay font size (mobile)'),
    ('// 線分の1点目 / 角度の途中点列はangPts', '// pending segment point / in-progress angle points'),
    ('// 現解像度に伸長', '// stretch to current resolution'),
    ('// 線分\n', '// segments\n'),
    ('// 角度\n', '// angles\n'),
    ('// 較正入力中', '// calibration input in progress'),
    ('// スケールバー(較正時のみ)', '// scale bar (only when calibrated)'),
    ('// 差分ブロック: 同一サイズに縮小して比較', '// diff blocks: compare at equal size'),
    ('/* ユーザー取消・非ジェスチャ→ダウンロードへ */', '/* cancel or no gesture -> download */'),
    # JS strings (toasts, prompts, status)
    ("'タイムラプスにはライブ映像が必要です'", "'Time-lapse needs a live camera'"),
    ("'既知の長さの始点・終点の順に2回タップしてください'", "'Tap start then end of a known length (2 taps)'"),
    ("'基準を固定しました(上=Reference / 下=Sample)'", "'Reference frozen (top=Reference / bottom=Sample)'"),
    ("'基準画像を設定しました'", "'Reference image set'"),
    ("'較正を取り消しました'", "'Calibration cancelled'"),
    ("'較正完了: ", "'Calibrated: "),
    ('`較正完了: ', '`Calibrated: '),
    ("'共有しました'", "'Shared'"),
    ("'保存しました: '", "'Saved: '"),
    ("'合成に失敗: '", "'Compose failed: '"),
    ("'カメラ起動失敗: '", "'Camera start failed: '"),
    ("'較正: 終点タップ'", "'cal: tap end point'"),
    ("'タイムラプス'", "'time-lapse'"),
    ("'線分測定'", "'segment'"),
    ("'角度測定'", "'angle'"),
    ("'差異検出'", "'diff'"),
    ("'停止'", "'Stop'"),
    ("'開始'", "'Start'"),
    ("'未'", "'none'"),
    # template literals
    ('` 測定=${segs.length}+${angles.length}`', '` meas=${segs.length}+${angles.length}`'),
    ('較正=${mpp', 'cal=${mpp'),
    (' モード=${{seg:', ' mode=${{seg:'),
    ('`→ ${Math.round(p.x)}倍速・撮影間隔${p.T.toFixed(1)}秒・${p.frames}枠・30fps`',
     '`→ ${Math.round(p.x)}x speed, interval ${p.T.toFixed(1)}s, ${p.frames} frames, 30fps`'),
    ('`タイムラプス開始: ${p.frames}枠・間隔${p.T.toFixed(1)}秒`',
     '`Time-lapse started: ${p.frames} frames, interval ${p.T.toFixed(1)}s`'),
    ('`合成中… ${talFrames.length}枠`', '`Composing… ${talFrames.length} frames`'),
    ('`基準長の実際(mm)を入力\\n画面長: ${Math.round(d)}px`',
     '`Enter real length (mm)\\nscreen: ${Math.round(d)}px`'),
    ('`角度${i + 1}: ', '`Angle${i + 1}: '),
    ('`線分${i + 1}: ', '`Segment${i + 1}: '),
]

out = src
for a, b in MAP:
    out = out.replace(a, b)

# verify: no Japanese left
left = re.findall(r"[^\x00-\x7f]+", out)
left = [s for s in left if re.search(r'[\u3000-\u30ff\u4e00-\u9fff]', s)]
if left:
    print('UNTRANSLATED:', left[:20]); sys.exit(1)

out = out.replace('<title>CxM Mobile</title>', '<title>CxM Mobile (EN)</title>')
(root / 'app' / 'cxm-mobile-en.html').write_text(out, encoding='utf-8')
print('WROTE app/cxm-mobile-en.html', len(out), 'chars')
