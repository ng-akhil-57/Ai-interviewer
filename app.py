"""
app.py  — AI Interviewer v2 (FINAL)
====================================================
Run with SSL so camera + microphone work in Chrome:
    python generate_cert.py   ← run once first
    python app.py
Then open: https://localhost:5000
Click Advanced → Proceed to localhost (unsafe)
"""

import os
import json
import uuid
import time
import ssl
from datetime import datetime

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv

from resume_analyser import ResumeAnalyser
from question_generator import QuestionGenerator
from answer_evaluator import evaluate_answer, compute_overall_score
from cheat_detector import detector


# ─────────────────────────────────────────────
# INIT
# ─────────────────────────────────────────────

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)

CORS(app)

app.config["UPLOAD_FOLDER"]  = os.path.join(BASE_DIR, "uploads")
app.config["REPORTS_FOLDER"] = os.path.join(BASE_DIR, "reports")

os.makedirs(app.config["UPLOAD_FOLDER"],  exist_ok=True)
os.makedirs(app.config["REPORTS_FOLDER"], exist_ok=True)

sessions = {}

analyser  = ResumeAnalyser()
generator = QuestionGenerator()


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def cleanup_old_sessions():
    now     = time.time()
    expired = [sid for sid, d in sessions.items()
               if now - d.get("created_at", 0) > 3600]
    for sid in expired:
        sessions.pop(sid, None)
        print(f"Expired session removed: {sid}")


def get_session(session_id):
    return sessions.get(session_id)


# ─────────────────────────────────────────────
# FRONTEND ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/interview")
def interview():
    return render_template("interview.html")


@app.route("/report")
def report():
    return render_template("report.html")


# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "anthropic_key": (
            "configured" if os.getenv("ANTHROPIC_API_KEY") else "missing"
        ),
        "active_sessions": len(sessions),
        "ssl": os.path.exists(os.path.join(BASE_DIR, "cert.pem")),
    })


# ─────────────────────────────────────────────
# UPLOAD RESUME
# ─────────────────────────────────────────────

@app.route("/upload-resume", methods=["POST"])
def upload_resume():

    try:

        cleanup_old_sessions()

        if "file" not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400

        file = request.files["file"]

        if not file.filename:
            return jsonify({"success": False, "error": "Empty filename"}), 400

        if not file.filename.lower().endswith(".pdf"):
            return jsonify({"success": False, "error": "Only PDF files allowed"}), 400

        session_id = str(uuid.uuid4())
        filepath   = os.path.join(app.config["UPLOAD_FOLDER"], f"{session_id}.pdf")

        file.save(filepath)
        print(f"Resume saved: {filepath}")

        analysis = analyser.analyse_from_file(filepath) or {}
        print("Resume analysis:", json.dumps(analysis, indent=2))

        sessions[session_id] = {
            "analysis"  : analysis,
            "answers"   : [],
            "questions" : [],
            "scores"    : [],
            "created_at": time.time(),
        }

        detector.reset()

        return jsonify({
            "success"   : True,
            "session_id": session_id,
            "analysis"  : analysis,
        })

    except Exception as e:
        print("UPLOAD ERROR:", e)
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────
# GENERATE QUESTIONS
# ─────────────────────────────────────────────

@app.route("/get-questions", methods=["POST"])
def get_questions():

    try:

        data       = request.get_json(force=True) or {}
        session_id = data.get("session_id")

        if not session_id:
            return jsonify({"success": False, "error": "session_id missing"}), 400

        session = get_session(session_id)
        if session is None:
            return jsonify({"success": False, "error": "Invalid or expired session"}), 400

        analysis  = session.get("analysis", {})
        questions = generator.generate_questions(analysis=analysis, num_questions=18)

        if not questions:
            return jsonify({"success": False, "error": "Question generation failed"}), 500

        session["questions"] = questions

        return jsonify({
            "success"  : True,
            "questions": questions,
            "count"    : len(questions),
        })

    except Exception as e:
        print("GET QUESTIONS ERROR:", e)
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────
# EVALUATE ANSWER
# ─────────────────────────────────────────────

@app.route("/evaluate-answer", methods=["POST"])
def evaluate_answer_route():

    try:

        data       = request.get_json(force=True) or {}
        question   = data.get("question", "")
        answer     = data.get("answer", "")
        domain     = data.get("domain", "")
        skills     = data.get("skills", [])
        session_id = data.get("session_id")

        result = evaluate_answer(
            question=question,
            answer=answer,
            domain=domain,
            skills=skills,
        )

        if session_id:
            session = get_session(session_id)
            if session is not None:
                session["answers"].append({
                    "question"  : question,
                    "answer"    : answer,
                    "score"     : result.get("score", 0),
                    "feedback"  : result.get("feedback", ""),
                    "dimensions": result.get("dimensions", {}),
                })
                session["scores"].append(result.get("score", 0))

        return jsonify({"success": True, **result})

    except Exception as e:
        print("EVALUATE ANSWER ERROR:", e)
        return jsonify({
            "success" : False,
            "score"   : 50,
            "feedback": str(e),
        }), 500


# ─────────────────────────────────────────────
# ANALYSE FRAME
# ─────────────────────────────────────────────

@app.route("/analyse-frame", methods=["POST"])
def analyse_frame():

    try:

        data      = request.get_json(force=True) or {}
        b64_frame = data.get("frame", "")

        if not b64_frame:
            return jsonify({"success": False, "error": "No frame provided"}), 400

        result = detector.analyse_frame(b64_frame)

        return jsonify({
            "success"        : True,
            "event"          : {
                "type"    : result.event.type,
                "message" : result.event.message,
                "severity": result.event.severity,
            },
            "annotated_b64"  : result.annotated_b64 or "",
            "face_confidence": round(result.face_confidence, 3),
        })

    except Exception as e:
        print("FRAME ANALYSIS ERROR:", e)
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────
# PROCTOR SUMMARY
# ─────────────────────────────────────────────

@app.route("/proctor-summary", methods=["GET"])
def proctor_summary():

    try:
        summary = detector.get_summary()
        return jsonify({"success": True, "summary": summary})

    except Exception as e:
        print("PROCTOR SUMMARY ERROR:", e)
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────
# SAVE REPORT
# ─────────────────────────────────────────────

@app.route("/save-report", methods=["POST"])
def save_report():

    try:

        report     = request.get_json(force=True) or {}
        session_id = report.get("session_id")

        if session_id:
            session = get_session(session_id)
            if session:
                if not report.get("answers"):
                    report["answers"] = session.get("answers", [])
                scores = [a.get("score", 0) for a in report["answers"]
                          if a.get("answer") != "(skipped)"]
                report["total_score"] = (
                    round(sum(scores) / len(scores)) if scores else 0
                )

        if not report.get("proctor"):
            report["proctor"] = detector.get_summary()

        report_id           = str(uuid.uuid4())
        report["report_id"] = report_id
        report["timestamp"] = datetime.utcnow().isoformat()

        filepath = os.path.join(
            app.config["REPORTS_FOLDER"], f"{report_id}.json"
        )

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"Report saved: {filepath}")

        if session_id:
            sessions.pop(session_id, None)

        return jsonify({"success": True, "report_id": report_id})

    except Exception as e:
        print("SAVE REPORT ERROR:", e)
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────
# GET REPORT
# ─────────────────────────────────────────────

@app.route("/get-report/<report_id>", methods=["GET"])
def get_report(report_id):

    try:

        safe_id  = "".join(c for c in report_id if c.isalnum() or c == "-")
        filepath = os.path.join(app.config["REPORTS_FOLDER"], f"{safe_id}.json")

        if not os.path.exists(filepath):
            return jsonify({"success": False, "error": "Report not found"}), 404

        with open(filepath, "r", encoding="utf-8") as f:
            report = json.load(f)

        return jsonify({"success": True, "report": report})

    except Exception as e:
        print("GET REPORT ERROR:", e)
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────
# RESET SESSION
# ─────────────────────────────────────────────

@app.route("/reset-session", methods=["POST"])
def reset_session():

    try:

        data       = request.get_json(force=True) or {}
        session_id = data.get("session_id")

        if session_id:
            sessions.pop(session_id, None)

        detector.reset()

        return jsonify({"success": True, "message": "Session reset"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────
# RUN SERVER — with SSL if cert exists
# ─────────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 60)
    print("AI Interviewer v2 Starting…")
    print("=" * 60)

    cert_file = os.path.join(BASE_DIR, "cert.pem")
    key_file  = os.path.join(BASE_DIR, "key.pem")

    if os.path.exists(cert_file) and os.path.exists(key_file):
        # Build SSL context from our self-signed cert
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(cert_file, key_file)

        print("🔒 SSL enabled — open https://localhost:5000")
        print("   Chrome will warn 'not private' — click Advanced → Proceed")
        print("=" * 60)

        app.run(
            debug=True,
            host="0.0.0.0",
            port=5000,
            ssl_context=ssl_ctx,
            use_reloader=False,
        )

    else:
        print("⚠️  No SSL cert found — running on HTTP")
        print("   Camera and microphone will NOT work!")
        print("   Run: python generate_cert.py  then restart")
        print("=" * 60)

        app.run(
            debug=True,
            host="0.0.0.0",
            port=5000,
            use_reloader=False,
        )