"""
question_generator.py
Structured Interview Question Generator
========================================
Interview flow (30-40 minutes, 18 questions):

  SECTION 1 — Introduction        (3 questions)  ~5 mins
  SECTION 2 — Technical / Skills  (8 questions)  ~15 mins
  SECTION 3 — Projects            (4 questions)  ~10 mins
  SECTION 4 — Behavioural         (3 questions)  ~8 mins

Questions are ordered — never shuffled — so the interview
flows naturally from intro → technical → projects → behavioural.
"""

import random


class QuestionGenerator:

    def __init__(self):

        # ── SECTION 1: Introduction ───────────────────────────
        self.intro_questions = [
            "Please introduce yourself and tell me about your background.",
            "Can you walk me through your resume briefly?",
            "Tell me about your educational background and how it relates to this role.",
        ]

        # ── SECTION 2: Technical — by skill ──────────────────

        self.python_questions = [
            "What are the key differences between a list, tuple, and dictionary in Python?",
            "Explain how object-oriented programming works in Python with an example.",
            "What are Python decorators and when would you use them?",
            "How does memory management work in Python?",
            "What is the difference between *args and **kwargs in Python?",
            "Explain generators and how they differ from regular functions.",
            "What are lambda functions and when are they useful?",
            "How do you handle exceptions in Python?",
        ]

        self.ml_questions = [
            "Explain the difference between supervised and unsupervised learning.",
            "What is overfitting and how do you prevent it?",
            "Explain the bias-variance tradeoff.",
            "What evaluation metrics have you used and when do you choose each?",
            "Walk me through the machine learning pipeline from data to deployment.",
            "What is cross-validation and why is it important?",
            "How do you handle imbalanced datasets?",
            "Explain feature engineering and why it matters.",
        ]

        self.deep_learning_questions = [
            "What is backpropagation and how does it work?",
            "Explain the architecture of a Convolutional Neural Network.",
            "What is the difference between CNN and RNN?",
            "What is transfer learning and when should you use it?",
            "What optimisers have you used and how do they differ?",
            "Explain batch normalisation and dropout.",
        ]

        self.data_science_questions = [
            "How do you handle missing data in a dataset?",
            "Walk me through how you perform exploratory data analysis.",
            "What is the difference between correlation and causation?",
            "How do you decide which visualisation to use for a given dataset?",
            "Explain what descriptive statistics are and why they are useful.",
            "What is hypothesis testing and how have you used it?",
        ]

        self.sql_questions = [
            "Explain the different types of SQL JOINs with examples.",
            "What is the difference between WHERE and HAVING clauses?",
            "What are indexes in SQL and why do they improve performance?",
            "Explain database normalisation and its different forms.",
            "What are window functions in SQL? Give an example.",
            "How would you optimise a slow-running SQL query?",
        ]

        self.power_bi_questions = [
            "What is DAX and how have you used it in Power BI?",
            "Explain the difference between calculated columns and measures in Power BI.",
            "How do you create relationships between tables in Power BI?",
            "What types of visualisations have you built in Power BI?",
            "How do you handle data refresh and scheduling in Power BI?",
        ]

        self.tableau_questions = [
            "What types of charts have you built in Tableau?",
            "Explain the difference between dimensions and measures in Tableau.",
            "How do you create calculated fields in Tableau?",
            "What is a dashboard in Tableau and how do you make it interactive?",
            "How have you used Tableau to communicate insights to stakeholders?",
        ]

        self.excel_questions = [
            "What advanced Excel functions have you used — VLOOKUP, INDEX-MATCH, SUMIFS?",
            "How do you use Pivot Tables to summarise data?",
            "Explain how you have used Excel for data cleaning.",
            "What is conditional formatting and when do you use it?",
            "Have you used Excel macros or VBA? Explain your experience.",
        ]

        self.web_questions = [
            "Explain the difference between frontend and backend development.",
            "What is a REST API and how does it work?",
            "How does a React component lifecycle work?",
            "Explain how HTTP requests and responses work.",
            "What is CORS and why does it matter in web development?",
            "How do you manage state in a React application?",
        ]

        self.flask_questions = [
            "Explain the Flask request-response lifecycle.",
            "How do you handle authentication in a Flask application?",
            "What is the difference between GET and POST requests?",
            "How do you connect a Flask app to a database?",
            "Explain how you would structure a large Flask application.",
        ]

        self.cloud_questions = [
            "What AWS services have you worked with?",
            "Explain the difference between IaaS, PaaS, and SaaS.",
            "What is Docker and how does containerisation work?",
            "How do you manage secrets and environment variables in cloud deployments?",
            "Explain what CI/CD means and how you have used it.",
        ]

        self.git_questions = [
            "Explain the Git workflow — add, commit, push, pull.",
            "What is the difference between git merge and git rebase?",
            "How do you resolve merge conflicts in Git?",
            "What is a pull request and how does the code review process work?",
        ]

        self.general_technical_questions = [
            "What data structures do you use most often and why?",
            "Explain the difference between an array and a linked list.",
            "What is time complexity and why does it matter?",
            "How do you approach debugging a complex issue in your code?",
            "What is version control and why is it important?",
        ]

        # ── SECTION 3: Project questions ─────────────────────
        # (dynamically generated from resume projects)

        # ── SECTION 4: Behavioural ────────────────────────────
        self.behavioural_questions = [
            "Describe a challenging project you worked on and how you overcame the difficulties.",
            "Tell me about a time you had to learn a new technology quickly. How did you approach it?",
            "Describe a situation where you had to work as part of a team. What was your role?",
            "Tell me about a mistake you made in a project and what you learnt from it.",
            "How do you prioritise tasks when you have multiple deadlines?",
            "Describe a time you received critical feedback. How did you respond?",
            "Tell me about a project you are most proud of and why.",
            "How do you stay updated with the latest trends in your field?",
            "Describe a situation where you had to explain a technical concept to a non-technical person.",
            "What motivates you and how do you stay productive during difficult tasks?",
        ]

    # ── Skill → question pool mapping ────────────────────────

    def _get_skill_questions(self, skill: str) -> list:
        s = skill.lower()
        if "python"           in s: return self.python_questions
        if "machine learning" in s or "ml" in s: return self.ml_questions
        if "deep learning"    in s: return self.deep_learning_questions
        if "data science"     in s: return self.data_science_questions
        if "sql"              in s: return self.sql_questions
        if "power bi"         in s: return self.power_bi_questions
        if "tableau"          in s: return self.tableau_questions
        if "excel"            in s: return self.excel_questions
        if "flask"            in s: return self.flask_questions
        if "react"            in s or "javascript" in s or "html" in s: return self.web_questions
        if "aws"              in s or "azure" in s or "docker" in s: return self.cloud_questions
        if "git"              in s: return self.git_questions
        return self.general_technical_questions

    # ── Duplicate-safe sampler ────────────────────────────────

    @staticmethod
    def _safe_sample(pool: list, n: int) -> list:
        return random.sample(pool, min(n, len(pool)))

    # ── MAIN GENERATOR ────────────────────────────────────────

    def generate_questions(self, analysis: dict, num_questions: int = 18) -> list:
        """
        Generate a structured interview question list.

        Order:
          1. Introduction     — 3 questions
          2. Technical/Skills — 8 questions  (from candidate's skills)
          3. Projects         — 4 questions  (from candidate's projects)
          4. Behavioural      — 3 questions

        Total: 18 questions (~30-40 minutes)
        """

        analysis  = analysis or {}
        skills    = analysis.get("skills",   []) or []
        projects  = analysis.get("projects", []) or []

        final_questions = []
        seen            = set()

        def add(q: str):
            if q not in seen:
                seen.add(q)
                final_questions.append(q)

        # ══════════════════════════════════════════
        # SECTION 1 — INTRODUCTION (3 questions)
        # ══════════════════════════════════════════

        for q in self.intro_questions:
            add(q)

        # ══════════════════════════════════════════
        # SECTION 2 — TECHNICAL (8 questions)
        # ══════════════════════════════════════════

        tech_questions = []
        used_pools     = set()

        # Pull 2-3 questions from each relevant skill pool
        for skill in skills:
            pool_key = skill.lower()

            # Avoid duplicate pools (e.g. Flask and Python both map to similar)
            if pool_key in used_pools:
                continue
            used_pools.add(pool_key)

            pool    = self._get_skill_questions(skill)
            sampled = self._safe_sample(pool, 2)

            for q in sampled:
                if q not in seen and q not in tech_questions:
                    tech_questions.append(q)

            if len(tech_questions) >= 10:
                break

        # If not enough from skills, pad with general technical
        if len(tech_questions) < 8:
            for q in self._safe_sample(self.general_technical_questions, 8):
                if q not in seen and q not in tech_questions:
                    tech_questions.append(q)
                if len(tech_questions) >= 8:
                    break

        # Add exactly 8 technical questions
        for q in tech_questions[:8]:
            add(q)

        # ══════════════════════════════════════════
        # SECTION 3 — PROJECTS (4 questions)
        # ══════════════════════════════════════════

        project_questions = []

        for project in projects[:3]:
            if isinstance(project, dict):
                pname = project.get("name", str(project))
            else:
                pname = str(project).strip()

            if not pname or len(pname) < 3:
                continue

            project_questions.append(
                f"Can you walk me through your project '{pname}'? "
                f"What was the goal and what did you build?"
            )
            project_questions.append(
                f"What was the biggest technical challenge you faced in '{pname}' "
                f"and how did you solve it?"
            )

        # If fewer than 4 project questions, add generic ones
        generic_project_qs = [
            "Tell me about the most impactful project you have worked on.",
            "What technologies did you use in your most recent project and why?",
            "How did you approach testing and validation in your projects?",
            "What would you do differently if you could redo one of your projects?",
        ]

        for q in generic_project_qs:
            if len(project_questions) >= 4:
                break
            if q not in seen:
                project_questions.append(q)

        for q in project_questions[:4]:
            add(q)

        # ══════════════════════════════════════════
        # SECTION 4 — BEHAVIOURAL (3 questions)
        # ══════════════════════════════════════════

        for q in self._safe_sample(self.behavioural_questions, 3):
            add(q)

        # ══════════════════════════════════════════
        # FINAL TRIM TO num_questions
        # ══════════════════════════════════════════

        result = final_questions[:num_questions]

        print("=" * 60)
        print(f"INTERVIEW PLAN — {len(result)} questions (~30-40 mins)")
        print("=" * 60)
        section_names = {
            0: "INTRODUCTION",
            3: "TECHNICAL",
            11: "PROJECTS",
            15: "BEHAVIOURAL",
        }
        for i, q in enumerate(result):
            label = section_names.get(i, "")
            if label:
                print(f"\n── {label} ──")
            print(f"  Q{i+1}: {q[:80]}{'...' if len(q) > 80 else ''}")
        print("=" * 60)

        return result