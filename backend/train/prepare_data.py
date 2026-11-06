"""
backend/train/prepare_data.py  —  STEP 2
Reads all resume PDFs from data/resumes/
Extracts text and builds structured training data for BERT and T5.

Run: python backend/train/prepare_data.py
"""

import os
import re
import json
import spacy
from pathlib import Path
from pypdf import PdfReader
from tqdm import tqdm

# ── CONFIG ──────────────────────────────────────────────────────────────────
RESUMES_DIR   = Path("data/resumes")
OUTPUT_DIR    = Path("data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── DOMAIN KEYWORDS ──────────────────────────────────────────────────────────
DOMAIN_KEYWORDS = {
    "data_science":       ["machine learning", "deep learning", "nlp", "data science",
                           "tensorflow", "pytorch", "sklearn", "pandas", "matplotlib",
                           "neural network", "computer vision", "reinforcement learning"],
    "software_engineering":["java", "spring boot", "microservices", "rest api", "docker",
                            "kubernetes", "ci/cd", "git", "agile", "software development"],
    "web_development":    ["react", "angular", "vue", "node.js", "django", "flask",
                           "html", "css", "javascript", "typescript", "mongodb"],
    "data_engineering":   ["spark", "kafka", "airflow", "etl", "pipeline", "hadoop",
                           "sql", "postgresql", "data warehouse", "bigquery"],
    "cloud_devops":       ["aws", "azure", "gcp", "terraform", "ansible", "jenkins",
                           "linux", "bash", "devops", "cloud"],
    "cybersecurity":      ["penetration testing", "siem", "firewall", "encryption",
                           "vulnerability", "ethical hacking", "security"],
}

SKILL_PATTERNS = [
    "python", "r", "java", "c++", "sql", "tensorflow", "pytorch", "keras",
    "scikit-learn", "pandas", "numpy", "matplotlib", "seaborn", "spark",
    "hadoop", "aws", "azure", "gcp", "docker", "kubernetes", "git",
    "react", "node.js", "django", "flask", "mongodb", "postgresql",
    "tableau", "power bi", "excel", "nlp", "computer vision", "opencv",
    "huggingface", "transformers", "bert", "gpt", "llm", "langchain",
    "machine learning", "deep learning", "data science", "statistics",
    "linux", "bash", "rest api", "graphql", "microservices",
]

# ── PDF EXTRACTION ───────────────────────────────────────────────────────────
def extract_text(pdf_path: str) -> str:
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text += content + "\n"
        return text.strip()
    except Exception as e:
        print(f"  ⚠️  Failed to read {pdf_path}: {e}")
        return ""


# ── SECTION SPLITTER ──────────────────────────────────────────────────────────
SECTION_HEADERS = {
    "experience":  r"(work experience|experience|employment|professional experience)",
    "education":   r"(education|academic|qualification|degree)",
    "skills":      r"(skills|technical skills|core competencies|technologies)",
    "projects":    r"(projects|personal projects|academic projects|key projects)",
    "summary":     r"(summary|objective|profile|about me|career objective)",
    "certifications": r"(certifications|certificates|achievements|awards)",
}

def split_sections(text: str) -> dict:
    sections = {k: "" for k in SECTION_HEADERS}
    lines = text.split("\n")
    current = "summary"
    for line in lines:
        lower = line.lower().strip()
        matched = False
        for section, pattern in SECTION_HEADERS.items():
            if re.search(pattern, lower):
                current = section
                matched = True
                break
        if not matched:
            sections[current] += line + "\n"
    return sections


# ── SKILL EXTRACTOR ───────────────────────────────────────────────────────────
def extract_skills(text: str) -> list:
    text_lower = text.lower()
    found = []
    for skill in SKILL_PATTERNS:
        if skill in text_lower:
            found.append(skill)
    return list(set(found))


# ── DOMAIN CLASSIFIER ────────────────────────────────────────────────────────
def classify_domain(text: str) -> str:
    text_lower = text.lower()
    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for kw in keywords if kw in text_lower)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


# ── YEARS OF EXPERIENCE ───────────────────────────────────────────────────────
def extract_years(text: str) -> str:
    patterns = [
        r"(\d+)\+?\s*years?\s*of\s*experience",
        r"(\d+)\+?\s*years?\s*experience",
        r"experience\s*of\s*(\d+)\+?\s*years?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return match.group(1) + " years"
    return "Fresher"


# ── NAME EXTRACTOR (spaCy) ────────────────────────────────────────────────────
def extract_name(text: str, nlp) -> str:
    # Try first 300 chars where name usually appears
    doc = nlp(text[:300])
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text.strip()
    # Fallback: first non-empty line
    for line in text.split("\n"):
        line = line.strip()
        if line and len(line.split()) <= 5 and not any(c.isdigit() for c in line):
            return line
    return "Unknown"


# ── Q&A PAIR GENERATOR (for T5 training) ─────────────────────────────────────
def generate_qa_pairs(parsed: dict) -> list:
    """Generate question-context-answer triples from parsed resume data."""
    pairs = []
    name    = parsed["name"]
    skills  = ", ".join(parsed["skills"][:5]) if parsed["skills"] else "various technologies"
    domain  = parsed["domain"].replace("_", " ")
    exp     = parsed["years_exp"]
    edu     = parsed["sections"].get("education", "").strip()[:200]
    proj    = parsed["sections"].get("projects", "").strip()[:300]
    summary = parsed["sections"].get("summary",  "").strip()[:200]

    # Introduction questions
    pairs += [
        {"context": summary,  "question": f"Tell me about yourself and your background in {domain}.",   "answer": summary},
        {"context": summary,  "question": "Why are you interested in this role?",                        "answer": summary},
        {"context": exp,      "question": f"You have {exp} of experience. Walk me through your journey.", "answer": exp},
    ]

    # Skill-based questions
    for skill in parsed["skills"][:4]:
        pairs.append({
            "context":  f"Skills: {skills}",
            "question": f"How have you used {skill} in your work or projects?",
            "answer":   f"Candidate has experience with {skill}"
        })

    # Project questions
    if proj:
        pairs += [
            {"context": proj, "question": "Describe your most challenging project and how you handled it.", "answer": proj},
            {"context": proj, "question": "What was your role and contribution in your key projects?",      "answer": proj},
        ]

    # Education questions
    if edu:
        pairs.append({"context": edu, "question": "Tell me about your educational background.", "answer": edu})

    # Behavioral questions
    pairs += [
        {"context": summary, "question": "Describe a time you solved a complex problem.",           "answer": ""},
        {"context": summary, "question": "How do you handle tight deadlines and pressure?",          "answer": ""},
        {"context": summary, "question": "Tell me about a time you worked in a team.",               "answer": ""},
        {"context": summary, "question": "Where do you see yourself in 5 years?",                   "answer": ""},
        {"context": skills,  "question": f"What is your strongest skill among {skills}? Explain why.", "answer": ""},
    ]

    return pairs


# ── MAIN PIPELINE ─────────────────────────────────────────────────────────────
def main():
    print("🔄 Loading spaCy model...")
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        print("❌ spaCy model not found. Run: python -m spacy download en_core_web_sm")
        return

    pdf_files = list(RESUMES_DIR.glob("*.pdf"))
    print(f"\n📄 Found {len(pdf_files)} resume PDFs in {RESUMES_DIR}\n")

    if not pdf_files:
        print("❌ No PDFs found! Place your resume PDFs in data/resumes/")
        return

    all_parsed  = []
    all_qa      = []

    for pdf_path in tqdm(pdf_files, desc="Processing PDFs"):
        text = extract_text(str(pdf_path))
        if not text or len(text) < 100:
            continue

        sections = split_sections(text)
        skills   = extract_skills(text)
        domain   = classify_domain(text)
        years    = extract_years(text)
        name     = extract_name(text, nlp)

        parsed = {
            "file":     pdf_path.name,
            "name":     name,
            "domain":   domain,
            "skills":   skills,
            "years_exp": years,
            "sections": sections,
            "full_text": text[:5000],   # keep first 5000 chars
        }

        qa_pairs = generate_qa_pairs(parsed)

        all_parsed.append(parsed)
        all_qa.extend(qa_pairs)

    # Save outputs
    parsed_path = OUTPUT_DIR / "parsed_resumes.json"
    qa_path     = OUTPUT_DIR / "qa_pairs.json"

    with open(parsed_path, "w", encoding="utf-8") as f:
        json.dump(all_parsed, f, indent=2, ensure_ascii=False)

    with open(qa_path, "w", encoding="utf-8") as f:
        json.dump(all_qa, f, indent=2, ensure_ascii=False)

    print(f"""
╔══════════════════════════════════════════════════════════╗
║              ✅ DATA PREPARATION DONE!                   ║
╠══════════════════════════════════════════════════════════╣
║  Resumes processed : {len(all_parsed):<35}║
║  QA pairs created  : {len(all_qa):<35}║
║  Saved to          : data/processed/                     ║
╚══════════════════════════════════════════════════════════╝

Next → Run: python backend/train/train_bert.py
""")


if __name__ == "__main__":
    main()