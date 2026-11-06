/* ═══════════════════════════════════════════════════════
   upload.js — Resume upload & analysis for AI Interviewer
   Place at: static/js/upload.js
   ═══════════════════════════════════════════════════════ */

(function () {
  'use strict';

  const dropZone    = document.getElementById('dropZone');
  const fileInput   = document.getElementById('fileInput');
  const uploadProg  = document.getElementById('uploadProgress');
  const progressFill= document.getElementById('progressFill');
  const progressLbl = document.getElementById('progressLabel');
  const analysisRes = document.getElementById('analysisResult');
  const resultName  = document.getElementById('resultName');
  const resultDomain= document.getElementById('resultDomain');
  const resultTags  = document.getElementById('resultTags');
  const startBtn    = document.getElementById('startBtn');

  if (!dropZone || !fileInput) {
    console.error('[upload.js] Required elements not found.');
    return;
  }

  // ── Replace emoji icon with inline SVG (always renders) ──
  const iconEl = dropZone.querySelector('.upload-icon');
  if (iconEl) {
    iconEl.innerHTML = `
      <svg width="56" height="56" viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="8" y="4" width="32" height="40" rx="3" fill="#13132a" stroke="#6c63ff" stroke-width="1.5"/>
        <path d="M30 4 L40 14 L30 14 Z" fill="#0d0d1a" stroke="#6c63ff" stroke-width="1.5" stroke-linejoin="round"/>
        <line x1="14" y1="22" x2="34" y2="22" stroke="#6c63ff" stroke-width="1.5" stroke-linecap="round"/>
        <line x1="14" y1="28" x2="34" y2="28" stroke="#6c63ff" stroke-width="1.5" stroke-linecap="round"/>
        <line x1="14" y1="34" x2="26" y2="34" stroke="#6c63ff" stroke-width="1.5" stroke-linecap="round"/>
        <circle cx="40" cy="42" r="12" fill="#6c63ff"/>
        <path d="M40 48 L40 36" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
        <path d="M35 41 L40 36 L45 41" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`;
  }

  // ── Prevent browser default on drag events ────────────
  ['dragenter','dragover','dragleave','drop'].forEach(evt => {
    document.addEventListener(evt, e => e.preventDefault(), false);
  });

  // ── Drag & Drop ───────────────────────────────────────
  dropZone.addEventListener('dragenter', e => {
    e.preventDefault(); e.stopPropagation();
    dropZone.classList.add('drag-over');
  });

  dropZone.addEventListener('dragover', e => {
    e.preventDefault(); e.stopPropagation();
    dropZone.classList.add('drag-over');
  });

  dropZone.addEventListener('dragleave', e => {
    e.preventDefault(); e.stopPropagation();
    if (!dropZone.contains(e.relatedTarget))
      dropZone.classList.remove('drag-over');
  });

  dropZone.addEventListener('drop', e => {
    e.preventDefault(); e.stopPropagation();
    dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) validateAndUpload(file);
  });

  // ── Click to browse ───────────────────────────────────
  dropZone.addEventListener('click', e => {
    if (e.target === fileInput) return;
    fileInput.click();
  });

  // Stop the "browse to upload" span from double-triggering
  const uploadLink = dropZone.querySelector('.upload-link');
  if (uploadLink) {
    uploadLink.addEventListener('click', e => {
      e.stopPropagation();
      fileInput.click();
    });
  }

  fileInput.addEventListener('change', e => {
    const file = e.target.files[0];
    if (file) validateAndUpload(file);
    fileInput.value = '';
  });

  // ── Validate ──────────────────────────────────────────
  function validateAndUpload(file) {
    const isPDF = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
    if (!isPDF)                         { showError('Only PDF files are accepted.'); return; }
    if (file.size > 10 * 1024 * 1024)  { showError('File too large. Max 10 MB.');  return; }
    uploadFile(file);
  }

  // ── Upload ────────────────────────────────────────────
  let ticker = null;

  function uploadFile(file) {
    dropZone.style.display   = 'none';
    uploadProg.style.display = 'block';
    setProgress(0, 'Uploading…');

    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener('progress', e => {
      if (e.lengthComputable)
        setProgress(Math.round((e.loaded / e.total) * 40), 'Uploading…');
    });

    xhr.addEventListener('load', () => {
      clearInterval(ticker);
      if (xhr.status === 200) {
        try {
          const data = JSON.parse(xhr.responseText);
          setProgress(100, 'Analysis complete! ✅');
          setTimeout(() => showResult(data), 700);
        } catch {
          showError('Bad server response.'); resetUI();
        }
      } else {
        let msg = 'Upload failed.';
        try { msg = JSON.parse(xhr.responseText).error || msg; } catch {}
        showError(msg); resetUI();
      }
    });

    xhr.addEventListener('error', () => {
      clearInterval(ticker);
      showError('Network error — is the server running?');
      resetUI();
    });

    xhr.open('POST', '/upload-resume');
    xhr.send(formData);

    // Animate 40 → 95% during backend processing
    let pct = 40;
    const stages = [
      { at: 55, msg: 'Reading resume with BERT…' },
      { at: 70, msg: 'Extracting skills & experience…' },
      { at: 82, msg: 'Identifying your domain…' },
      { at: 93, msg: 'Generating interview questions…' },
    ];
    let si = 0;
    ticker = setInterval(() => {
      pct = Math.min(pct + 1, 95);
      if (si < stages.length && pct >= stages[si].at) {
        setProgress(pct, stages[si].msg); si++;
      } else {
        setProgress(pct, progressLbl.textContent);
      }
    }, 130);
  }

  // ── Show result ───────────────────────────────────────
  function showResult(data) {
    uploadProg.style.display = 'none';
    const analysis = data.analysis || {};

    sessionStorage.setItem('session_id', data.session_id || '');
    sessionStorage.setItem('analysis',   JSON.stringify(analysis));

    resultName.textContent   = analysis.name   || 'Candidate';
    resultDomain.textContent = analysis.domain || 'General';

    resultTags.innerHTML = '';
    (Array.isArray(analysis.skills) ? analysis.skills : []).slice(0, 8).forEach(skill => {
      const tag = document.createElement('span');
      tag.className = 'tag'; tag.textContent = skill;
      resultTags.appendChild(tag);
    });

    startBtn.onclick = () => { window.location.href = '/interview'; };
    analysisRes.style.display = 'block';
  }

  // ── Helpers ───────────────────────────────────────────
  function setProgress(pct, label) {
    progressFill.style.width = Math.min(pct, 100) + '%';
    if (label !== undefined) progressLbl.textContent = label;
  }

  function showError(msg) {
    setProgress(100, '⚠️ ' + msg);
    progressFill.style.background = '#7f1d1d';
    progressLbl.style.color       = '#f87171';
  }

  function resetUI() {
    setTimeout(() => {
      uploadProg.style.display      = 'none';
      dropZone.style.display        = 'block';
      progressFill.style.background = '';
      progressLbl.style.color       = '';
      setProgress(0, 'Uploading…');
    }, 3000);
  }

})();
