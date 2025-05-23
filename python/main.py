import os
import re
import psycopg2
import fitz  # PyMuPDF
import docx
from uuid import uuid4
from sklearn.metrics import jaccard_score
from sklearn.preprocessing import MultiLabelBinarizer

# Database connection settings (replace with your Azure PostgreSQL settings)
DB_SETTINGS = {
    'host': 'your-db-hostname',
    'dbname': 'your-db-name',
    'user': 'your-db-user',
    'password': 'your-db-password',
    'port': 5432,
}

def extract_text_from_pdf(path):
    """Extract full text from PDF file using PyMuPDF."""
    doc = fitz.open(path)
    text = " ".join([page.get_text() for page in doc])
    doc.close()
    return text

def extract_text_from_docx(path):
    """Extract full text from DOCX file."""
    doc = docx.Document(path)
    return " ".join([para.text for para in doc.paragraphs])

def extract_skills(text):
    """Extract skills using simple keyword-based matching (can be upgraded later)."""
    predefined_skills = ['python', 'java', 'sql', 'html', 'css', 'javascript', 'react', 'nodejs', 'laravel']
    found_skills = []
    for skill in predefined_skills:
        if re.search(r'\b' + re.escape(skill) + r'\b', text, re.IGNORECASE):
            found_skills.append(skill.lower())
    return list(set(found_skills))

def connect_db():
    """Connect to PostgreSQL."""
    return psycopg2.connect(**DB_SETTINGS)

def fetch_job_listings(cursor):
    """Fetch job listings and required skills from the database."""
    cursor.execute("SELECT id, requirements FROM job_listings")
    return cursor.fetchall()

def insert_match_score(cursor, resume_id, job_id, score):
    """Insert match score into the matches table."""
    cursor.execute(
        "INSERT INTO matches (resume_id, job_listing_id, similarity_score) VALUES (%s, %s, %s)",
        (resume_id, job_id, score)
    )

def jaccard_similarity(list1, list2):
    """Compute Jaccard similarity between two skill lists."""
    mlb = MultiLabelBinarizer()
    binary = mlb.fit_transform([list1, list2])
    return jaccard_score(binary[0], binary[1])

def process_resume(file_path):
    """Extract name, id, skills from resume file."""
    ext = os.path.splitext(file_path)[-1].lower()
    if ext == '.pdf':
        text = extract_text_from_pdf(file_path)
    elif ext == '.docx':
        text = extract_text_from_docx(file_path)
    else:
        return None

    resume_id = str(uuid4())
    name_match = re.search(r'(?i)(?:name\s*[:\-]?\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', text)
    name = name_match.group(1).strip() if name_match else "Unknown Name"
    skills = extract_skills(text)
    return resume_id, name, skills

def main(resume_file_path):
    resume_data = process_resume(resume_file_path)
    if not resume_data:
        print("Unsupported file type.")
        return

    resume_id, name, resume_skills = resume_data
    print(f"Parsed: {name} [{resume_id}] with skills: {resume_skills}")

    conn = connect_db()
    cur = conn.cursor()

    # Insert the resume into the database
    cur.execute("INSERT INTO resumes (id, name, skills) VALUES (%s, %s, %s)", (resume_id, name, ','.join(resume_skills)))

    # Compare against all job listings
    for job_id, req in fetch_job_listings(cur):
        required_skills = extract_skills(req)
        score = jaccard_similarity(resume_skills, required_skills)
        insert_match_score(cur, resume_id, job_id, round(score * 100, 2))

    conn.commit()
    cur.close()
    conn.close()
    print("Matching complete and scores inserted.")

# Example usage:
# main("path_to_resume.pdf") or main("path_to_resume.docx")

