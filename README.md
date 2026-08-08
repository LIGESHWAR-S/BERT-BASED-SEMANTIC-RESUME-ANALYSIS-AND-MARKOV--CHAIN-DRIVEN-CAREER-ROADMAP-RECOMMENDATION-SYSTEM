# BERT-Based Resume Analyzer & Markov Chain Career Prediction System

This is a premium, full-stack Django application that implements a natural language pipeline to parse candidate resumes (PDF, DOCX, TXT), compute semantic similarity against job requirements using Sentence-BERT (`all-MiniLM-L6-v2`), extract and normalize technical/soft skills, run detailed skill-gap calculations, and recommend career roadmap progressions utilizing a Markov Chain stochastic transition model.

---

## 🚀 Key Features

1. **Robust Document Parsing**: Text extraction using PyMuPDF (`fitz`), python-docx, and custom regex segmentation to isolate contact, summaries, education, experience, and skills.
2. **Skill Normalization Engine**: Scans text for skills and maps synonyms/aliases to a standardized database catalog (e.g. "MS Excel" & "Excel" map to "Microsoft Excel").
3. **BERT Semantic Matcher**: Compares complete candidate profiles and specific sections (e.g. Projects) against job descriptions using dense vector representations and cosine similarity.
4. **Scoring Breakdown**: Provides clear scorecards spanning Semantic Match, Technical Skills, Years of Experience, Education Degrees, and Project Relevance.
5. **Skill Gap Analysis**: Classifies target skills into Matched, Missing, and Recommended with Critical, High, Medium, or Low priority tags.
6. **Markov Chain Progression Model**: Utilizes stochastic transition counts from historical career pathways to predict the most probable sequence of future roles:
   $$\text{Current State} \to \text{Next State} \to \text{Future State} \to \text{Advanced State}$$
7. **Hybrid Interface**: Serves both a visual HTML5/Tailwind CSS v4 user dashboard (complete with Chart.js radar and bar graphs) and RESTful API endpoints.

---

## 🛠️ Technology Stack

* **Backend**: Python 3.11+, Django 5.0+, Django REST Framework
* **AI/NLP**: PyTorch, Sentence-Transformers (BERT), spaCy, scikit-learn, NumPy, Pandas, NLTK
* **File Extractors**: PyMuPDF (`fitz`), python-docx
* **Frontend**: HTML5, Django Templates, Tailwind CSS v4 (via CDN), Chart.js
* **Database**: SQLite3 (development) / PostgreSQL-ready (production)

---

## 📈 Formulations & Calculations

### 1. Resume Match Score
$$Score_{Match} = 0.40 \cdot Sim_{Semantic} + 0.30 \cdot Match_{Skill} + 0.10 \cdot Score_{Exp} + 0.10 \cdot Score_{Edu} + 0.10 \cdot Score_{Project}$$
* *Weights are fully configurable in settings.*

### 2. Markov Chain Transitions
Transition probability from state $i$ to state $j$:
$$P(X_{t+1} = j \mid X_t = i) = \frac{\text{Count}(i \to j)}{\sum_{k} \text{Count}(i \to k)}$$

### 3. Career Recommendation Score
Used to rank alternative path selections:
$$Score_{Career} = 0.50 \cdot P(Transition) + 0.30 \cdot Comp_{Skill} + 0.20 \cdot Sim_{Semantic}$$

---

## 📂 Project Directory Structure

```
resume_career_system/
├── data/                      # CSV Datasets
│   ├── skills.csv             # Catalog & aliases
│   ├── job_roles.csv          # Predefined requirements
│   └── career_transitions.csv # Markov frequencies
├── nlp_engine/                # Modular Core NLP Engine
│   ├── parser.py              # Text extraction & sections
│   ├── extractor.py           # Skill extraction & matching
│   ├── embedder.py            # Sentence-BERT singleton
│   └── markov.py              # Markov transition engine
├── accounts/                  # User Authentication app
├── resumes/                   # Resume Management app
├── jobs/                      # Matching & Skill Gaps app
├── career/                    # Markov Roadmaps app
├── templates/                 # Global dashboard templates
├── seed_data.py               # DB pre-population script
├── manage.py
└── requirements.txt           # Python library dependencies
```

---

## ⚙️ Setup and Installation Instructions

### 1. Clone & Initialize Directory
Set this folder as your active terminal path.

### 2. Configure Virtual Environment
Create and activate a python virtual environment:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install Core Libraries
Install dependencies listed in requirements.txt (includes torch and sentence-transformers):
```powershell
pip install -r requirements.txt
```

### 4. Download spaCy Model
```powershell
python -m spacy download en_core_web_sm
```

### 5. Apply Database Migrations
Create the SQLite database and schemas:
```powershell
python manage.py makemigrations accounts resumes jobs career
python manage.py migrate
```

### 6. Pre-populate & Seed Datasets
Import CSV catalogs and pre-calculate predefined SBERT embeddings:
```powershell
python seed_data.py
```

### 7. Create Superuser (Admin Access)
```powershell
python manage.py createsuperuser
```

### 8. Run Development Server
```powershell
python manage.py runserver
```
Visit the local server at `http://127.0.0.1:8000/`.

---

## 🧪 Running Verification Tests

Run the complete automated test suite verifying auth views, text extraction, SBERT cosine similarity, skill normalizations, and Markov roadmap trees:
```powershell
python manage.py test
```

---

## 🔌 API Documentation

* `POST /api/accounts/register/`: Register a new user account.
* `POST /api/resume/upload/`: Upload PDF/DOCX/TXT resume. Returns parsed sections and skills.
* `POST /api/job/analyze/`: Input a custom Job Description. Extracts skills and embeds text.
* `POST /api/match/`: Calculate multi-dimensional score and skill gaps between a resume and job description.
* `GET /api/skills/`: Get list of all cataloged skills.
* `GET /api/skill-gaps/?analysis_id={id}`: Retrieve skill gaps categorized by status and priority.
* `POST /api/career/recommend/`: Compute Markov chain progression recommendations.
* `GET /api/career/roadmap/`: Returns the latest 3-step career progression nodes.
* `GET /api/analysis/{id}/`: Retrieve matching scorecard and NLP explanation block.
