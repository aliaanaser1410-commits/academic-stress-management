
import streamlit as st
import pandas as pd
import sqlite3
import json
import os
import fitz
from pathlib import Path
from datetime import date, datetime, timedelta

# =====================================================
# CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="Smart Student Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = Path(__file__).parent / "student_assistant.db"

# =====================================================
# DATABASE
# =====================================================

def db_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    with db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY,
                data TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_date TEXT,
                subject TEXT,
                duration REAL,
                status TEXT DEFAULT 'Pending'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT,
                message TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                subject TEXT,
                content TEXT
            )
        """)


def save_profile(data):
    with db_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO profile (id, data) VALUES (1, ?)",
            (json.dumps(data, ensure_ascii=False),)
        )


def load_profile():
    with db_connection() as conn:
        row = conn.execute(
            "SELECT data FROM profile WHERE id=1"
        ).fetchone()
    return json.loads(row[0]) if row else {}


def save_plan(plan):
    with db_connection() as conn:
        conn.execute("DELETE FROM sessions")
        for item in plan:
            conn.execute("""
                INSERT INTO sessions
                (session_date, subject, duration, status)
                VALUES (?, ?, ?, ?)
            """, (
                item["date"],
                item["subject"],
                item["duration"],
                item.get("status", "Pending")
            ))


def load_plan():
    with db_connection() as conn:
        rows = conn.execute("""
            SELECT session_date, subject, duration, status
            FROM sessions ORDER BY session_date, id
        """).fetchall()

    return [
        {
            "date": r[0],
            "subject": r[1],
            "duration": r[2],
            "status": r[3]
        } for r in rows
    ]


def save_chat(role, message):
    with db_connection() as conn:
        conn.execute("""
            INSERT INTO chat (role, message, created_at)
            VALUES (?, ?, ?)
        """, (role, message, datetime.now().isoformat()))


def load_chat():
    with db_connection() as conn:
        rows = conn.execute("""
            SELECT role, message FROM chat
            ORDER BY id DESC LIMIT 30
        """).fetchall()
    return list(reversed(rows))


def clear_chat():
    with db_connection() as conn:
        conn.execute("DELETE FROM chat")


def save_material(filename, subject, content):
    with db_connection() as conn:
        conn.execute("""
            INSERT INTO materials (filename, subject, content)
            VALUES (?, ?, ?)
        """, (filename, subject, content))


def load_materials():
    with db_connection() as conn:
        return conn.execute("""
            SELECT id, filename, subject, content
            FROM materials ORDER BY id DESC
        """).fetchall()


def delete_material(material_id):
    with db_connection() as conn:
        conn.execute(
            "DELETE FROM materials WHERE id=?",
            (material_id,)
        )


init_db()

# =====================================================
# LANGUAGE
# =====================================================

if "language" not in st.session_state:
    st.session_state.language = "English"

LANG = st.session_state.language
AR = LANG == "Arabic"

TEXT = {
    "home": ("الرئيسية", "Home"),
    "interview": ("تقييم الطالب", "Student Interview"),
    "profile": ("ملفي الشخصي", "My Profile"),
    "materials": ("المحاضرات والملفات", "My Materials"),
    "planner": ("الجدول الأسبوعي", "Weekly Planner"),
    "buddy": ("المساعد الذكي", "Study Buddy"),
    "progress": ("إنجازاتي", "My Progress"),
    "stress": ("إدارة التوتر", "Stress Management"),
    "settings": ("الإعدادات", "Settings"),
    "welcome": ("مرحبًا بك في مساعدك الدراسي الذكي", "Welcome to your Smart Student Assistant"),
    "start": ("ابدأ التقييم", "Start Assessment"),
    "next": ("التالي", "Next"),
    "back": ("السابق", "Back"),
    "generate": ("إنشاء الجدول", "Generate Plan"),
    "save": ("حفظ", "Save"),
    "no_profile": ("ابدأ المقابلة أولًا لتجهيز خطتك.", "Complete the interview first to prepare your plan."),
}


def tr(key):
    return TEXT.get(key, (key, key))[0 if AR else 1]


# =====================================================
# THEME
# =====================================================

if "theme" not in st.session_state:
    st.session_state.theme = "Purple"

if "mode" not in st.session_state:
    st.session_state.mode = "Dark"

THEMES = {
    "Purple": "#8B5CF6",
    "Blue": "#3B82F6",
    "Pink": "#EC4899",
    "Green": "#10B981",
    "Orange": "#F97316",
    "Teal": "#14B8A6",
    "Red": "#EF4444",
    "Indigo": "#6366F1"
}

accent = THEMES[st.session_state.theme]

if st.session_state.mode == "Dark":
    bg = "#10121C"
    panel = "#1B1E2B"
    foreground = "#F4F4F8"
else:
    bg = "#F5F6FA"
    panel = "#FFFFFF"
    foreground = "#202235"

st.markdown(f"""
<style>
.stApp {{
    background-color: {bg};
    color: {foreground};
}}
[data-testid="stSidebar"] {{
    background-color: {panel};
}}
h1, h2, h3, p, label {{
    color: {foreground};
}}
div.stButton > button {{
    background-color: {accent};
    color: white;
    border: none;
    border-radius: 10px;
    padding: 9px 20px;
}}
div.stButton > button:hover {{
    border: 1px solid {accent};
    color: {accent};
}}
[data-testid="stMetric"] {{
    background-color: {panel};
    padding: 16px;
    border-radius: 12px;
}}
.card {{
    background: {panel};
    border-radius: 14px;
    padding: 18px;
    margin-bottom: 12px;
}}
</style>
""", unsafe_allow_html=True)

# =====================================================
# SESSION STATE
# =====================================================

defaults = {
    "page": "Home",
    "interview_step": 0,
    "answers": {},
    "profile": load_profile(),
    "plan": load_plan(),
    "chat_history": load_chat(),
    "pending_plan": [],
    "show_recommendations": False,
    "xp": 0,
    "completed_ids": []
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

profile = st.session_state.profile

# =====================================================
# EXPERT SYSTEM – IF / THEN RULES
# =====================================================

def expert_evaluation(p):
    rules = []

    stress = int(p.get("stress", 5))
    sleep = float(p.get("sleep", 7))
    focus = int(p.get("focus", 5))
    workload = int(p.get("workload", 5))
    days = int(p.get("days_left", 30))

    if stress >= 8:
        rules.append({
            "id": "R01",
            "level": "High",
            "title": "High Stress",
            "reason": "Stress level is 8 or higher.",
            "action": "Reduce today's workload and include relaxation breaks."
        })

    elif stress >= 5:
        rules.append({
            "id": "R02",
            "level": "Medium",
            "title": "Moderate Stress",
            "reason": "Stress level is between 5 and 7.",
            "action": "Use shorter focused sessions and regular breaks."
        })

    if sleep < 5:
        rules.append({
            "id": "R03",
            "level": "High",
            "title": "Insufficient Sleep",
            "reason": "Sleep duration is below 5 hours.",
            "action": "Prioritize sleep and avoid late-night study."
        })

    elif sleep < 7:
        rules.append({
            "id": "R04",
            "level": "Medium",
            "title": "Sleep Needs Improvement",
            "reason": "Sleep duration is below 7 hours.",
            "action": "Try to maintain a consistent sleep routine."
        })

    if focus <= 3:
        rules.append({
            "id": "R05",
            "level": "High",
            "title": "Low Concentration",
            "reason": "Focus score is 3 or lower.",
            "action": "Start with 30-minute sessions and remove distractions."
        })

    if workload >= 8:
        rules.append({
            "id": "R06",
            "level": "High",
            "title": "Heavy Workload",
            "reason": "Workload score is 8 or higher.",
            "action": "Break large tasks into smaller steps."
        })

    if days <= 3:
        rules.append({
            "id": "R07",
            "level": "High",
            "title": "Exam Approaching",
            "reason": "The nearest exam is within 3 days.",
            "action": "Prioritize revision and important topics."
        })

    if not rules:
        rules.append({
            "id": "R00",
            "level": "Positive",
            "title": "Balanced Starting Point",
            "reason": "No high-priority risk rules were activated.",
            "action": "Maintain a balanced study routine."
        })

    return rules


# =====================================================
# STUDY PLANNER
# =====================================================

def make_weekly_plan(p):
    subjects = p.get("subjects", [])
    if not subjects:
        return []

    hours = float(p.get("study_hours", 3))
    if any(r["level"] == "High" for r in expert_evaluation(p)):
        hours = min(hours, 4)

    hours = max(0.5, min(hours, 12))

    subjects = [dict(s) for s in subjects]
    for s in subjects:
        s["scheduled"] = 0

    plan = []
    last_day = {}

    lengths = [2, 1.5, 1, 0.5]

    for day_index in range(7):
        current = date.today() + timedelta(days=day_index)
        remaining = hours
        used = set()
        daily_count = 0

        while remaining >= 0.5 and daily_count < 3:
            candidates = [s for s in subjects if s["name"] not in used]
            if not candidates:
                break

            def score(s):
                difficulty = int(s.get("difficulty", 3))
                priority = int(s.get("priority", 3))
                exam_days = int(s.get("exam_days", 30))
                urgency = max(0, 30 - exam_days)
                recent = day_index - last_day.get(s["name"], -10)

                return (
                    difficulty * 2
                    + priority * 2
                    + urgency / 10
                    + min(recent, 5) * 0.8
                    - s["scheduled"] * 0.15
                )

            chosen = max(candidates, key=score)
            duration = next(
                (x for x in lengths if x <= remaining + 0.0001),
                0
            )

            if not duration:
                break

            plan.append({
                "date": current.isoformat(),
                "day": current.strftime("%A"),
                "subject": chosen["name"],
                "duration": duration,
                "status": "Pending"
            })

            chosen["scheduled"] += duration
            used.add(chosen["name"])
            last_day[chosen["name"]] = day_index
            remaining -= duration
            daily_count += 1

    return plan


# =====================================================
# PDF MATERIAL EXTRACTION
# =====================================================

def extract_pdf(uploaded_file):
    try:
        document = fitz.open(
            stream=uploaded_file.getvalue(),
            filetype="pdf"
        )
        pages = []

        for page in document:
            pages.append(page.get_text())

        return "\n".join(pages).strip()

    except Exception as error:
        st.error(f"PDF extraction error: {error}")
        return ""


# =====================================================
# AI STUDY BUDDY
# =====================================================

def get_ai_response(question):
    try:
        from openai import OpenAI

        api_key = st.secrets.get("OPENAI_API_KEY", "")

        if not api_key:
            return (
                "AI API key is missing. Add OPENAI_API_KEY "
                "in Streamlit Cloud Secrets."
            )

        client = OpenAI(api_key=api_key)

        language = "Arabic" if AR else "English"

        student_context = json.dumps(
            profile,
            ensure_ascii=False
        )

        materials = load_materials()
        material_context = "\n\n".join(
            f"File: {m[1]}\nSubject: {m[2]}\nContent:\n{m[3][:5000]}"
            for m in materials
        )

        messages = [
            {
                "role": "system",
                "content": f"""
You are Study Buddy, a friendly academic assistant.

Respond in {language}.
Help with studying, time management, revision and student wellbeing.
Use the student's profile when relevant.
Use uploaded materials when answering questions about their lectures.
Never invent facts from uploaded materials.
If the uploaded files do not contain the answer, say so clearly.
Give clear, practical and encouraging answers.

Student profile:
{student_context}

Uploaded study materials:
{material_context}
"""
            }
        ]

        for role, content in st.session_state.chat_history[-12:]:
            if role in ("user", "assistant"):
                messages.append({
                    "role": role,
                    "content": content
                })

        messages.append({
            "role": "user",
            "content": question
        })

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.5
        )

        return response.choices[0].message.content

    except Exception as error:
        return f"AI connection error: {error}"


# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:
    st.markdown("# 🎓 Smart Student")
    st.caption("Your Academic Companion")

    st.divider()

    st.markdown("### 🌐 Language")

    language_choice = st.selectbox(
        "Language",
        ["English", "Arabic"],
        index=0 if LANG == "English" else 1
    )

    if language_choice != LANG:
        st.session_state.language = language_choice
        st.rerun()

    st.divider()

    pages = [
        ("Home", tr("home")),
        ("Student Interview", tr("interview")),
        ("My Profile", tr("profile")),
        ("My Materials", tr("materials")),
        ("Weekly Planner", tr("planner")),
        ("Study Buddy", tr("buddy")),
        ("My Progress", tr("progress")),
        ("Stress Management", tr("stress")),
        ("Settings", tr("settings"))
    ]

    for page_id, label in pages:
        if st.button(label, key=f"nav_{page_id}", use_container_width=True):
            st.session_state.page = page_id
            st.rerun()

    st.divider()
    st.caption("🤖 Study Buddy is available in the sidebar.")

    if st.session_state.profile:
        st.success("Student profile ready")
    else:
        st.info("Complete your student interview")


# =====================================================
# HOME
# =====================================================

page = st.session_state.page

if page == "Home":
    st.title(tr("welcome"))
    st.write(
        "A personal system to organize your studies, "
        "understand your academic needs and manage stress."
        if not AR else
        "نظامك الشخصي لتنظيم المذاكرة وفهم احتياجاتك الدراسية وإدارة التوتر."
    )

    if not profile:
        st.info(tr("no_profile"))

        if st.button(tr("start"), type="primary"):
            st.session_state.page = "Student Interview"
            st.rerun()

    else:
        col1, col2, col3 = st.columns(3)

        col1.metric(
            "📚 Subjects" if not AR else "📚 المواد",
            len(profile.get("subjects", []))
        )

        col2.metric(
            "⏰ Daily Study Hours" if not AR else "⏰ ساعات المذاكرة",
            profile.get("study_hours", 0)
        )

        col3.metric(
            "📅 Days to Exam" if not AR else "📅 أيام للامتحان",
            profile.get("days_left", 0)
        )

        st.subheader(
            "Quick Actions" if not AR else "إجراءات سريعة"
        )

        a, b, c = st.columns(3)

        if a.button("📅 Weekly Planner", use_container_width=True):
            st.session_state.page = "Weekly Planner"
            st.rerun()

        if b.button("🤖 Study Buddy", use_container_width=True):
            st.session_state.page = "Study Buddy"
            st.rerun()

        if c.button("📂 My Materials", use_container_width=True):
            st.session_state.page = "My Materials"
            st.rerun()

        completed = sum(
            s["status"] == "Completed"
            for s in st.session_state.plan
        )
        total = len(st.session_state.plan)

        st.subheader(
            "Your Progress" if not AR else "تقدمك"
        )

        st.progress(completed / total if total else 0)

        st.write(f"{completed} / {total} sessions completed")

        if not st.session_state.plan:
            if st.button(
                "Create your study plan" if not AR else "إنشاء جدول المذاكرة"
            ):
                st.session_state.page = "Weekly Planner"
                st.rerun()


# =====================================================
# INTERACTIVE STUDENT INTERVIEW
# =====================================================

elif page == "Student Interview":
    st.title(
        "Student Assessment Interview"
        if not AR else
        "مقابلة تقييم الطالب"
    )

    questions = [
        {
            "key": "name",
            "question": "What is your name?" if not AR else "ما اسمك؟",
            "type": "text"
        },
        {
            "key": "year",
            "question": "Which academic year are you in?" if not AR else "في أي سنة دراسية أنت؟",
            "type": "select",
            "options": ["First", "Second", "Third", "Fourth", "Other"]
        },
        {
            "key": "days_left",
            "question": "How many days until your nearest exam?" if not AR else "كم يوم متبقي على أقرب امتحان؟",
            "type": "number"
        },
        {
            "key": "study_hours",
            "question": "How many hours can you study daily?" if not AR else "كم ساعة تستطيع المذاكرة يوميًا؟",
            "type": "number"
        },
        {
            "key": "subjects_text",
            "question": "Enter your subjects separated by commas." if not AR else "اكتب أسماء المواد وافصل بينها بفواصل.",
            "type": "text"
        },
        {
            "key": "hardest_subject",
            "question": "Which subject is the hardest for you?" if not AR else "ما أصعب مادة بالنسبة لك؟",
            "type": "text"
        },
        {
            "key": "study_time",
            "question": "When do you prefer studying?" if not AR else "متى تفضل المذاكرة؟",
            "type": "select",
            "options": ["Morning", "Afternoon", "Evening", "Night"]
        },
        {
            "key": "stress",
            "question": "How stressed do you feel? (0–10)" if not AR else "ما مستوى التوتر لديك؟ (من 0 إلى 10)",
            "type": "slider"
        },
        {
            "key": "sleep",
            "question": "How many hours do you sleep?" if not AR else "كم ساعة تنام يوميًا؟",
            "type": "number"
        },
        {
            "key": "focus",
            "question": "How is your concentration? (0–10)" if not AR else "ما مستوى تركيزك؟ (من 0 إلى 10)",
            "type": "slider"
        },
        {
            "key": "workload",
            "question": "How heavy is your workload? (0–10)" if not AR else "ما حجم ضغط الدراسة لديك؟ (من 0 إلى 10)",
            "type": "slider"
        },
        {
            "key": "problem",
            "question": "What is your biggest study problem?" if not AR else "ما أكبر مشكلة تواجهك في المذاكرة؟",
            "type": "text"
        }
    ]

    if "interview_answers" not in st.session_state:
        st.session_state.interview_answers = {}

    answers = st.session_state.interview_answers
    step = st.session_state.interview_step

    total_questions = len(questions)

    if step < total_questions:
        q = questions[step]

        st.progress((step + 1) / total_questions)
        st.caption(f"Question {step + 1} / {total_questions}")

        st.subheader(q["question"])

        key = q["key"]

        if q["type"] == "text":
            value = st.text_input(
                "Your answer" if not AR else "إجابتك",
                value=answers.get(key, ""),
                key=f"answer_{key}"
            )

        elif q["type"] == "number":
            default = answers.get(
                key,
                3 if key == "study_hours" else
                7 if key == "sleep" else 7
            )
            value = st.number_input(
                "Your answer" if not AR else "إجابتك",
                min_value=0,
                max_value=24 if key in ("study_hours", "sleep") else 365,
                value=int(default),
                key=f"answer_{key}"
            )

        elif q["type"] == "slider":
            value = st.slider(
                "Choose a value" if not AR else "اختر قيمة",
                0, 10,
                int(answers.get(key, 5)),
                key=f"answer_{key}"
            )

        else:
            value = st.selectbox(
                "Choose" if not AR else "اختر",
                q["options"],
                index=q["options"].index(
                    answers.get(key, q["options"][0])
                ) if answers.get(key) in q["options"] else 0,
                key=f"answer_{key}"
            )

        col1, col2 = st.columns(2)

        with col1:
            if step > 0 and st.button(tr("back")):
                st.session_state.interview_step -= 1
                st.rerun()

        with col2:
            if st.button(tr("next"), type="primary"):
                if q["type"] == "text" and not value.strip():
                    st.warning(
                        "Please enter an answer."
                        if not AR else
                        "من فضلك أدخل إجابة."
                    )
                else:
                    answers[key] = value
                    st.session_state.interview_answers = answers
                    st.session_state.interview_step += 1
                    st.rerun()

    else:
        st.success(
            "Interview completed!" if not AR else "اكتملت المقابلة!"
        )

        if st.button(
            "Analyze my answers" if not AR else "حلل إجاباتي",
            type="primary"
        ):
            raw_subjects = answers.get("subjects_text", "")
            subject_names = [
                x.strip() for x in raw_subjects.split(",")
                if x.strip()
            ]

            subjects = []

            for name in subject_names:
                subjects.append({
                    "name": name,
                    "difficulty": 5 if name == answers.get("hardest_subject") else 3,
                    "priority": 5 if name == answers.get("hardest_subject") else 3,
                    "exam_days": int(answers.get("days_left", 30))
                })

            new_profile = {
                "name": answers.get("name", ""),
                "year": answers.get("year", ""),
                "days_left": int(answers.get("days_left", 7)),
                "study_hours": float(answers.get("study_hours", 3)),
                "subjects": subjects,
                "hardest_subject": answers.get("hardest_subject", ""),
                "study_time": answers.get("study_time", ""),
                "stress": int(answers.get("stress", 5)),
                "sleep": float(answers.get("sleep", 7)),
                "focus": int(answers.get("focus", 5)),
                "workload": int(answers.get("workload", 5)),
                "problem": answers.get("problem", "")
            }

            st.session_state.profile = new_profile
            save_profile(new_profile)
            st.session_state.show_recommendations = True
            st.rerun()

    if st.session_state.show_recommendations and profile:
        st.divider()

        st.subheader(
            "Expert System Analysis" if not AR else "تحليل النظام الخبير"
        )

        for rule in expert_evaluation(profile):
            st.markdown(f"""
            <div class="card">
                <b>{rule['id']} – {rule['title']}</b><br>
                {rule['reason']}<br>
                <b>Recommendation:</b> {rule['action']}
            </div>
            """, unsafe_allow_html=True)

        st.warning(
            "Review your answers before creating your plan."
            if not AR else
            "راجِع إجاباتك قبل إنشاء الجدول."
        )

        if st.button(
            "Approve and create my plan" if not AR else "موافق، أنشئ جدولي",
            type="primary"
        ):
            st.session_state.plan = make_weekly_plan(profile)
            save_plan(st.session_state.plan)
            st.session_state.page = "Weekly Planner"
            st.rerun()


# =====================================================
# STUDENT PROFILE
# =====================================================

elif page == "My Profile":
    st.title(tr("profile"))

    if not profile:
        st.info(tr("no_profile"))
        if st.button(tr("start")):
            st.session_state.page = "Student Interview"
            st.rerun()
    else:
        st.write("###", profile.get("name", "Student"))

        st.write("Academic year:", profile.get("year"))
        st.write("Study hours:", profile.get("study_hours"))
        st.write("Nearest exam:", profile.get("days_left"), "days")

        st.subheader("Subjects")

        for subject in profile.get("subjects", []):
            st.write(
                f"📘 {subject['name']} – "
                f"Difficulty: {subject['difficulty']}/5"
            )

        if st.button("Retake interview"):
            st.session_state.interview_step = 0
            st.session_state.interview_answers = {}
            st.session_state.show_recommendations = False
            st.session_state.page = "Student Interview"
            st.rerun()


# =====================================================
# MY MATERIALS
# =====================================================

elif page == "My Materials":
    st.title(tr("materials"))

    st.write(
        "Upload PDF lectures. Extracted text can be used by Study Buddy."
        if not AR else
        "ارفعي ملفات المحاضرات PDF ليتم استخراج النص واستخدامه بواسطة المساعد الذكي."
    )

    uploaded_files = st.file_uploader(
        "Upload PDF files",
        type=["pdf"],
        accept_multiple_files=True
    )

    if uploaded_files:
        for file in uploaded_files:
            subject = st.text_input(
                f"Subject for {file.name}",
                key=f"subject_{file.name}"
            )

            if st.button(
                f"Analyze and save {file.name}",
                key=f"save_{file.name}"
            ):
                content = extract_pdf(file)

                if content:
                    save_material(file.name, subject or "General", content)
                    st.success("File extracted and saved.")
                else:
                    st.warning(
                        "No readable text found. Scanned PDF OCR is not included yet."
                    )

    st.divider()
    st.subheader("Saved Materials")

    materials = load_materials()

    if not materials:
        st.info("No materials uploaded yet.")
    else:
        for material in materials:
            with st.expander(f"📄 {material[1]} – {material[2]}"):
                st.write(material[3][:3000] or "No text extracted.")

                if st.button(
                    "Delete",
                    key=f"delete_material_{material[0]}"
                ):
                    delete_material(material[0])
                    st.rerun()


# =====================================================
# WEEKLY PLANNER
# =====================================================

elif page == "Weekly Planner":
    st.title(tr("planner"))

    if not profile:
        st.info(tr("no_profile"))
    else:
        if st.button(
            "Generate / Refresh Weekly Plan"
            if not AR else
            "إنشاء / تحديث الجدول الأسبوعي",
            type="primary"
        ):
            st.session_state.plan = make_weekly_plan(profile)
            save_plan(st.session_state.plan)
            st.rerun()

        plan = st.session_state.plan

        if plan:
            total_hours = sum(x["duration"] for x in plan)
            completed = sum(
                x["status"] == "Completed" for x in plan
            )

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Hours", total_hours)
            c2.metric("Sessions", len(plan))
            c3.metric("Completed", completed)

            st.progress(
                completed / len(plan) if plan else 0
            )

            for offset in range(7):
                day_date = date.today() + timedelta(days=offset)
                day_sessions = [
                    (i, s) for i, s in enumerate(plan)
                    if s["date"] == day_date.isoformat()
                ]

                with st.expander(
                    f"📅 {day_date.strftime('%A – %d %B')} "
                    f"({len(day_sessions)} sessions)",
                    expanded=(offset == 0)
                ):
                    if not day_sessions:
                        st.write("No sessions scheduled.")

                    for index, session in day_sessions:
                        col1, col2 = st.columns([3, 1])

                        col1.write(
                            f"📘 **{session['subject']}** – "
                            f"{session['duration']} hours"
                        )

                        if session["status"] == "Completed":
                            col2.success("Completed")
                        else:
                            if col2.button(
                                "Complete",
                                key=f"complete_{index}"
                            ):
                                st.session_state.plan[index]["status"] = "Completed"
                                st.session_state.xp += 10
                                save_plan(st.session_state.plan)
                                st.rerun()

            st.divider()

            if st.button(
                "Reschedule pending sessions"
                if not AR else
                "إعادة جدولة الجلسات المتبقية"
            ):
                today = date.today()
                pending = [
                    s for s in plan
                    if s["status"] != "Completed"
                    and date.fromisoformat(s["date"]) >= today
                ]

                completed_sessions = [
                    s for s in plan
                    if s["status"] == "Completed"
                    or date.fromisoformat(s["date"]) < today
                ]

                occupied = {}
                for s in completed_sessions:
                    occupied[s["date"]] = occupied.get(s["date"], 0) + 1

                new_sessions = []
                overflow = []

                for session in pending:
                    placed = False

                    for day_offset in range(14):
                        target = today + timedelta(days=day_offset)
                        target_str = target.isoformat()

                        if occupied.get(target_str, 0) < 3:
                            updated = dict(session)
                            updated["date"] = target_str
                            updated["day"] = target.strftime("%A")
                            new_sessions.append(updated)
                            occupied[target_str] = occupied.get(target_str, 0) + 1
                            placed = True
                            break

                    if not placed:
                        overflow.append(session)

                st.session_state.plan = completed_sessions + new_sessions
                save_plan(st.session_state.plan)

                st.success("Pending sessions rescheduled.")
                if overflow:
                    st.warning(
                        f"{len(overflow)} sessions could not be scheduled."
                    )

                st.rerun()

        else:
            st.info("Your plan has not been created yet.")


# =====================================================
# STUDY BUDDY CHAT
# =====================================================

elif page == "Study Buddy":
    st.title("🤖 Study Buddy")
    st.caption(
        "Your AI academic companion."
        if not AR else
        "مساعدك الذكي في المذاكرة."
    )

    for role, message in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(message)

    question = st.chat_input(
        "Ask me about your studies..."
        if not AR else
        "اسألني عن المذاكرة..."
    )

    if question:
        st.session_state.chat_history.append(
            ("user", question)
        )
        save_chat("user", question)

        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Study Buddy is thinking..."):
                answer = get_ai_response(question)
                st.markdown(answer)

        st.session_state.chat_history.append(
            ("assistant", answer)
        )
        save_chat("assistant", answer)

    if st.button("Clear Chat"):
        clear_chat()
        st.session_state.chat_history = []
        st.rerun()


# =====================================================
# MY PROGRESS
# =====================================================

elif page == "My Progress":
    st.title(tr("progress"))

    plan = st.session_state.plan

    if not plan:
        st.info("Create your weekly plan to track progress.")
    else:
        completed = [
            s for s in plan if s["status"] == "Completed"
        ]

        pending = len(plan) - len(completed)
        completed_hours = sum(
            s["duration"] for s in completed
        )

        c1, c2, c3 = st.columns(3)

        c1.metric("Completed Sessions", len(completed))
        c2.metric("Remaining Sessions", pending)
        c3.metric("Completed Hours", completed_hours)

        st.progress(len(completed) / len(plan))

        st.subheader("Subject Progress")

        progress_data = {}

        for session in plan:
            subject = session["subject"]
            if subject not in progress_data:
                progress_data[subject] = {
                    "Completed": 0,
                    "Total": 0
                }

            progress_data[subject]["Total"] += session["duration"]

            if session["status"] == "Completed":
                progress_data[subject]["Completed"] += session["duration"]

        for subject, values in progress_data.items():
            percentage = (
                values["Completed"] / values["Total"]
                if values["Total"] else 0
            )

            st.write(f"**{subject}**")
            st.progress(percentage)
            st.caption(
                f"{values['Completed']} / {values['Total']} hours"
            )

        st.subheader("Study Level")

        xp = st.session_state.xp

        if xp < 50:
            level = "🐣 Beginner"
        elif xp < 150:
            level = "🐥 Focused Learner"
        elif xp < 300:
            level = "🦉 Study Champion"
        else:
            level = "🦅 Study Master"

        st.metric("Your Level", level)
        st.metric("XP", xp)


# =====================================================
# STRESS MANAGEMENT
# =====================================================

elif page == "Stress Management":
    st.title(tr("stress"))

    if not profile:
        st.info(tr("no_profile"))
    else:
        rules = expert_evaluation(profile)

        st.subheader("Your Assessment")

        st.metric(
            "Stress Level",
            f"{profile.get('stress', 0)}/10"
        )

        st.metric(
            "Sleep Hours",
            profile.get("sleep", 0)
        )

        st.metric(
            "Focus",
            f"{profile.get('focus', 0)}/10"
        )

        st.subheader("Recommendations")

        for rule in rules:
            st.markdown(f"""
            <div class="card">
                <b>{rule['title']}</b><br>
                {rule['action']}
            </div>
            """, unsafe_allow_html=True)

        st.info(
            "Remember: short breaks, adequate sleep, and realistic goals can help."
            if not AR else
            "تذكّر: الفواصل القصيرة والنوم الكافي والأهداف الواقعية قد تساعدك."
        )


# =====================================================
# SETTINGS
# =====================================================

elif page == "Settings":
    st.title(tr("settings"))

    st.subheader("Appearance")

    theme = st.selectbox(
        "Accent Color",
        list(THEMES.keys()),
        index=list(THEMES.keys()).index(st.session_state.theme)
    )

    mode = st.radio(
        "Display Mode",
        ["Dark", "Light"],
        horizontal=True,
        index=0 if st.session_state.mode == "Dark" else 1
    )

    if st.button("Save Settings"):
        st.session_state.theme = theme
        st.session_state.mode = mode
        st.success("Settings updated. Refresh the app to apply all changes.")
        st.rerun()

    st.divider()

    st.subheader("AI Connection")

    if st.secrets.get("OPENAI_API_KEY", ""):
        st.success("AI API key is configured.")
    else:
        st.warning("AI API key has not been configured yet.")


# =====================================================
# FOOTER
# =====================================================

st.divider()

st.caption(
    "Smart Student Assistant | Academic & Stress Management Expert System"
)
