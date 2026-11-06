"""
answer_evaluator.py
Evaluates candidate answers using Claude API.
Returns score (0-100) + detailed feedback + dimension scores.
"""

import os
import json
import re
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def evaluate_answer(question: str, answer: str, domain: str = "", skills: list = None) -> dict:
    """
    Evaluate a candidate's answer to an interview question.
    
    Returns:
        {
            "score": int (0-100),
            "feedback": str (human-readable feedback as AI interviewer),
            "dimensions": {
                "accuracy": int,
                "depth": int,
                "clarity": int,
                "relevance": int
            },
            "strengths": [str],
            "improvements": [str]
        }
    """
    if not answer or answer.strip() == "":
        return {
            "score": 0,
            "feedback": "You didn't provide an answer to this question. It's important to attempt every question, even if you're unsure — a partial answer is always better than no answer.",
            "dimensions": {"accuracy": 0, "depth": 0, "clarity": 0, "relevance": 0},
            "strengths": [],
            "improvements": ["Always attempt to answer, even partially"]
        }

    skills_str = ", ".join(skills or []) if skills else "general"
    
    system_prompt = """You are a professional, warm, and encouraging AI interviewer evaluating a job candidate's answer.
Your evaluation must be:
- Fair and constructive (not harsh)
- Specific to the answer given
- Focused on technical accuracy AND communication quality
- Encouraging for good points, specific on improvement areas

ALWAYS respond with ONLY valid JSON. No markdown, no extra text."""

    user_prompt = f"""Evaluate this interview answer:

DOMAIN: {domain or 'General Technology'}
CANDIDATE SKILLS: {skills_str}
QUESTION: {question}
CANDIDATE ANSWER: {answer}

Respond ONLY with this JSON structure:
{{
  "score": <integer 0-100>,
  "feedback": "<2-4 sentence feedback as a friendly interviewer — acknowledge good points, suggest improvements naturally>",
  "dimensions": {{
    "accuracy": <0-100>,
    "depth": <0-100>,
    "clarity": <0-100>,
    "relevance": <0-100>
  }},
  "strengths": ["<specific strength 1>", "<specific strength 2>"],
  "improvements": ["<specific improvement 1>", "<specific improvement 2>"]
}}

Scoring guide:
- 85-100: Excellent, comprehensive, with examples
- 70-84: Good understanding, minor gaps
- 55-69: Adequate, correct basics but lacks depth
- 40-54: Partial understanding, significant gaps
- 0-39: Incorrect or very insufficient"""

    try:
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=600,
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt
        )

        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"```json|```", "", raw).strip()
        result = json.loads(raw)

        # Validate and clamp score
        result["score"] = max(0, min(100, int(result.get("score", 50))))
        return result

    except json.JSONDecodeError as e:
        print(f"[Evaluator] JSON parse error: {e}")
        return _fallback_evaluation(answer)
    except anthropic.APIError as e:
        print(f"[Evaluator] Anthropic API error: {e}")
        return _fallback_evaluation(answer)
    except Exception as e:
        print(f"[Evaluator] Unexpected error: {e}")
        return _fallback_evaluation(answer)


def _fallback_evaluation(answer: str) -> dict:
    """Simple keyword-based fallback when Claude API is unavailable."""
    word_count = len(answer.split())
    
    if word_count < 10:
        score = 25
        feedback = "Your answer was very brief. Try to elaborate more with examples and specific details."
    elif word_count < 30:
        score = 50
        feedback = "You've shown basic understanding. Try to add more specific examples and technical depth to your answers."
    elif word_count < 80:
        score = 65
        feedback = "Good effort! You've provided a reasonable answer. Adding concrete examples from your experience would make it stronger."
    else:
        score = 75
        feedback = "Well done! You've given a comprehensive answer. Keep this level of detail throughout the interview."

    return {
        "score": score,
        "feedback": feedback,
        "dimensions": {
            "accuracy": score,
            "depth": max(0, score - 10),
            "clarity": score,
            "relevance": score
        },
        "strengths": ["Attempted the question"],
        "improvements": ["Provide more specific examples", "Elaborate with technical details"]
    }


def batch_evaluate(qa_pairs: list, domain: str = "", skills: list = None) -> list:
    """
    Evaluate multiple Q&A pairs and return aggregate stats.
    
    Args:
        qa_pairs: [{"question": str, "answer": str}]
    
    Returns:
        list of evaluation results with added summary stats
    """
    results = []
    for pair in qa_pairs:
        result = evaluate_answer(
            question=pair.get("question", ""),
            answer=pair.get("answer", ""),
            domain=domain,
            skills=skills
        )
        results.append({
            "question": pair.get("question", ""),
            "answer": pair.get("answer", ""),
            **result
        })
    return results


def compute_overall_score(evaluations: list) -> dict:
    """Compute aggregate scores across all evaluations."""
    if not evaluations:
        return {"overall": 0, "dimensions": {}}

    scores = [e.get("score", 0) for e in evaluations]
    overall = round(sum(scores) / len(scores))

    dim_keys = ["accuracy", "depth", "clarity", "relevance"]
    dimensions = {}
    for key in dim_keys:
        vals = [e.get("dimensions", {}).get(key, 0) for e in evaluations]
        dimensions[key] = round(sum(vals) / len(vals)) if vals else 0

    # Map dimensions to report categories
    return {
        "overall": overall,
        "technical": dimensions.get("accuracy", 0),
        "communication": dimensions.get("clarity", 0),
        "problem_solving": dimensions.get("depth", 0),
        "confidence": min(100, overall + 5),
        "dimensions": dimensions
    }
