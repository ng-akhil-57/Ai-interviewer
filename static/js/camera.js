/**
 * camera.js  — v2 (Oval Frame + Status Glow Edition) FIXED
 * =========================================================
 * Fix: init() now always looks up DOM elements by ID itself.
 * Never relies on caller passing elements — this eliminates
 * the "Video or canvas element not found" race condition.
 */

const CameraModule = (() => {

  const CONFIG = {
    captureIntervalMs: 1800,
    jpegQuality:       0.75,
    videoWidth:        320,
    videoHeight:       240,
  };

  const OVAL = {
    cxRatio: 0.50,
    cyRatio: 0.46,
    rxRatio: 0.38,
    ryRatio: 0.46,
  };

  const STATUS_COLORS = {
    ok:             '#4ade80',
    looking_away:   '#fbbf24',
    no_face:        '#f87171',
    multiple_faces: '#f87171',
    error:          '#94a3b8',
    init:           '#6c63ff',
  };

  let stream          = null;
  let videoEl         = null;
  let canvasEl        = null;
  let ctx             = null;
  let overlayImgEl    = null;
  let captureTimer    = null;
  let onCheatCallback = null;
  let currentStatus   = 'init';
  let animFrame       = null;
  let glowPhase       = 0;

  // ─────────────────────────────────────────────
  // INIT — always looks up elements by ID itself
  // ─────────────────────────────────────────────

  async function init(options) {

    // Always look up by ID — ignore any passed options
    // This avoids race conditions where caller passes a null element
    videoEl      = document.getElementById('webcam-video');
    canvasEl     = document.getElementById('webcam-canvas');
    overlayImgEl = document.getElementById('webcam-overlay');

    // Hard check
    if (!videoEl) {
      console.error('[Camera] #webcam-video not found in DOM');
      _setBadge('❌ Camera element missing', '#f87171');
      return false;
    }

    if (!canvasEl) {
      console.error('[Camera] #webcam-canvas not found in DOM');
      _setBadge('❌ Canvas element missing', '#f87171');
      return false;
    }

    ctx = canvasEl.getContext('2d');

    try {

      // Request camera permission
      stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width:      { ideal: CONFIG.videoWidth },
          height:     { ideal: CONFIG.videoHeight },
          facingMode: 'user',
        },
        audio: false,
      });

      // Attach stream to hidden video element
      videoEl.srcObject = stream;

      // Wait for video to be ready to play
      await new Promise((resolve, reject) => {
        videoEl.onloadedmetadata = () => {
          videoEl.play().then(resolve).catch(reject);
        };
        videoEl.onerror = reject;
        // Timeout after 8 seconds
        setTimeout(() => reject(new Error('Video load timeout')), 8000);
      });

      // Set canvas dimensions to match video
      canvasEl.width  = videoEl.videoWidth  || CONFIG.videoWidth;
      canvasEl.height = videoEl.videoHeight || CONFIG.videoHeight;

      console.log('[Camera] Video ready:', canvasEl.width, 'x', canvasEl.height);

      document.addEventListener('visibilitychange', _onVisibilityChange);

      _drawLoop();

      captureTimer = setInterval(_captureAndAnalyse, CONFIG.captureIntervalMs);

      console.log('[Camera] Initialised ✅');
      _setBadge('🟡 Detecting face…', '#6c63ff');
      return true;

    } catch (err) {
      console.error('[Camera] Failed:', err.message);
      _setStatus('error');
      _setBadge('❌ ' + err.message, '#f87171');
      return false;
    }
  }

  // ─────────────────────────────────────────────
  // TAB SWITCH
  // ─────────────────────────────────────────────

  function _onVisibilityChange() {
    if (document.hidden) {
      _dispatchCheat({
        type:     'tab_switch',
        message:  'Tab switched away during interview',
        severity: 'high',
      });
    }
  }

  // ─────────────────────────────────────────────
  // DRAW LOOP
  // ─────────────────────────────────────────────

  function _drawLoop() {
    if (!ctx || !videoEl) return;

    // Only draw if video has data
    if (videoEl.readyState >= 2) {
      glowPhase = (glowPhase + 0.04) % (Math.PI * 2);

      const w  = canvasEl.width;
      const h  = canvasEl.height;
      const cx = w * OVAL.cxRatio;
      const cy = h * OVAL.cyRatio;
      const rx = w * OVAL.rxRatio;
      const ry = h * OVAL.ryRatio;

      ctx.drawImage(videoEl, 0, 0, w, h);
      _drawVignetteOutsideOval(cx, cy, rx, ry, w, h);

      const color = STATUS_COLORS[currentStatus] || STATUS_COLORS.init;
      const pulse = 0.55 + 0.45 * Math.sin(glowPhase);
      _drawOvalGlowRings(cx, cy, rx, ry, color, pulse);
      _drawOvalBorder(cx, cy, rx, ry, color);
      _drawStatusDot(cx, cy + ry + 14, color);
    }

    animFrame = requestAnimationFrame(_drawLoop);
  }

  function _drawVignetteOutsideOval(cx, cy, rx, ry, w, h) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, w, h);
    ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(6,6,15,0.55)';
    ctx.fill('evenodd');
    ctx.restore();
  }

  function _drawOvalGlowRings(cx, cy, rx, ry, color, pulse) {
    const rings = [
      { extra: 14, alpha: 0.10 * pulse },
      { extra:  8, alpha: 0.18 * pulse },
      { extra:  3, alpha: 0.28 * pulse },
    ];
    for (const { extra, alpha } of rings) {
      ctx.save();
      ctx.beginPath();
      ctx.ellipse(cx, cy, rx + extra, ry + extra, 0, 0, Math.PI * 2);
      ctx.strokeStyle = _hexToRgba(color, alpha);
      ctx.lineWidth   = 5;
      ctx.stroke();
      ctx.restore();
    }
  }

  function _drawOvalBorder(cx, cy, rx, ry, color) {
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
    ctx.strokeStyle = color;
    ctx.lineWidth   = 2.5;
    ctx.stroke();
    ctx.restore();
  }

  function _drawStatusDot(x, y, color) {
    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, 7, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.beginPath();
    ctx.arc(x, y, 7, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(255,255,255,0.6)';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.restore();
  }

  // ─────────────────────────────────────────────
  // FRAME CAPTURE → BACKEND
  // ─────────────────────────────────────────────

  async function _captureAndAnalyse() {
    if (!videoEl || videoEl.readyState < 2) return;

    const tempCanvas        = document.createElement('canvas');
    tempCanvas.width        = CONFIG.videoWidth;
    tempCanvas.height       = CONFIG.videoHeight;
    const tempCtx           = tempCanvas.getContext('2d');
    tempCtx.drawImage(videoEl, 0, 0, CONFIG.videoWidth, CONFIG.videoHeight);
    const b64Frame          = tempCanvas.toDataURL('image/jpeg', CONFIG.jpegQuality);

    try {
      const resp = await fetch('/analyse-frame', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ frame: b64Frame }),
      });

      if (!resp.ok) return;

      const data = await resp.json();

      _setStatus(data.event?.type || 'ok');

      if (overlayImgEl && data.annotated_b64) {
        overlayImgEl.src              = data.annotated_b64;
        overlayImgEl.style.display    = 'block';
        overlayImgEl.style.opacity    = '0.45';
      }

      _updateStatusBadge(data.event);

      if (data.event && data.event.type !== 'ok') {
        _dispatchCheat(data.event);
      }

    } catch (err) {
      console.warn('[Camera] Frame analysis failed:', err.message);
    }
  }

  // ─────────────────────────────────────────────
  // STATUS
  // ─────────────────────────────────────────────

  function _setStatus(type) {
    currentStatus = type;
  }

  function _setBadge(text, color) {
    const badge = document.getElementById('camera-status-badge');
    if (!badge) return;
    badge.textContent = text;
    badge.style.color = color || '#4ade80';
  }

  function _updateStatusBadge(event) {
    if (!event) return;
    const color = STATUS_COLORS[event.type] || STATUS_COLORS.init;
    const icons = {
      ok:             '✅',
      looking_away:   '👀',
      no_face:        '⚠️',
      multiple_faces: '👥',
      tab_switch:     '🔄',
      error:          '❌',
    };
    _setBadge(`${icons[event.type] || '⚠️'} ${event.message}`, color);
  }

  function _dispatchCheat(event) {
    if (onCheatCallback) onCheatCallback(event);
  }

  // ─────────────────────────────────────────────
  // PUBLIC
  // ─────────────────────────────────────────────

  function onCheat(cb) { onCheatCallback = cb; }

  function captureFrame() {
    if (!videoEl || videoEl.readyState < 2) return null;
    const tmp = document.createElement('canvas');
    tmp.width  = CONFIG.videoWidth;
    tmp.height = CONFIG.videoHeight;
    tmp.getContext('2d').drawImage(videoEl, 0, 0);
    return tmp.toDataURL('image/jpeg', CONFIG.jpegQuality);
  }

  function stop() {
    if (captureTimer) { clearInterval(captureTimer); captureTimer = null; }
    if (animFrame)    { cancelAnimationFrame(animFrame); animFrame = null; }
    if (stream)       { stream.getTracks().forEach(t => t.stop()); stream = null; }
    document.removeEventListener('visibilitychange', _onVisibilityChange);
  }

  // ─────────────────────────────────────────────
  // UTIL
  // ─────────────────────────────────────────────

  function _hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }

  return { init, stop, onCheat, captureFrame };

})();