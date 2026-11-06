// ═══════════════════════════════════════════════════════════════
// interview.js  —  Full Interview Flow Controller
// ═══════════════════════════════════════════════════════════════

window.questions            = [];
window.currentQuestionIndex = 0;

const state = {
  sessionId : null,
  analysis  : {},
  answers   : [],
  startTime : Date.now(),
};


// ═══════════════════════════════════════════════════════════════
// BOOT
// ═══════════════════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", () => {

  const params    = new URLSearchParams(window.location.search);
  state.sessionId = params.get("session_id");

  // Restore analysis from sessionStorage
  try {
    const raw = sessionStorage.getItem("ai_interviewer_analysis");
    if (raw) state.analysis = JSON.parse(raw);
  } catch (_) {}

  // Populate title
  const titleEl = document.getElementById("interview-title");
  if (titleEl) {
    const name   = state.analysis.name   || "";
    const domain = state.analysis.domain || "";
    if (name)        titleEl.textContent = `${name}'s Interview`;
    else if (domain) titleEl.textContent = `${domain} Interview`;
  }

  // Guard: no session
  if (!state.sessionId) {
    alert("No interview session found. Please upload your resume first.");
    window.location.href = "/";
    return;
  }

  wireButtons();

  // NOTE: Camera and speech are initialised by window.load
  // in the inline script at the bottom of interview.html.
  // Do NOT init them here — it causes a race condition where
  // the video/canvas elements are not yet accessible.

  loadQuestions(state.sessionId);
});


// ═══════════════════════════════════════════════════════════════
// WIRE BUTTONS
// ═══════════════════════════════════════════════════════════════

function wireButtons() {

  const submitBtn = document.getElementById("submit-btn");
  if (submitBtn) submitBtn.addEventListener("click", handleSubmit);

  const skipBtn = document.getElementById("skip-btn");
  if (skipBtn) skipBtn.addEventListener("click", handleSkip);

  const nextBtn = document.getElementById("next-btn");
  if (nextBtn) nextBtn.addEventListener("click", handleNext);

  // Mic button wired here as backup — also wired in window.load
  const micBtn = document.getElementById("mic-btn");
  if (micBtn) {
    micBtn.addEventListener("click", () => {
      if (typeof SpeechModule !== "undefined") {
        SpeechModule.toggleListening();
      }
    });
  }
}


// ═══════════════════════════════════════════════════════════════
// LOAD QUESTIONS
// ═══════════════════════════════════════════════════════════════

async function loadQuestions(sessionId) {

  try {

    setQuestionText("Generating your personalised questions…");
    setSubmitEnabled(false);

    const response = await fetch("/get-questions", {
      method : "POST",
      headers: { "Content-Type": "application/json" },
      body   : JSON.stringify({ session_id: sessionId }),
    });

    if (!response.ok) throw new Error(`Server Error: ${response.status}`);

    const data = await response.json();

    if (!data.success) throw new Error(data.error || "Unknown error");
    if (!Array.isArray(data.questions) || data.questions.length === 0)
      throw new Error("No questions returned");

    window.questions            = data.questions;
    window.currentQuestionIndex = 0;

    showQuestion(0);
    setSubmitEnabled(true);

  } catch (err) {
    console.error("LOAD QUESTIONS ERROR:", err);
    setQuestionText("⚠ Failed to load questions: " + err.message);
    alert("Could not load interview questions.\n\n" + err.message);
  }
}


// ═══════════════════════════════════════════════════════════════
// SHOW QUESTION
// ═══════════════════════════════════════════════════════════════

function showQuestion(index) {

  if (!window.questions || window.questions.length === 0) return;
  if (index < 0 || index >= window.questions.length) return;

  const total = window.questions.length;

  setQuestionText(window.questions[index]);

  const counterEl = document.getElementById("q-counter");
  if (counterEl) counterEl.textContent = `Question ${index + 1} of ${total}`;

  const fillEl = document.getElementById("q-progress-fill");
  if (fillEl) fillEl.style.width = `${((index + 1) / total) * 100}%`;

  hideFeedback();
  clearAnswer();

  window.currentQuestionIndex = index;

  // Speak the question aloud
  if (typeof SpeechModule !== "undefined") {
    SpeechModule.speak(window.questions[index]);
  }
}


// ═══════════════════════════════════════════════════════════════
// HANDLE SUBMIT
// ═══════════════════════════════════════════════════════════════

async function handleSubmit() {

  const answerEl = document.getElementById("answer-text");
  const answer   = answerEl ? answerEl.value.trim() : "";

  if (!answer) {
    alert("Please provide an answer before submitting, or click Skip.");
    return;
  }

  // Stop listening if still active
  if (typeof SpeechModule !== "undefined" && SpeechModule.getIsListening()) {
    SpeechModule.stopListening();
  }

  const question = window.questions[window.currentQuestionIndex];

  // Collect NLP data before clearing transcript
  let nlpSnapshot = null;
  if (typeof SpeechModule !== "undefined") {
    nlpSnapshot = SpeechModule.getNLPSummary();
  }

  setSubmitEnabled(false);
  showFeedbackLoading();

  try {

    const result = await evaluateAnswer(
      question,
      answer,
      state.analysis.domain || "",
      state.analysis.skills || []
    );

    state.answers.push({
      question,
      answer,
      score     : result.score      || 0,
      feedback  : result.feedback   || "",
      dimensions: result.dimensions || {},
      nlp       : nlpSnapshot,
    });

    renderFeedback(result);

  } catch (err) {
    console.error("SUBMIT ERROR:", err);
    hideFeedback();
    alert("Evaluation failed: " + err.message);
    setSubmitEnabled(true);
  }
}


// ═══════════════════════════════════════════════════════════════
// HANDLE SKIP
// ═══════════════════════════════════════════════════════════════

function handleSkip() {

  const question = window.questions[window.currentQuestionIndex];

  state.answers.push({
    question,
    answer    : "(skipped)",
    score     : 0,
    feedback  : "Question skipped.",
    dimensions: {},
    nlp       : null,
  });

  advanceOrFinish();
}


// ═══════════════════════════════════════════════════════════════
// HANDLE NEXT
// ═══════════════════════════════════════════════════════════════

function handleNext() {
  advanceOrFinish();
}


// ═══════════════════════════════════════════════════════════════
// ADVANCE OR FINISH
// ═══════════════════════════════════════════════════════════════

function advanceOrFinish() {
  const next = window.currentQuestionIndex + 1;
  if (next < window.questions.length) {
    showQuestion(next);
    setSubmitEnabled(true);
  } else {
    finishInterview();
  }
}


// ═══════════════════════════════════════════════════════════════
// EVALUATE ANSWER
// ═══════════════════════════════════════════════════════════════

async function evaluateAnswer(question, answer, domain, skills) {

  const response = await fetch("/evaluate-answer", {
    method : "POST",
    headers: { "Content-Type": "application/json" },
    body   : JSON.stringify({ question, answer, domain, skills, session_id: state.sessionId }),
  });

  if (!response.ok) throw new Error(`Server Error: ${response.status}`);

  const data = await response.json();
  if (!data.success) throw new Error(data.error || "Evaluation failed");

  return data;
}


// ═══════════════════════════════════════════════════════════════
// RENDER FEEDBACK CARD
// ═══════════════════════════════════════════════════════════════

function renderFeedback(result) {

  const score      = Math.round(result.score || 0);
  const feedback   = result.feedback   || "No feedback available.";
  const dimensions = result.dimensions || {};

  const circleEl = document.getElementById("score-circle");
  const numEl    = document.getElementById("score-num");
  if (numEl) numEl.textContent = score;
  if (circleEl) {
    const color = score >= 75 ? "#4ade80" : score >= 50 ? "#fbbf24" : "#f87171";
    circleEl.style.color      = color;
    circleEl.style.background = color + "22";
  }

  const feedbackEl = document.getElementById("score-feedback");
  if (feedbackEl) feedbackEl.textContent = feedback;

  const dimGrid = document.getElementById("dim-grid");
  if (dimGrid) {
    dimGrid.innerHTML = "";
    Object.entries(dimensions).forEach(([label, val]) => {
      const pct = Math.round(val);
      dimGrid.innerHTML += `
        <div class="dim-item">
          <div class="dim-label">
            <span>${escapeHtml(label)}</span><span>${pct}%</span>
          </div>
          <div class="dim-bar">
            <div class="dim-fill" style="width:${pct}%"></div>
          </div>
        </div>`;
    });
  }

  const feedbackCard = document.getElementById("feedback-card");
  if (feedbackCard) feedbackCard.style.display = "block";

  const nextBtn = document.getElementById("next-btn");
  if (nextBtn) {
    const isLast = window.currentQuestionIndex >= window.questions.length - 1;
    nextBtn.textContent = isLast ? "Finish Interview →" : "Next Question →";
  }
}


// ═══════════════════════════════════════════════════════════════
// FINISH INTERVIEW
// ═══════════════════════════════════════════════════════════════

async function finishInterview() {

  console.log("Interview complete. Saving report…");

  if (typeof CameraModule !== "undefined") CameraModule.stop();

  const answeredOnly = state.answers.filter(a => a.answer !== "(skipped)");

  const totalScore = answeredOnly.length > 0
    ? Math.round(answeredOnly.reduce((s, a) => s + (a.score || 0), 0) / answeredOnly.length)
    : 0;

  const dimTotals = {};
  const dimCounts = {};
  answeredOnly.forEach(a => {
    Object.entries(a.dimensions || {}).forEach(([k, v]) => {
      dimTotals[k] = (dimTotals[k] || 0) + v;
      dimCounts[k] = (dimCounts[k] || 0) + 1;
    });
  });
  const avgDimensions = {};
  Object.keys(dimTotals).forEach(k => {
    avgDimensions[k] = Math.round(dimTotals[k] / dimCounts[k]);
  });

  const scores = {
    overall         : totalScore,
    technical       : avgDimensions["accuracy"]  || totalScore,
    communication   : avgDimensions["clarity"]   || totalScore,
    confidence      : avgDimensions["relevance"] || totalScore,
    problem_solving : avgDimensions["depth"]     || totalScore,
    dimensions      : avgDimensions,
  };

  const nlpAnswers = answeredOnly.filter(a => a.nlp);
  const nlpAgg = {
    confidence  : nlpAnswers.length
      ? Math.round(nlpAnswers.reduce((s, a) => s + (a.nlp.confidence || 0), 0) / nlpAnswers.length)
      : 0,
    fillerCount : nlpAnswers.reduce((s, a) => s + (a.nlp.fillerCount || 0), 0),
    wpm         : nlpAnswers.length
      ? Math.round(nlpAnswers.reduce((s, a) => s + (a.nlp.wpm || 0), 0) / nlpAnswers.length)
      : 0,
    sentiment   : nlpAnswers.length
      ? nlpAnswers[nlpAnswers.length - 1].nlp.sentiment
      : { label: "neutral", score: 0 },
    keywords    : nlpAnswers.length
      ? nlpAnswers[nlpAnswers.length - 1].nlp.keywords || []
      : [],
  };

  const durationSec = Math.round((Date.now() - state.startTime) / 1000);

  const reportPayload = {
    session_id  : state.sessionId,
    analysis    : state.analysis,
    evaluations : state.answers,
    answers     : state.answers,
    scores,
    nlp         : nlpAgg,
    total_score : totalScore,
    duration_sec: durationSec,
  };

  try {

    const response = await fetch("/save-report", {
      method : "POST",
      headers: { "Content-Type": "application/json" },
      body   : JSON.stringify(reportPayload),
    });

    const data = await response.json();

    if (!data.success || !data.report_id) throw new Error(data.error || "Save failed");

    try {
      sessionStorage.setItem(
        "interview_report",
        JSON.stringify({ ...reportPayload, report_id: data.report_id, timestamp: new Date().toISOString() })
      );
    } catch (_) {}

    window.location.href = `/report?report_id=${data.report_id}`;

  } catch (err) {
    console.error("SAVE REPORT ERROR:", err);
    alert("Interview complete! Report could not be saved:\n" + err.message);
    window.location.href = "/";
  }
}


// ═══════════════════════════════════════════════════════════════
// UI HELPERS
// ═══════════════════════════════════════════════════════════════

function setQuestionText(text) {
  const el = document.getElementById("question-text");
  if (el) el.innerText = text;
}

function setSubmitEnabled(enabled) {
  const submitBtn = document.getElementById("submit-btn");
  const skipBtn   = document.getElementById("skip-btn");
  if (submitBtn) submitBtn.disabled = !enabled;
  if (skipBtn)   skipBtn.disabled   = !enabled;
}

function hideFeedback() {
  const card = document.getElementById("feedback-card");
  if (card) card.style.display = "none";
}

function showFeedbackLoading() {
  const feedbackEl = document.getElementById("score-feedback");
  if (feedbackEl) feedbackEl.textContent = "Evaluating your answer…";
  const numEl = document.getElementById("score-num");
  if (numEl) numEl.textContent = "…";
  const dimGrid = document.getElementById("dim-grid");
  if (dimGrid) dimGrid.innerHTML = "";
  const card = document.getElementById("feedback-card");
  if (card) card.style.display = "block";
}

function clearAnswer() {
  const el = document.getElementById("answer-text");
  if (el) el.value = "";
  if (typeof SpeechModule !== "undefined") {
    SpeechModule.clearTranscript();
  }
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

window.resetSpeechInput = function () {
  if (typeof SpeechModule !== "undefined") SpeechModule.clearTranscript();
};