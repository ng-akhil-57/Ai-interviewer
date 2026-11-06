/* ═══════════════════════════════════════════════════════
   upload.js — FIXED & OPTIMIZED VERSION
   Features:
   ✅ Proper error handling
   ✅ Safe DOM loading
   ✅ Better upload progress
   ✅ Handles backend failures safely
   ✅ Cleaner UI reset
   ✅ Prevents duplicate uploads
   ✅ Better PDF validation
   ✅ FIXED: session_id passed in URL to /interview
   ✅ FIXED: analysis stored under correct sessionStorage key
   ═══════════════════════════════════════════════════════ */

(function () {

  'use strict';

  // ─────────────────────────────────────────────────────
  // DOM ELEMENTS
  // ─────────────────────────────────────────────────────

  const dropZone      = document.getElementById('dropZone');
  const fileInput     = document.getElementById('fileInput');

  const uploadProg    = document.getElementById('uploadProgress');
  const progressFill  = document.getElementById('progressFill');
  const progressLbl   = document.getElementById('progressLabel');

  const analysisRes   = document.getElementById('analysisResult');

  const resultName    = document.getElementById('resultName');
  const resultDomain  = document.getElementById('resultDomain');
  const resultTags    = document.getElementById('resultTags');

  const startBtn      = document.getElementById('startBtn');

  // Prevent crashes if HTML elements missing
  if (
    !dropZone ||
    !fileInput ||
    !uploadProg ||
    !progressFill ||
    !progressLbl
  ) {
    console.error('[Upload] Required HTML elements missing');
    return;
  }

  // ─────────────────────────────────────────────────────
  // STATE
  // ─────────────────────────────────────────────────────

  let isUploading = false;
  let sessionId   = null;   // ← holds session_id after successful upload

  // ─────────────────────────────────────────────────────
  // DRAG & DROP
  // ─────────────────────────────────────────────────────

  dropZone.addEventListener('dragover', (e) => {

    e.preventDefault();

    dropZone.classList.add('drag-over');
  });

  dropZone.addEventListener('dragleave', () => {

    dropZone.classList.remove('drag-over');
  });

  dropZone.addEventListener('drop', (e) => {

    e.preventDefault();

    dropZone.classList.remove('drag-over');

    const file = e.dataTransfer.files[0];

    if (file) {
      validateAndUpload(file);
    }
  });

  // ─────────────────────────────────────────────────────
  // CLICK TO BROWSE
  // ─────────────────────────────────────────────────────

  dropZone.addEventListener('click', () => {

    if (!isUploading) {
      fileInput.click();
    }
  });

  fileInput.addEventListener('change', (e) => {

    const file = e.target.files[0];

    if (file) {
      validateAndUpload(file);
    }
  });

  // ─────────────────────────────────────────────────────
  // VALIDATE FILE
  // ─────────────────────────────────────────────────────

  function validateAndUpload(file) {

    if (isUploading) return;

    // PDF validation
    const isPDF =
      file.type === 'application/pdf' ||
      file.name.toLowerCase().endsWith('.pdf');

    if (!isPDF) {

      showError('Only PDF files are allowed.');

      return;
    }

    // Size validation
    const maxSize = 10 * 1024 * 1024;

    if (file.size > maxSize) {

      showError('File too large. Maximum size is 10 MB.');

      return;
    }

    uploadFile(file);
  }

  // ─────────────────────────────────────────────────────
  // UPLOAD FILE
  // ─────────────────────────────────────────────────────

  function uploadFile(file) {

    isUploading = true;

    // UI
    dropZone.style.display    = 'none';
    analysisRes.style.display = 'none';
    uploadProg.style.display  = 'block';

    setProgress(0, 'Uploading resume...');

    const formData = new FormData();

    formData.append('file', file);

    const xhr = new XMLHttpRequest();

    // ───────────────────────────────────────────────────
    // REAL UPLOAD PROGRESS
    // ───────────────────────────────────────────────────

    xhr.upload.addEventListener('progress', (e) => {

      if (!e.lengthComputable) return;

      const percent = Math.round((e.loaded / e.total) * 40);

      setProgress(percent, 'Uploading PDF...');
    });

    // ───────────────────────────────────────────────────
    // SUCCESS
    // ───────────────────────────────────────────────────

    xhr.addEventListener('load', () => {

      try {

        if (xhr.status !== 200) {

          let msg = 'Upload failed';

          try {
            const err = JSON.parse(xhr.responseText);
            msg = err.error || msg;
          } catch {}

          throw new Error(msg);
        }

        const data = JSON.parse(xhr.responseText);

        animateToComplete(data);

      } catch (err) {

        console.error('[Upload] Error:', err);

        showError(err.message);

        resetToUpload();
      }
    });

    // ───────────────────────────────────────────────────
    // NETWORK ERROR
    // ───────────────────────────────────────────────────

    xhr.addEventListener('error', () => {

      console.error('[Upload] Network error');

      showError('Network error. Make sure Flask server is running.');

      resetToUpload();
    });

    // ───────────────────────────────────────────────────
    // TIMEOUT
    // ───────────────────────────────────────────────────

    xhr.timeout = 120000;

    xhr.addEventListener('timeout', () => {

      showError('Request timeout. Try again.');

      resetToUpload();
    });

    // ───────────────────────────────────────────────────
    // SEND REQUEST
    // ───────────────────────────────────────────────────

    xhr.open('POST', '/upload-resume');

    xhr.send(formData);

    // ───────────────────────────────────────────────────
    // FAKE ANALYSIS PROGRESS
    // ───────────────────────────────────────────────────

    let fakeProgress = 40;

    const stages = [
      [55, 'Reading resume using AI...'],
      [70, 'Extracting skills & projects...'],
      [82, 'Identifying experience level...'],
      [92, 'Generating interview questions...'],
      [96, 'Finalizing analysis...']
    ];

    let stageIndex = 0;

    const ticker = setInterval(() => {

      if (fakeProgress >= 96) return;

      fakeProgress++;

      if (
        stageIndex < stages.length &&
        fakeProgress >= stages[stageIndex][0]
      ) {
        setProgress(stages[stageIndex][0], stages[stageIndex][1]);
        stageIndex++;
      }

    }, 120);

    xhr.addEventListener('loadend', () => {
      clearInterval(ticker);
    });
  }

  // ─────────────────────────────────────────────────────
  // COMPLETE ANIMATION
  // ─────────────────────────────────────────────────────

  function animateToComplete(data) {

    setProgress(100, 'Analysis Complete ✅');

    setTimeout(() => {

      uploadProg.style.display = 'none';

      renderResult(data);

      isUploading = false;

    }, 700);
  }

  // ─────────────────────────────────────────────────────
  // RENDER RESULT
  // ─────────────────────────────────────────────────────

  function renderResult(data) {

    const analysis = data.analysis || {};

    // ── FIX 1: store session_id in module variable ───────────────
    // (used in the redirect below — NOT read from sessionStorage)
    sessionId = data.session_id || '';

    // ── FIX 2: correct sessionStorage key ───────────────────────
    // Old key: 'interview_session'
    // interview.js reads: 'ai_interviewer_analysis'  ← must match
    try {
      sessionStorage.setItem(
        'ai_interviewer_analysis',
        JSON.stringify(analysis)
      );
    } catch (_) {
      console.warn('[Upload] sessionStorage unavailable.');
    }

    // Name
    if (resultName) {
      resultName.textContent = analysis.name || 'Candidate';
    }

    // Domain
    if (resultDomain) {
      resultDomain.textContent = analysis.domain || 'General';
    }

    // Skills
    if (resultTags) {

      resultTags.innerHTML = '';

      const skills = analysis.skills || [];

      if (skills.length === 0) {

        resultTags.innerHTML = '<div class="tag">No skills detected</div>';

      } else {

        skills.slice(0, 10).forEach((skill) => {

          const tag       = document.createElement('div');
          tag.className   = 'tag';
          tag.textContent = skill;

          resultTags.appendChild(tag);
        });
      }
    }

    // ── FIX 3: redirect with ?session_id= in the URL ─────────────
    // Old code: window.location.href = '/interview'
    // interview.js reads: new URLSearchParams(location.search).get('session_id')
    // Without the param it gets null → shows "no session" alert → redirects home
    if (startBtn) {

      startBtn.onclick = () => {

        if (!sessionId) {
          alert('Session not found. Please re-upload your resume.');
          return;
        }

        window.location.href =
          '/interview?session_id=' + encodeURIComponent(sessionId);
      };
    }

    analysisRes.style.display = 'block';
  }

  // ─────────────────────────────────────────────────────
  // SET PROGRESS
  // ─────────────────────────────────────────────────────

  function setProgress(percent, label) {

    progressFill.style.width = percent + '%';

    progressLbl.textContent  = label;
  }

  // ─────────────────────────────────────────────────────
  // RESET UI
  // ─────────────────────────────────────────────────────

  function resetToUpload() {

    isUploading = false;

    setTimeout(() => {

      uploadProg.style.display  = 'none';
      dropZone.style.display    = 'block';

      progressFill.style.width      = '0%';
      progressLbl.textContent       = 'Upload your resume';
      progressLbl.style.color       = '';
      progressFill.style.background = '';

      fileInput.value = '';

    }, 2200);
  }

  // ─────────────────────────────────────────────────────
  // ERROR UI
  // ─────────────────────────────────────────────────────

  function showError(message) {

    console.error('[Upload]', message);

    progressLbl.textContent       = '⚠️ ' + message;
    progressLbl.style.color       = '#f87171';
    progressFill.style.background = 'linear-gradient(90deg,#ef4444,#b91c1c)';
  }

})();