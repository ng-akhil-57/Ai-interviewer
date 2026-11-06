"""
resume_analyser.py
Handles all PDF types:
  - Spaced text PDFs (A K H I L  N  G) → clean then parse
  - Normal text PDFs → parse directly
  - Image-only PDFs (Naveen) → OCR with pytesseract
"""

import os
import re
from pypdf import PdfReader
from dotenv import load_dotenv

load_dotenv()

# ── Paths — update if different on your machine ───────────────
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH   = r"C:\Users\Asus\Documents\Release-26.02.0-0\poppler-26.02.0\Library\bin"


# ─────────────────────────────────────────────────────────────
# TEXT CLEANER — fixes spaced PDFs like "A K H I L  N  G"
# ─────────────────────────────────────────────────────────────

def clean_spaced_text(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        tokens       = stripped.split(" ")
        single_count = sum(1 for t in tokens if len(t) == 1 and t.isalpha())
        total        = len(tokens)
        if total > 2 and single_count / total > 0.4:
            collapsed = re.sub(r"(?<=[A-Za-z]) (?=[A-Za-z])", "", stripped)
            words     = re.split(r"  +", collapsed)
            lines.append(" ".join(w.strip() for w in words if w.strip()))
        else:
            lines.append(stripped)
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# ANALYSER
# ─────────────────────────────────────────────────────────────

class ResumeAnalyser:

    def __init__(self):

        # Configure tesseract
        try:
            import pytesseract
            if os.path.exists(TESSERACT_PATH):
                pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
        except ImportError:
            pass

        self.skill_keywords = {
            "Python"          : ["python"],
            "Flask"           : ["flask"],
            "Django"          : ["django"],
            "FastAPI"         : ["fastapi"],
            "Machine Learning": ["machine learning", "scikit", "sklearn", "scikit-learn"],
            "Deep Learning"   : ["deep learning", "tensorflow", "pytorch", "keras"],
            "Data Science"    : ["data science"],
            "Computer Vision" : ["computer vision", "opencv"],
            "NLP"             : ["nlp", "natural language", "bert", "spacy"],
            "SQL"             : ["mysql", "postgresql", "sql", "sqlite"],
            "Power BI"        : ["power bi", "powerbi"],
            "Tableau"         : ["tableau"],
            "Excel"           : ["excel", "ms excel"],
            "HTML/CSS"        : ["html", "css"],
            "JavaScript"      : ["javascript"],
            "React"           : ["react"],
            "Node.js"         : ["node", "nodejs", "express"],
            "AWS"             : ["aws", "amazon web services"],
            "Azure"           : ["azure"],
            "GCP"             : ["gcp", "google cloud"],
            "Docker"          : ["docker"],
            "Git"             : ["git", "github", "gitlab"],
            "Statistics"      : ["statistics", "hypothesis", "probability", "descriptive"],
            "Matplotlib"      : ["matplotlib", "seaborn"],
            "NumPy"           : ["numpy"],
            "Pandas"          : ["pandas"],
            "LLM"             : ["llm", "langchain", "gpt"],
            "MongoDB"         : ["mongodb"],
            "EDA"             : ["eda", "exploratory data", "data cleaning", "preprocessing"],
        }

    # ─────────────────────────────────────────────
    # MAIN
    # ─────────────────────────────────────────────

    def analyse_from_file(self, pdf_path: str) -> dict:

        # Step 1: Try pypdf
        raw_text = self._pypdf_extract(pdf_path)

        # Step 2: If little/no text → OCR
        if len(raw_text.strip()) < 100:
            print("[ResumeAnalyser] pypdf got no text → trying OCR...")
            raw_text = self._ocr_extract(pdf_path)
        else:
            print(f"[ResumeAnalyser] pypdf extracted {len(raw_text)} chars")

        if not raw_text.strip():
            print("[ResumeAnalyser] ⚠️ No text extracted at all")
            return self._empty()

        # Step 3: Clean spaced text
        clean_text = clean_spaced_text(raw_text)

        # Step 4: Analyse
        return self.analyse_from_text(clean_text, raw_text)

    # ─────────────────────────────────────────────
    # PYPDF EXTRACTION
    # ─────────────────────────────────────────────

    def _pypdf_extract(self, pdf_path: str) -> str:
        text = ""
        try:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
        except Exception as e:
            print(f"[ResumeAnalyser] pypdf error: {e}")
        return text

    # ─────────────────────────────────────────────
    # OCR EXTRACTION
    # ─────────────────────────────────────────────

    def _ocr_extract(self, pdf_path: str) -> str:
        text = ""
        try:
            import pytesseract
            from pdf2image import convert_from_path

            poppler = POPPLER_PATH if os.path.exists(POPPLER_PATH) else None

            pages = convert_from_path(pdf_path, dpi=200, poppler_path=poppler)

            for i, img in enumerate(pages):
                page_text = pytesseract.image_to_string(img, lang="eng")
                text     += page_text + "\n"
                print(f"[ResumeAnalyser] OCR page {i+1}: {len(page_text)} chars")

            print(f"[ResumeAnalyser] Total OCR: {len(text)} chars")

        except ImportError:
            print("[ResumeAnalyser] ⚠️ pytesseract/pdf2image not installed")
        except Exception as e:
            print(f"[ResumeAnalyser] OCR error: {e}")

        return text

    # ─────────────────────────────────────────────
    # ANALYSE TEXT
    # ─────────────────────────────────────────────

    def analyse_from_text(self, clean_text: str, raw_text: str = "") -> dict:
        lower      = clean_text.lower()
        name       = self._extract_name(clean_text)
        skills     = self._extract_skills(lower)
        projects   = self._extract_projects(clean_text)
        education  = self._extract_education(clean_text)
        experience = self._extract_experience(lower)
        domain     = self._detect_domain(skills, lower)

        print(f"[ResumeAnalyser] ✅ Name: {name}")
        print(f"[ResumeAnalyser] ✅ Skills: {skills}")
        print(f"[ResumeAnalyser] ✅ Domain: {domain}")

        return {
            "name"      : name,
            "domain"    : domain,
            "skills"    : skills,
            "projects"  : projects,
            "education" : education,
            "experience": experience,
            "raw_text"  : (raw_text or clean_text)[:3000],
        }

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        return self._pypdf_extract(pdf_path)

    # ─────────────────────────────────────────────
    # NAME EXTRACTION
    # ─────────────────────────────────────────────

    def _extract_name(self, text: str) -> str:
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        skip_words = {
            "resume", "cv", "curriculum", "vitae", "profile", "summary",
            "objective", "contact", "email", "phone", "address", "linkedin",
            "github", "portfolio", "fresher", "engineer", "developer",
            "analyst", "scientist", "designer", "manager", "intern",
            "data", "science", "education", "skills", "projects",
            "certification", "experience", "technical",
        }

        for line in lines[:15]:
            words = line.split()

            if not (1 <= len(words) <= 4):
                continue
            if any(char.isdigit() for char in line):
                continue
            if any(c in line for c in ["@", "|", "·", "/", "\\", "+"]):
                continue
            if "http" in line.lower() or "www" in line.lower():
                continue
            if any(w.lower() in skip_words for w in words):
                continue
            if len(words) == 1 and len(line) < 4:
                continue

            all_alpha_words = [w for w in words if w.isalpha()]

            if len(all_alpha_words) >= 2:
                is_caps  = all(w.isupper() for w in all_alpha_words)
                is_title = all(w[0].isupper() for w in all_alpha_words if w)
                if is_caps or is_title:
                    return line

        m = re.search(
            r"(?:name\s*[:\-]?\s*)([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]*){1,3})",
            text
        )
        if m:
            return m.group(1).strip()

        return "Candidate"

    # ─────────────────────────────────────────────
    # SKILLS
    # ─────────────────────────────────────────────

    def _extract_skills(self, text: str) -> list:
        found = []
        for skill, keywords in self.skill_keywords.items():
            for kw in keywords:
                if kw in text:
                    if skill not in found:
                        found.append(skill)
                    break
        return found

    # ─────────────────────────────────────────────
    # PROJECTS
    # ─────────────────────────────────────────────

    def _extract_projects(self, text: str) -> list:
        projects = []
        capture  = False
        for line in text.split("\n"):
            lower = line.lower().strip()
            if not lower:
                continue
            if lower in ["projects", "project"]:
                capture = True
                continue
            if capture:
                if any(s in lower for s in [
                    "education", "skill", "experience",
                    "certification", "award", "language", "contact"
                ]):
                    break
                stripped = line.strip()
                if 3 < len(stripped) < 60:
                    words = stripped.split()
                    cap   = sum(1 for w in words if w and w[0].isupper())
                    if cap >= 1 and len(words) <= 8:
                        projects.append(stripped)
                if len(projects) >= 5:
                    break
        return projects

    # ─────────────────────────────────────────────
    # EDUCATION
    # ─────────────────────────────────────────────

    def _extract_education(self, text: str) -> str:
        keywords = [
            "b.tech", "b.e", "bachelor", "master", "mca", "bca",
            "m.tech", "bsc", "msc", "b.sc", "m.sc", "b sc", "m sc",
            "engineering", "university", "college", "institute",
        ]
        for line in text.split("\n"):
            lower = line.lower()
            if any(w in lower for w in keywords):
                return line.strip()
        return "Not found"

    # ─────────────────────────────────────────────
    # EXPERIENCE
    # ─────────────────────────────────────────────

    def _extract_experience(self, text: str) -> list:
        matches = re.findall(r"(\d+)\+?\s*(years?|months?)", text)
        return [f"{m[0]} {m[1]}" for m in matches] if matches else ["Fresher"]

    # ─────────────────────────────────────────────
    # DOMAIN DETECTION — fixed to correctly separate
    # Data Analyst vs AI/ML vs Data Scientist
    # ─────────────────────────────────────────────

    def _detect_domain(self, skills: list, raw_text: str = "") -> str:
        s = [x.lower() for x in skills]

        # Count signals per domain
        ml_signals      = sum(1 for x in [
            "machine learning", "deep learning", "nlp",
            "llm", "computer vision", "data science"
        ] if x in s)

        analyst_signals = sum(1 for x in [
            "power bi", "tableau", "excel", "eda", "statistics"
        ] if x in s)

        web_signals     = sum(1 for x in [
            "react", "javascript", "flask", "django", "html/css", "node.js"
        ] if x in s)

        cloud_signals   = sum(1 for x in [
            "aws", "azure", "gcp", "docker"
        ] if x in s)

        # Check raw text for job title hints
        is_data_analyst = any(phrase in raw_text for phrase in [
            "data analyst", "business analyst", "bi analyst",
            "kpi", "dashboard", "reporting"
        ])

        is_data_scientist = any(phrase in raw_text for phrase in [
            "data scientist", "machine learning engineer",
            "ml engineer", "ai engineer"
        ])

        # Decision logic — order matters

        # 1. Explicit job title in resume text
        if is_data_scientist and ml_signals >= 1:
            return "AI / Machine Learning"

        if is_data_analyst and ml_signals == 0:
            return "Data Analytics"

        # 2. Strong ML signals → AI/ML
        if ml_signals >= 2:
            return "AI / Machine Learning"

        # 3. Analyst tools dominate with weak/no ML → Data Analytics
        if analyst_signals >= 2 and ml_signals <= 1:
            return "Data Analytics"

        # 4. Some ML but also analyst tools → check which is stronger
        if ml_signals >= 1 and analyst_signals >= 1:
            if analyst_signals > ml_signals:
                return "Data Analytics"
            return "AI / Machine Learning"

        # 5. Single ML signal with no analyst tools
        if ml_signals == 1 and analyst_signals == 0:
            return "AI / Machine Learning"

        # 6. Web development
        if web_signals >= 2:
            return "Web Development"

        # 7. Cloud/DevOps
        if cloud_signals >= 1:
            return "Cloud / DevOps"

        # 8. SQL/data tools only
        if any(x in s for x in ["sql", "power bi", "tableau", "excel", "eda"]):
            return "Data Analytics"

        # 9. Python default
        if "python" in s:
            return "Software Engineering"

        return "Software Engineering"

    # ─────────────────────────────────────────────
    # EMPTY RESULT
    # ─────────────────────────────────────────────

    def _empty(self) -> dict:
        return {
            "name"      : "Candidate",
            "domain"    : "Software Engineering",
            "skills"    : [],
            "projects"  : [],
            "education" : "Not found",
            "experience": ["Fresher"],
            "raw_text"  : "",
        }