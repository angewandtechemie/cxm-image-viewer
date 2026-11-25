# CxM Image Viewer

Microscope camera viewer & image analyzer — a single HTML file that runs in any modern browser.
顕微鏡USBカメラ(H1612等UVC)の表示・撮影・解析アプリ。単一HTML、インストール不要。

**Live app / 起動:** https://angewandtechemie.github.io/cxm-image-viewer/

## Layout

| Path | Description |
|---|---|
| `index.html` | Landing page (EN/JP entry) |
| `app/index.html` | App, Japanese (Version 1.11) |
| `app/index-en.html` | App, English (Version 1.11) |
| `app/cxm-mobile.html` | Phone app, Japanese (segment/angle/difference/time-lapse only) |
| `app/cxm-mobile-en.html` | Phone app, English (built by `tools/build_en_mobile.py`) |
| `tools/build_en_mobile.py` | String-translation build for the phone app |
| `manual/index.html` | User manual, Japanese |
| `manual/index-en.html` | User manual, English |
| `downloads/` | Offline ZIP bundle (`start_viewer.bat` + `serve.ps1`, no Python needed) |

## Features

- Live camera view (UVC: H1612 digital microscope, webcams) up to 4K, with per-camera supported-resolution probing
- Image math: R/G/B, Human Eye (R+G), Red/Green Enhance, ExG, Red/Green/Blue Index, Pseudo Gray
- Corrections: gamma, contrast, sharpen, median/Gaussian denoise, temporal frame averaging, gray-world auto WB, one-click auto-correct
- Capture: PNG stills, video (WebM, optional analysis overlay baked in), time-lapse, interval capture with progress markers
- Analysis (shared mm calibration): 2-point distance, angle, shape (circle/rectangle/square/quad), point set, line profile with edge detection, area (target color), particles (threshold/hue segmentation, watershed, circularity filter, size histogram, CSV)
- Image comparison (reference vs live, block diff heatmap)
- Outputs: annotated PNG + TXT (Shift+S), HTML report, conditions JSON, CSV
- Keyboard shortcuts (S/V/L/K/P/N/G/C/M/R, Shift+S)

## Offline use

Unzip `downloads/CxM_ImageViewer_v111_full_20261125.zip`, double-click `start_viewer.bat`.
Served on `http://127.0.0.1:8642/` via Windows built-in PowerShell (no Python required).
Opening `index.html` directly (file://) works for saved-image analysis only — browsers disable the camera API on file://.

## Notes

- The English app is generated from the Japanese source by a string-translation build; keep both files in sync when updating.
- Camera features require a secure context: `https://` (GitHub Pages) or `http://127.0.0.1`.

Version 1.11 (2026-11-24) — see the manual's version history.
