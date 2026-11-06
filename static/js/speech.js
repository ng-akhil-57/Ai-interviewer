/**
 * speech.js  — v2 (NLP Edition)
 * ==============================
 * New in v2:
 *  ✅ Filler-word removal  (um, uh, like, you know, basically, …)
 *  ✅ Keyword extraction   (TF-IDF-lite, domain-aware stop-words)
 *  ✅ Voice confidence     (speech pace, hesitation density, avg word length)
 *  ✅ Sentiment signal     (positive / neutral / negative word lists)
 *  ✅ Real-time NLP badge  shown next to the transcript
 *  ✅ All v1 recognition & TTS behaviour preserved
 */

const SpeechModule = (() => {

  // ─────────────────────────────────────────────
  // NLP DATA
  // ─────────────────────────────────────────────

  const FILLER_WORDS = new Set([
    'um','uh','uhh','umm','er','err','ah','ahh',
    'like','basically','literally','actually','honestly',
    'you know','i mean','kind of','sort of','kinda','sorta',
    'right','okay','ok','so','well','just','really',
    'very','quite','maybe','perhaps','anyway'
  ]);

  // Stop-words excluded from keyword extraction
  const STOP_WORDS = new Set([
    'a','an','the','and','or','but','in','on','at','to','for',
    'of','with','by','from','is','it','its','was','are','be',
    'been','being','have','has','had','do','does','did','will',
    'would','could','should','may','might','shall','can',
    'this','that','these','those','i','we','you','he','she','they',
    'my','your','our','their','me','him','her','us','them',
    'not','no','nor','so','yet','both','either','whether',
    'what','which','who','whom','whose','when','where','why','how',
    'all','any','each','few','more','most','other','some','such',
    ...FILLER_WORDS
  ]);

  // Positive / negative word pools for sentiment
  const POSITIVE_WORDS = new Set([
    'good','great','excellent','strong','best','love','enjoy','success',
    'confident','proud','optimistic','innovative','effective','efficient',
    'improved','solved','built','designed','led','achieved','delivered',
    'implemented','created','developed','launched','optimised','streamlined'
  ]);

  const NEGATIVE_WORDS = new Set([
    'bad','wrong','failed','error','problem','issue','difficult','hard',
    'struggle','unsure','confused','unclear','never','cannot','couldn\'t',
    'didn\'t','won\'t','don\'t','not','lack','missing','weak','poor'
  ]);

  // ─────────────────────────────────────────────
  // STATE
  // ─────────────────────────────────────────────

  let recognition      = null;
  let synthesis        = window.speechSynthesis;
  let isListening      = false;
  let isSpeaking       = false;
  let rawTranscript    = '';        // includes fillers
  let cleanTranscript  = '';        // filler-stripped
  let onResultCallback = null;
  let onStatusCallback = null;
  let preferredVoice   = null;

  // NLP state
  let wordTimestamps   = [];        // {word, ts} — for pace calc
  let fillerCount      = 0;
  let totalWordCount   = 0;

  // ─────────────────────────────────────────────
  // NLP UTILITIES
  // ─────────────────────────────────────────────

  /**
   * removeFiller
   * Strips filler words from a transcript string.
   * Handles multi-word fillers first, then single tokens.
   */
  function removeFiller(text) {
    let out = text;

    // Multi-word fillers  (order matters — longest first)
    const multiWord = [
      'you know','i mean','kind of','sort of','you see','as well'
    ];
    for (const mw of multiWord) {
      const re = new RegExp(`\\b${mw}\\b,?`, 'gi');
      out = out.replace(re, '');
    }

    // Single-word fillers
    out = out.split(/\s+/).filter(token => {
      const clean = token.replace(/[^a-z]/gi, '').toLowerCase();
      return clean.length > 0 && !FILLER_WORDS.has(clean);
    }).join(' ');

    return out.trim();
  }

  /**
   * extractKeywords
   * Returns top-N keywords ranked by frequency × inverse-rarity.
   * (TF-IDF lite — no corpus needed, uses stop-word exclusion instead)
   */
  function extractKeywords(text, topN = 8) {
    const tokens = text.toLowerCase()
      .replace(/[^a-z\s]/g, ' ')
      .split(/\s+/)
      .filter(t => t.length > 3 && !STOP_WORDS.has(t));

    const freq = {};
    for (const t of tokens) {
      freq[t] = (freq[t] || 0) + 1;
    }

    return Object.entries(freq)
      .sort((a, b) => b[1] - a[1])
      .slice(0, topN)
      .map(([word, count]) => ({ word, count }));
  }

  /**
   * analyseConfidence
   * Returns a 0–100 score based on:
   *   • speech pace (words / minute)       — 110-160 wpm = ideal
   *   • hesitation density                 — filler % of total words
   *   • avg word length                    — proxy for vocabulary richness
   */
  function analyseConfidence(text, durationSec) {
    const words      = text.split(/\s+/).filter(Boolean);
    const wordCount  = words.length;
    if (wordCount < 3 || durationSec < 1) return 50;

    const wpm           = (wordCount / durationSec) * 60;
    const avgWordLen    = words.reduce((s, w) => s + w.length, 0) / wordCount;
    const fillerRatio   = fillerCount / Math.max(1, totalWordCount);

    // Pace score (100 at 130 wpm, drops outside 90–180)
    const paceScore = Math.max(0, 100 - Math.abs(wpm - 130) * 0.8);

    // Hesitation penalty
    const hesScore  = Math.max(0, 100 - fillerRatio * 300);

    // Vocabulary richness (ideal avg length 5–7 chars)
    const vocabScore = Math.min(100, avgWordLen * 14);

    const combined = Math.round(paceScore * 0.45 + hesScore * 0.35 + vocabScore * 0.20);
    return Math.max(0, Math.min(100, combined));
  }

  /**
   * analyseSentiment
   * Returns { score: -1..1, label: 'positive'|'neutral'|'negative' }
   */
  function analyseSentiment(text) {
    const tokens = text.toLowerCase().split(/\W+/);
    let pos = 0, neg = 0;
    for (const t of tokens) {
      if (POSITIVE_WORDS.has(t)) pos++;
      if (NEGATIVE_WORDS.has(t)) neg++;
    }
    const total = pos + neg || 1;
    const score = (pos - neg) / total;
    const label = score > 0.15 ? 'positive' : score < -0.15 ? 'negative' : 'neutral';
    return { score: parseFloat(score.toFixed(2)), label };
  }

  // ─────────────────────────────────────────────
  // INIT
  // ─────────────────────────────────────────────

  let _startTime = null;

  function init() {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      console.warn('[Speech] Not supported in this browser');
      showStatus('⚠️ Voice recognition not supported. Use Chrome or Edge.');
      return false;
    }

    recognition = new SpeechRecognition();
    recognition.continuous      = true;
    recognition.interimResults  = true;
    recognition.lang            = 'en-US';
    recognition.maxAlternatives = 1;

    // ── Events ──────────────────────────────────

    recognition.onstart = () => {
      isListening = true;
      _startTime  = Date.now();
      updateMicBtn(true);
      showWaveform(true);
      showStatus('🎙️ Listening…');
    };

    recognition.onresult = (event) => {
      let interim   = '';
      let finalText = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const text = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalText += text + ' ';

          // Track word timestamps & filler count
          const newWords = text.trim().split(/\s+/);
          const now      = Date.now();
          for (const w of newWords) {
            totalWordCount++;
            wordTimestamps.push({ word: w, ts: now });
            const clean = w.replace(/[^a-z]/gi,'').toLowerCase();
            if (FILLER_WORDS.has(clean)) fillerCount++;
          }
        } else {
          interim += text;
        }
      }

      rawTranscript  += finalText;
      cleanTranscript = removeFiller(rawTranscript);

      const displayText = (cleanTranscript + interim).trim();
      updateVoiceText(displayText);

      // Compute NLP metrics on every result
      const elapsed    = (_startTime ? (Date.now() - _startTime) / 1000 : 10);
      const keywords   = extractKeywords(cleanTranscript);
      const confidence = analyseConfidence(cleanTranscript, elapsed);
      const sentiment  = analyseSentiment(cleanTranscript);

      updateNLPBadge({ keywords, confidence, sentiment, fillerCount });

      if (onResultCallback) {
        onResultCallback({
          interim:    interim.trim(),
          final:      finalText.trim(),
          full:       displayText,
          raw:        rawTranscript.trim(),
          clean:      cleanTranscript,
          keywords,
          confidence,
          sentiment,
          fillerCount,
          wpm: totalWordCount > 0 && elapsed > 0
               ? Math.round((totalWordCount / elapsed) * 60) : 0,
        });
      }
    };

    recognition.onerror = (event) => {
      console.error('[Speech] Error:', event.error);
      switch (event.error) {
        case 'not-allowed':  showStatus('❌ Microphone permission denied'); stopListening(); break;
        case 'no-speech':    showStatus('🔇 No speech detected'); break;
        case 'audio-capture':showStatus('🎤 No microphone found'); stopListening(); break;
        case 'network':      showStatus('📶 Network issue'); break;
        case 'aborted':      break;
        default:             showStatus(`⚠️ ${event.error}`);
      }
    };

    recognition.onend = () => {
      updateMicBtn(false);
      showWaveform(false);
      if (isListening) {
        try { recognition.start(); }
        catch (err) { isListening = false; }
      }
    };

    loadVoices();
    if (speechSynthesis.onvoiceschanged !== undefined) {
      speechSynthesis.onvoiceschanged = loadVoices;
    }
    return true;
  }

  // ─────────────────────────────────────────────
  // TTS VOICES
  // ─────────────────────────────────────────────

  function loadVoices() {
    const voices = synthesis.getVoices();
    if (!voices.length) return;
    const preferred = [
      'Google UK English Female','Google US English',
      'Microsoft Zira Desktop','Samantha','Alex'
    ];
    preferredVoice = null;
    for (const name of preferred) {
      const v = voices.find(v => v.name === name);
      if (v) { preferredVoice = v; break; }
    }
    if (!preferredVoice)
      preferredVoice = voices.find(v => v.lang.startsWith('en')) || voices[0];
  }

  // ─────────────────────────────────────────────
  // LISTEN / STOP / TOGGLE
  // ─────────────────────────────────────────────

  function startListening() {
    if (!recognition) init();
    if (!recognition || isListening) return;

    rawTranscript   = '';
    cleanTranscript = '';
    fillerCount     = 0;
    totalWordCount  = 0;
    wordTimestamps  = [];
    updateVoiceText('');
    hideNLPBadge();

    try { recognition.start(); }
    catch (err) { console.error('[Speech] Failed to start:', err); }
  }

  function stopListening() {
    if (!recognition) return;
    isListening = false;
    try { recognition.stop(); } catch {}
    updateMicBtn(false);
    showWaveform(false);

    const finalClean = cleanTranscript.trim();
    if (finalClean) {
      showStatus(`✅ Captured: "${finalClean.slice(0, 60)}${finalClean.length > 60 ? '…' : ''}"`);
    } else {
      showStatus('⚠️ No speech captured');
    }
    return finalClean;
  }

  function toggleListening() {
    return isListening ? stopListening() : (startListening(), null);
  }

  function clearTranscript() {
    rawTranscript   = '';
    cleanTranscript = '';
    fillerCount     = 0;
    totalWordCount  = 0;
    wordTimestamps  = [];
    updateVoiceText('');
    hideNLPBadge();
  }

  // ─────────────────────────────────────────────
  // TTS SPEAK
  // ─────────────────────────────────────────────

  function speak(text, options = {}) {
    if (!synthesis || !text) return;
    const cleanText = text.replace(/<[^>]*>/g, '');
    synthesis.cancel();

    const utt   = new SpeechSynthesisUtterance(cleanText);
    utt.voice   = preferredVoice;
    utt.rate    = options.rate   || 0.95;
    utt.pitch   = options.pitch  || 1;
    utt.volume  = options.volume || 1;
    utt.lang    = 'en-US';

    utt.onstart = () => { isSpeaking = true;  if (onStatusCallback) onStatusCallback('speaking'); };
    utt.onend   = () => { isSpeaking = false; if (onStatusCallback) onStatusCallback('idle'); };
    utt.onerror = (e) => { console.error('[Speech] TTS:', e); isSpeaking = false; };

    synthesis.speak(utt);
  }

  function stopSpeaking() {
    if (synthesis) synthesis.cancel();
    isSpeaking = false;
  }

  // ─────────────────────────────────────────────
  // NLP RESULTS — public getter
  // ─────────────────────────────────────────────

  function getNLPSummary() {
    const elapsed = _startTime ? (Date.now() - _startTime) / 1000 : 10;
    return {
      clean:        cleanTranscript,
      raw:          rawTranscript,
      keywords:     extractKeywords(cleanTranscript),
      confidence:   analyseConfidence(cleanTranscript, elapsed),
      sentiment:    analyseSentiment(cleanTranscript),
      fillerCount,
      totalWordCount,
      wpm: totalWordCount > 0 && elapsed > 0
           ? Math.round((totalWordCount / elapsed) * 60) : 0,
    };
  }

  // ─────────────────────────────────────────────
  // UI HELPERS
  // ─────────────────────────────────────────────

  function showWaveform(show) {
    const display = document.getElementById('voice-display');
    if (!display) return;
    display.innerHTML = show
      ? `<div class="waveform">
           <div class="wave-bar"></div><div class="wave-bar"></div>
           <div class="wave-bar"></div><div class="wave-bar"></div>
           <div class="wave-bar"></div>
         </div>
         <span id="voice-text" style="margin-left:10px;color:#94a3b8">Listening…</span>`
      : `<span id="voice-text">Click mic or type answer…</span>`;
  }

  function updateVoiceText(text) {
    const el = document.getElementById('voice-text');
    if (el) {
      el.textContent = text || (isListening ? 'Listening…' : 'Click mic or type answer…');
      el.style.color = text ? '#e2e8f0' : '#64748b';
    }
    const ta = document.getElementById('answer-text');
    if (ta && text) ta.value = text;
  }

  function updateMicBtn(active) {
    const btn = document.getElementById('mic-btn');
    if (!btn) return;
    if (active) {
      btn.classList.add('listening');
      btn.innerHTML = '🔴';
      btn.title     = 'Stop Recording';
    } else {
      btn.classList.remove('listening');
      btn.innerHTML = '🎤';
      btn.title     = 'Start Recording';
    }
  }

  function showStatus(msg) {
    const el = document.getElementById('voice-text');
    if (el) { el.textContent = msg; el.style.color = '#94a3b8'; }
  }

  /** Render the NLP insight badge below the transcript */
  function updateNLPBadge({ keywords, confidence, sentiment, fillerCount }) {
    let badge = document.getElementById('nlp-badge');
    if (!badge) {
      badge = document.createElement('div');
      badge.id = 'nlp-badge';
      badge.style.cssText = `
        margin-top:10px;padding:10px 14px;border-radius:12px;
        background:rgba(108,99,255,.08);border:1px solid rgba(108,99,255,.2);
        font-size:12px;color:#94a3b8;line-height:1.7;
        font-family:'Inter',sans-serif;transition:all .3s ease;
      `;
      const voiceDisplay = document.getElementById('voice-display');
      if (voiceDisplay && voiceDisplay.parentNode) {
        voiceDisplay.parentNode.insertBefore(badge, voiceDisplay.nextSibling);
      }
    }

    const sentColor = sentiment.label === 'positive' ? '#4ade80'
                    : sentiment.label === 'negative'  ? '#f87171' : '#94a3b8';
    const confColor = confidence > 70 ? '#4ade80'
                    : confidence > 45 ? '#fbbf24' : '#f87171';
    const topKw = keywords.slice(0, 5).map(k => k.word).join(', ') || '—';

    badge.innerHTML = `
      <div style="display:flex;gap:18px;flex-wrap:wrap;align-items:center">
        <span title="Confidence score based on pace, hesitation & vocabulary">
          🧠 Confidence:
          <strong style="color:${confColor}">${confidence}%</strong>
        </span>
        <span title="Tone of your response">
          ${sentiment.label === 'positive' ? '😊' : sentiment.label === 'negative' ? '😟' : '😐'}
          Tone: <strong style="color:${sentColor}">${sentiment.label}</strong>
        </span>
        <span title="Filler words detected (um, uh, like…)">
          🔇 Fillers: <strong style="color:#fbbf24">${fillerCount}</strong>
        </span>
      </div>
      <div style="margin-top:6px">
        🏷️ Keywords: <span style="color:#a78bfa">${topKw}</span>
      </div>
    `;
    badge.style.display = 'block';
  }

  function hideNLPBadge() {
    const badge = document.getElementById('nlp-badge');
    if (badge) badge.style.display = 'none';
  }

  // ─────────────────────────────────────────────
  // CALLBACKS
  // ─────────────────────────────────────────────

  function onResult(cb)  { onResultCallback  = cb; }
  function onStatus(cb)  { onStatusCallback  = cb; }

  // ─────────────────────────────────────────────
  // GETTERS
  // ─────────────────────────────────────────────

  function getTranscript()   { return cleanTranscript.trim(); }
  function getRawTranscript(){ return rawTranscript.trim(); }
  function getIsListening()  { return isListening; }
  function getIsSpeaking()   { return isSpeaking; }

  // ─────────────────────────────────────────────
  // PUBLIC API
  // ─────────────────────────────────────────────

  return {
    init,
    startListening, stopListening, toggleListening,
    clearTranscript,
    speak, stopSpeaking,
    onResult, onStatus,
    getTranscript, getRawTranscript,
    getIsListening, getIsSpeaking,
    getNLPSummary,
    // expose NLP utils for tests / external use
    nlp: { removeFiller, extractKeywords, analyseConfidence, analyseSentiment }
  };

})();
