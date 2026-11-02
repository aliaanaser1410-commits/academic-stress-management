

import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import math
import re
from datetime import date, datetime, timedelta

try:
    import fitz
except ImportError:
    fitz = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# =====================================================
# 1. CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="Smart Student Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = "student_assistant.db"

DAYS = [
    "Saturday", "Sunday", "Monday", "Tuesday",
    "Wednesday", "Thursday", "Friday"
]


# =====================================================
# 2. DATABASE CONNECTION
# =====================================================

def db_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def execute(query, params=()):
    with db_connection() as conn:
        conn.execute(query, params)


def fetch_one(query, params=()):
    with db_connection() as conn:
        return conn.execute(query, params).fetchone()


def fetch_all(query, params=()):
    with db_connection() as conn:
        return conn.execute(query, params).fetchall()


# =====================================================
# 3. SAFE DATABASE INITIALIZATION & MIGRATION
# =====================================================

def initialize_database():

    with db_connection() as conn:

        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY,
                name TEXT DEFAULT '',
                college TEXT DEFAULT '',
                major TEXT DEFAULT '',
                year TEXT DEFAULT '',
                daily_hours REAL DEFAULT 4
            )
        """)

        cur.execute("""
            INSERT OR IGNORE INTO profile(id)
            VALUES(1)
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                difficulty TEXT,
                priority TEXT,
                exam_date TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                subject TEXT,
                content TEXT,
                created TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS timetable (
                id INTEGER PRIMARY KEY,
                content TEXT,
                confirmed INTEGER DEFAULT 0
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS xp (
                event TEXT PRIMARY KEY,
                points INTEGER
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS stress_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created TEXT,
                score REAL,
                stress INTEGER,
                sleep REAL,
                focus INTEGER,
                workload INTEGER
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                language TEXT DEFAULT 'English',
                theme TEXT DEFAULT 'Dark'
            )
        """)

        cur.execute("""
            INSERT OR IGNORE INTO settings(id)
            VALUES(1)
        """)

        # Repair old sessions tables without deleting existing data.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT,
                session_date TEXT,
                start_time TEXT,
                subject TEXT,
                duration REAL DEFAULT 0.5,
                status TEXT DEFAULT 'Pending'
            )
        """)

        cur.execute("PRAGMA table_info(sessions)")
        columns = {
            row[1] for row in cur.fetchall()
        }

        required_columns = {
            "id": "INTEGER",
            "day": "TEXT",
            "session_date": "TEXT",
            "start_time": "TEXT",
            "subject": "TEXT",
            "duration": "REAL DEFAULT 0.5",
            "status": "TEXT DEFAULT 'Pending'"
        }

        for column, column_type in required_columns.items():

            if column not in columns:
                cur.execute(
                    f"ALTER TABLE sessions ADD COLUMN "
                    f"{column} {column_type}"
                )

        # Fill IDs for old databases where id was absent or empty.
        cur.execute("""
            UPDATE sessions
            SET id = rowid
            WHERE id IS NULL
        """)

        # Recover values from common legacy column names.
        cur.execute("PRAGMA table_info(sessions)")
        columns = {
            row[1] for row in cur.fetchall()
        }

        legacy_mappings = {
            "day": ["weekday", "study_day"],
            "session_date": ["date", "study_date"],
            "start_time": ["start", "time", "start_at"],
            "subject": ["subject_name", "course"],
            "duration": ["hours", "duration_hours"],
            "status": ["state"]
        }

        for target, alternatives in legacy_mappings.items():

            for old_column in alternatives:

                if old_column in columns:

                    cur.execute(
                        f"""
                        UPDATE sessions
                        SET {target} = {old_column}
                        WHERE {target} IS NULL
                        """
                    )

        conn.commit()


initialize_database()


# =====================================================
# 4. SESSION STATE
# =====================================================

defaults = {
    "page": "Home",
    "chat_history": []
}

for key, value in defaults.items():

    if key not in st.session_state:
        st.session_state[key] = value


# =====================================================
# 5. SETTINGS & LANGUAGE
# =====================================================

def get_settings():

    row = fetch_one("""
        SELECT language, theme
        FROM settings
        WHERE id=1
    """)

    return row or ("English", "Dark")


LANGUAGE, THEME = get_settings()

ARABIC = LANGUAGE == "العربية"
DARK = THEME == "Dark"


def t(en, ar):
    return ar if ARABIC else en


# =====================================================
# 6. PROFILE & DATA HELPERS
# =====================================================

def get_profile():

    row = fetch_one("""
        SELECT name, college, major, year, daily_hours
        FROM profile
        WHERE id=1
    """)

    if not row:
        return {
            "name": "",
            "college": "",
            "major": "",
            "year": "",
            "daily_hours": 4
        }

    return {
        "name": row[0] or "",
        "college": row[1] or "",
        "major": row[2] or "",
        "year": row[3] or "",
        "daily_hours": row[4] or 4
    }


def get_subjects():

    rows = fetch_all("""
        SELECT id, name, difficulty, priority, exam_date
        FROM subjects
        ORDER BY id
    """)

    return pd.DataFrame(
        rows,
        columns=[
            "ID", "Subject", "Difficulty",
            "Priority", "Exam Date"
        ]
    )


def get_sessions():

    rows = fetch_all("""
        SELECT id, day, session_date, start_time,
               subject, duration, status
        FROM sessions
        ORDER BY session_date, start_time
    """)

    return pd.DataFrame(
        rows,
        columns=[
            "ID", "Day", "Date", "Start",
            "Subject", "Hours", "Status"
        ]
    )


def get_materials():

    return fetch_all("""
        SELECT id, filename, subject, content, created
        FROM materials
        ORDER BY id DESC
    """)


# =====================================================
# 7. XP SYSTEM
# =====================================================

def add_xp(event, points=20):

    execute("""
        INSERT OR IGNORE INTO xp(event, points)
        VALUES(?, ?)
    """, (event, points))


def get_xp():

    row = fetch_one("""
        SELECT COALESCE(SUM(points), 0)
        FROM xp
    """)

    return int(row[0]) if row else 0


def get_level(points):

    levels = [
        (0, "Beginner", "🐣"),
        (100, "Focused Learner", "🐥"),
        (300, "Study Champion", "🦉"),
        (600, "Study Master", "🦅")
    ]

    current = levels[0]

    for level in levels:
        if points >= level[0]:
            current = level

    next_level = next(
        (item for item in levels if item[0] > points),
        None
    )

    return current, next_level


# =====================================================
# 8. DESIGN
# =====================================================

BG = "#101827" if DARK else "#F3F6FC"
PANEL = "#1B293B" if DARK else "#FFFFFF"
FG = "#F4F6FC" if DARK else "#172033"
MUTED = "#AAB7C8" if DARK else "#68758A"

st.markdown(f"""
<style>

.stApp {{
    background: {BG};
    color: {FG};
}}

[data-testid="stSidebar"] {{
    background: {PANEL};
}}

.block-container {{
    max-width: 1450px;
    padding-top: 1.5rem;
}}

h1, h2, h3, h4, p, label {{
    color: {FG};
}}

.hero {{
    background: linear-gradient(120deg, #253A70, #7057C8);
    padding: 30px;
    border-radius: 22px;
    margin-bottom: 22px;
    color: white;
}}

.hero h1, .hero p {{
    color: white !important;
}}

.robot-card {{
    background: linear-gradient(130deg, #30245F, #6554B8);
    padding: 16px;
    border-radius: 18px;
    margin-bottom: 15px;
    color: white;
}}

.robot-card h3, .robot-card p {{
    color: white !important;
}}

.feature-card {{
    background: {PANEL};
    border: 1px solid rgba(140,150,180,.18);
    padding: 20px;
    border-radius: 17px;
}}

.footer {{
    text-align: center;
    color: {MUTED};
    padding: 25px;
    font-size: 12px;
}}

div.stButton > button {{
    border-radius: 11px;
    min-height: 42px;
    font-weight: 600;
}}

[data-testid="stMetric"] {{
    background: {PANEL};
    padding: 14px;
    border-radius: 14px;
}}

</style>
""", unsafe_allow_html=True)


# =====================================================
# 9. ROBOT
# =====================================================

ROBOT = """
<svg width="70" height="70" viewBox="0 0 100 100"
xmlns="http://www.w3.org/2000/svg">
<path d="M50 7V18" stroke="#D8D2FF" stroke-width="5"/>
<circle cx="50" cy="7" r="5" fill="#A99CFF"/>
<rect x="16" y="22" width="68" height="57"
rx="19" fill="#F2F3FF"/>
<rect x="23" y="30" width="54" height="40"
rx="13" fill="#6554B8"/>
<circle cx="39" cy="49" r="5" fill="#8EF0E0"/>
<circle cx="61" cy="49" r="5" fill="#8EF0E0"/>
<path d="M40 60 Q50 68 60 60"
stroke="white" stroke-width="3" fill="none"/>
<rect x="7" y="43" width="9" height="20"
rx="4" fill="#B8B0FF"/>
<rect x="84" y="43" width="9" height="20"
rx="4" fill="#B8B0FF"/>
<rect x="31" y="78" width="12" height="12"
rx="5" fill="#B8B0FF"/>
<rect x="57" y="78" width="12" height="12"
rx="5" fill="#B8B0FF"/>
</svg>
"""


# =====================================================
# 10. SIDEBAR
# =====================================================

with st.sidebar:

    st.markdown(
        f"""
        <div class="robot-card">
            {ROBOT}
            <h3>AI Study Buddy</h3>
            <p>Your academic companion 🤖</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.button(
        t("💬 Open Study Buddy", "💬 افتحي مساعد الدراسة"),
        use_container_width=True,
        type="primary"
    ):

        st.session_state.page = "Chat"
        st.rerun()

    st.divider()

    navigation = {
        "🏠 Home": "Home",
        "👤 Student Profile": "Profile",
        "📂 Upload & Analyze": "Upload",
        "📚 My Materials": "Materials",
        "🗓️ Academic Timetable": "Timetable",
        "📅 Smart Weekly Planner": "Planner",
        "📈 My Progress": "Progress",
        "🧠 Stress Management": "Stress",
        "💡 Help & Guide": "Help",
        "⚙️ Settings": "Settings",
        "🤖 AI Study Buddy": "Chat"
    }

    if ARABIC:

        navigation = {
            "🏠 الرئيسية": "Home",
            "👤 الملف الشخصي": "Profile",
            "📂 رفع وتحليل الملفات": "Upload",
            "📚 ملفاتي الدراسية": "Materials",
            "🗓️ الجدول الأكاديمي": "Timetable",
            "📅 المخطط الأسبوعي": "Planner",
            "📈 إنجازاتي": "Progress",
            "🧠 إدارة التوتر": "Stress",
            "💡 المساعدة": "Help",
            "⚙️ الإعدادات": "Settings",
            "🤖 مساعد الدراسة": "Chat"
        }

    labels = list(navigation.keys())

    current = next(
        (
            label for label, value in navigation.items()
            if value == st.session_state.page
        ),
        labels[0]
    )

    selected = st.radio(
        "Navigation",
        labels,
        index=labels.index(current),
        label_visibility="collapsed"
    )

    st.session_state.page = navigation[selected]


page = st.session_state.page


# =====================================================
# 11. FILE EXTRACTION
# =====================================================

def extract_pdf(uploaded_file):

    if fitz is None:
        raise RuntimeError(
            "PyMuPDF is missing. Add it to requirements.txt."
        )

    document = fitz.open(
        stream=uploaded_file.getvalue(),
        filetype="pdf"
    )

    pages = []

    for number, page in enumerate(document, start=1):

        content = page.get_text("text").strip()

        if not content:
            content = (
                "No selectable text found on this page. "
                "This may be a scanned page."
            )

        pages.append(
            f"[Page {number}]\n{content}"
        )

    document.close()

    return "\n\n".join(pages)


# =====================================================
# 12. HOME
# =====================================================

if page == "Home":

    profile = get_profile()
    subjects = get_subjects()
    sessions = get_sessions()

    xp = get_xp()
    level, next_level = get_level(xp)

    name = profile["name"]

    greeting = (
        f"Welcome back, {name}!"
        if name else "Welcome to your study workspace!"
    )

    if ARABIC:
        greeting = (
            f"أهلاً بعودتك، {name}!"
            if name else "أهلاً بك في مساعدك الدراسي الذكي!"
        )

    st.markdown(
        f"""
        <div class="hero">
            <h1>🎓 {greeting}</h1>
            <p>{t(
                "Organize your study life and take care of yourself.",
                "نظّمي مذاكرتك واهتمي بنفسك."
            )}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    a, b, c, d = st.columns(4)

    a.metric(t("📚 Subjects", "📚 المواد"), len(subjects))
    b.metric(t("⏰ Daily hours", "⏰ ساعات يومية"),
             f"{profile['daily_hours']} h")
    c.metric(t("📅 Sessions", "📅 الجلسات"), len(sessions))
    d.metric("⭐ XP", xp)

    st.subheader(t("Your Study Buddy", "مساعدك الدراسي"))

    st.markdown(
        f"""
        <div class="feature-card">
            <h2>{level[2]} {level[1]}</h2>
            <p>{t(
                "Complete your sessions to level up.",
                "أنجزي جلسات المذاكرة لتطوير مستوى مساعدك."
            )}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    if next_level:

        progress = (
            (xp - level[0])
            / (next_level[0] - level[0])
        )

        st.progress(min(1.0, progress))
        st.caption(f"{next_level[0] - xp} XP to {next_level[1]}")

    st.subheader(t("Quick Access", "وصول سريع"))

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button(t("📂 Upload Files", "📂 رفع الملفات"),
                     use_container_width=True):
            st.session_state.page = "Upload"
            st.rerun()

    with c2:
        if st.button(t("📅 Weekly Planner", "📅 الجدول الأسبوعي"),
                     use_container_width=True):
            st.session_state.page = "Planner"
            st.rerun()

    with c3:
        if st.button(t("🤖 Study Buddy", "🤖 مساعد الدراسة"),
                     use_container_width=True):
            st.session_state.page = "Chat"
            st.rerun()

    if not sessions.empty:

        st.subheader(t("Your Current Plan", "خطتك الحالية"))

        st.dataframe(
            sessions.drop(columns=["ID"]),
            use_container_width=True,
            hide_index=True
        )


# =====================================================
# 13. STUDENT PROFILE
# =====================================================

elif page == "Profile":

    st.title("👤 " + t("Student Profile", "الملف الشخصي"))

    p = get_profile()

    with st.form("profile_form"):

        name = st.text_input(
            t("Student Name", "اسم الطالب"),
            p["name"]
        )

        college = st.text_input(
            t("University / College", "الجامعة / الكلية"),
            p["college"]
        )

        major = st.text_input(
            t("Major", "التخصص"),
            p["major"]
        )

        years = [
            "1st year", "2nd year",
            "3rd year", "4th year", "Other"
        ]

        year = st.selectbox(
            t("Academic Year", "السنة الدراسية"),
            years,
            index=years.index(p["year"])
            if p["year"] in years else 0
        )

        hours = st.slider(
            t("Daily Study Hours", "ساعات المذاكرة اليومية"),
            1, 12, int(p["daily_hours"])
        )

        submitted = st.form_submit_button(
            t("Save Profile", "حفظ البيانات"),
            type="primary"
        )

        if submitted:

            execute("""
                UPDATE profile
                SET name=?, college=?, major=?,
                    year=?, daily_hours=?
                WHERE id=1
            """, (name, college, major, year, hours))

            st.success(t("Profile saved!", "تم حفظ البيانات!"))


# =====================================================
# 14. UPLOAD FILES
# =====================================================

elif page == "Upload":

    st.title("📂 " + t("Upload & Analyze", "رفع وتحليل الملفات"))

    st.info(t(
        "Upload lecture PDFs and academic timetable PDFs.",
        "ارفعي ملفات المحاضرات والجداول الأكاديمية بصيغة PDF."
    ))

    lectures = st.file_uploader(
        t("Lecture PDFs", "ملفات المحاضرات"),
        type=["pdf"],
        accept_multiple_files=True,
        key="lecture_upload"
    )

    schedules = st.file_uploader(
        t("Timetable / Exam PDFs", "ملفات الجدول والامتحانات"),
        type=["pdf"],
        accept_multiple_files=True,
        key="schedule_upload"
    )

    if st.button(
        t("🔍 Extract Text", "🔍 استخراج النص"),
        type="primary",
        use_container_width=True
    ):

        selected_files = (
            [(f, "Lecture") for f in (lectures or [])]
            + [(f, "Academic Schedule") for f in (schedules or [])]
        )

        if not selected_files:

            st.warning(t(
                "Choose files first.",
                "اختاري الملفات أولاً."
            ))

        for file, kind in selected_files:

            try:

                content = extract_pdf(file)

                execute("""
                    INSERT INTO materials
                    (filename, subject, content, created)
                    VALUES (?, ?, ?, ?)
                """, (
                    file.name,
                    kind,
                    content,
                    datetime.now().isoformat(timespec="minutes")
                ))

                if kind == "Academic Schedule":

                    execute("""
                        INSERT INTO timetable(id, content, confirmed)
                        VALUES(1, ?, 0)
                        ON CONFLICT(id)
                        DO UPDATE SET
                        content=excluded.content,
                        confirmed=0
                    """, (content,))

                st.success(file.name + " ✓")

            except Exception as error:

                st.error(f"{file.name}: {error}")

    st.caption(
        "Scanned PDFs may need OCR before their text can be extracted."
    )


# =====================================================
# 15. MY MATERIALS
# =====================================================

elif page == "Materials":

    st.title("📚 " + t("My Materials", "ملفاتي الدراسية"))

    search = st.text_input(
        t("Search materials", "ابحثي في الملفات")
    )

    materials = get_materials()

    if not materials:

        st.info(t(
            "No materials uploaded yet.",
            "لم يتم رفع ملفات بعد."
        ))

    for item in materials:

        mid, filename, subject, content, created = item

        if search and search.lower() not in (
            filename + subject + content
        ).lower():
            continue

        with st.expander("📄 " + filename):

            st.caption(f"{subject} · {created}")

            edited = st.text_area(
                "Extracted Text",
                content or "",
                height=250,
                key=f"material_{mid}"
            )

            c1, c2 = st.columns(2)

            with c1:

                if st.button(
                    "Save Corrections",
                    key=f"save_{mid}"
                ):

                    execute(
                        "UPDATE materials SET content=? WHERE id=?",
                        (edited, mid)
                    )

                    st.success("Saved.")

            with c2:

                if st.button(
                    "Delete Material",
                    key=f"delete_{mid}"
                ):

                    execute(
                        "DELETE FROM materials WHERE id=?",
                        (mid,)
                    )

                    st.rerun()


# =====================================================
# 16. ACADEMIC TIMETABLE
# =====================================================

elif page == "Timetable":

    st.title("🗓️ " + t("Academic Timetable", "الجدول الأكاديمي"))

    row = fetch_one("""
        SELECT content, confirmed
        FROM timetable
        WHERE id=1
    """)

    if row:

        corrected = st.text_area(
            t("Review your timetable", "راجعي الجدول"),
            row[0] or "",
            height=300
        )

        if st.button(
            t("Confirm Timetable", "تأكيد الجدول"),
            type="primary"
        ):

            execute("""
                UPDATE timetable
                SET content=?, confirmed=1
                WHERE id=1
            """, (corrected,))

            st.success(t(
                "Timetable confirmed.",
                "تم تأكيد الجدول."
            ))

        st.warning(t(
            "The extracted schedule is stored as text. "
            "Automatic calendar conversion is not enabled.",
            "يتم حفظ الجدول كنص للمراجعة، "
            "والتحويل التلقائي لمواعيد التقويم غير مفعّل."
        ))

    else:

        st.info(t(
            "Upload your academic timetable first.",
            "ارفعي الجدول الأكاديمي أولاً."
        ))


# =====================================================
# 17. SMART WEEKLY PLANNER
# =====================================================

elif page == "Planner":

    st.title("📅 " + t("Smart Weekly Planner", "المخطط الأسبوعي الذكي"))

    st.caption(t(
        "Study sessions: 30, 60, 90 or 120 minutes. "
        "Maximum 3 subjects per day.",
        "جلسات المذاكرة: 30 أو 60 أو 90 أو 120 دقيقة. "
        "بحد أقصى 3 مواد يومياً."
    ))

    with st.form("add_subject", clear_on_submit=True):

        subject_name = st.text_input(
            t("Subject Name", "اسم المادة")
        )

        c1, c2 = st.columns(2)

        with c1:

            difficulty = st.selectbox(
                t("Difficulty", "الصعوبة"),
                ["Easy", "Medium", "Hard"]
            )

        with c2:

            priority = st.selectbox(
                t("Priority", "الأولوية"),
                ["Low", "Normal", "High"]
            )

        exam = st.date_input(
            t("Exam Date", "تاريخ الامتحان"),
            value=None
        )

        add = st.form_submit_button(
            t("➕ Add Subject", "➕ إضافة مادة")
        )

        if add:

            if not subject_name.strip():

                st.error(t(
                    "Enter a subject name.",
                    "اكتبي اسم المادة."
                ))

            else:

                try:

                    execute("""
                        INSERT INTO subjects
                        (name, difficulty, priority, exam_date)
                        VALUES (?, ?, ?, ?)
                    """, (
                        subject_name.strip(),
                        difficulty,
                        priority,
                        exam.isoformat() if exam else ""
                    ))

                    st.success(t(
                        "Subject added.",
                        "تمت إضافة المادة."
                    ))

                    st.rerun()

                except sqlite3.IntegrityError:

                    st.error(t(
                        "Subject already exists.",
                        "المادة موجودة بالفعل."
                    ))

    subjects = get_subjects()

    if not subjects.empty:

        st.subheader(t("Your Subjects", "موادك الدراسية"))

        st.dataframe(
            subjects.drop(columns=["ID"]),
            use_container_width=True,
            hide_index=True
        )

        daily_hours = st.slider(
            t("Daily Study Hours", "ساعات المذاكرة اليومية"),
            1, 12,
            int(get_profile()["daily_hours"])
        )

        if st.button(
            t("✨ Generate Weekly Plan", "✨ إنشاء الجدول الأسبوعي"),
            type="primary",
            use_container_width=True
        ):

            difficulty_weight = {
                "Easy": 1,
                "Medium": 2,
                "Hard": 3
            }

            priority_weight = {
                "Low": 1,
                "Normal": 2,
                "High": 3
            }

            items = []

            for _, row in subjects.iterrows():

                weight = (
                    difficulty_weight.get(row["Difficulty"], 2)
                    + priority_weight.get(row["Priority"], 2)
                ) / 2

                if row["Exam Date"]:

                    try:

                        days_left = (
                            date.fromisoformat(row["Exam Date"])
                            - date.today()
                        ).days

                        if 0 <= days_left <= 14:
                            weight += (15 - days_left) / 5

                    except ValueError:
                        pass

                items.append({
                    "name": row["Subject"],
                    "weight": weight
                })

            total_weight = sum(
                item["weight"] for item in items
            )

            remaining = {
                item["name"]: max(
                    0.5,
                    round(
                        daily_hours * 7
                        * item["weight"] / total_weight * 2
                    ) / 2
                )
                for item in items
            }

            today = date.today()

            days_until_saturday = (
                5 - today.weekday()
            ) % 7

            if days_until_saturday == 0:
                days_until_saturday = 7

            week_start = today + timedelta(
                days=days_until_saturday
            )

            generated = []

            for index, day_name in enumerate(DAYS):

                current_date = week_start + timedelta(days=index)

                used_hours = 0
                used_subjects = set()
                minute_of_day = 9 * 60

                while used_hours + 0.5 <= daily_hours:

                    choices = [
                        item for item in items
                        if remaining[item["name"]] >= 0.5
                        and item["name"] not in used_subjects
                    ]

                    if not choices:
                        break

                    chosen = max(
                        choices,
                        key=lambda item: (
                            item["weight"],
                            remaining[item["name"]]
                        )
                    )

                    duration = min(
                        2,
                        daily_hours - used_hours,
                        remaining[chosen["name"]]
                    )

                    duration = math.floor(duration * 2) / 2

                    if duration < 0.5:
                        break

                    start = (
                        datetime.combine(
                            current_date,
                            datetime.min.time()
                        )
                        + timedelta(minutes=minute_of_day)
                    ).strftime("%H:%M")

                    generated.append((
                        day_name,
                        current_date.isoformat(),
                        start,
                        chosen["name"],
                        duration,
                        "Pending"
                    ))

                    remaining[chosen["name"]] -= duration
                    used_hours += duration
                    used_subjects.add(chosen["name"])

                    minute_of_day += int(duration * 60) + 15

                    if len(used_subjects) >= 3:
                        break

            with db_connection() as conn:

                conn.execute("DELETE FROM sessions")

                for item in generated:

                    conn.execute("""
                        INSERT INTO sessions
                        (day, session_date, start_time,
                         subject, duration, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, item)

            st.success(t(
                "Your weekly plan is ready!",
                "تم إنشاء جدولك الأسبوعي!"
            ))

            st.rerun()

    sessions = get_sessions()

    if not sessions.empty:

        st.divider()

        st.subheader(t(
            "Your Weekly Schedule",
            "جدولك الأسبوعي"
        ))

        st.dataframe(
            sessions.drop(columns=["ID"]),
            use_container_width=True,
            hide_index=True
        )

        csv_data = sessions.drop(
            columns=["ID"]
        ).to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            t("⬇️ Download CSV", "⬇️ تحميل الجدول"),
            csv_data,
            "weekly_study_plan.csv",
            "text/csv"
        )

        pending = sessions[
            sessions["Status"] == "Pending"
        ]

        if not pending.empty:

            selected = st.multiselect(
                t(
                    "Select completed sessions",
                    "اختاري الجلسات المكتملة"
                ),
                pending["ID"].tolist()
            )

            if st.button(
                t("✅ Mark as Completed", "✅ تحديد كمكتملة")
            ):

                for session_id in selected:

                    execute("""
                        UPDATE sessions
                        SET status='Completed'
                        WHERE id=? AND status='Pending'
                    """, (session_id,))

                    add_xp(f"session-{session_id}", 20)

                st.success(t(
                    "Progress updated!",
                    "تم تحديث الإنجاز!"
                ))

                st.rerun()

        if st.button(
            t("🗑️ Clear Weekly Plan", "🗑️ مسح الجدول")
        ):

            execute("DELETE FROM sessions")
            st.rerun()


# =====================================================
# 18. AI STUDY BUDDY
# =====================================================

elif page == "Chat":

    st.title("🤖 " + t("AI Study Buddy", "مساعد الدراسة الذكي"))

    st.markdown(
        f"""
        <div class="robot-card">
            {ROBOT}
            <h3>Study Buddy</h3>
            <p>{t(
                "Your friendly academic companion.",
                "رفيقك الدراسي الذكي."
            )}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    for role, message in st.session_state.chat_history:

        with st.chat_message(
            role,
            avatar="🤖" if role == "assistant" else "🧑‍🎓"
        ):

            st.markdown(message)

    question = st.chat_input(
        t("Ask your study buddy...", "اسألي مساعد الدراسة...")
    )

    if question:

        st.session_state.chat_history.append(
            ("user", question)
        )

        materials = get_materials()

        context = "\n\n".join(
            f"FILE: {item[1]}\n{item[3]}"
            for item in materials
        )

        answer = ""

        try:
            api_key = st.secrets.get(
                "OPENAI_API_KEY",
                os.getenv("OPENAI_API_KEY", "")
            )
        except Exception:
            api_key = os.getenv("OPENAI_API_KEY", "")

        if api_key and OpenAI:

            try:

                client = OpenAI(api_key=api_key)

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    temperature=0.2,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a careful bilingual study assistant. "
                                "Use uploaded materials as the main source. "
                                "If information is missing, say so clearly. "
                                "Do not invent facts."
                            )
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Uploaded materials:\n{context[:25000]}\n\n"
                                f"Question: {question}"
                            )
                        }
                    ]
                )

                answer = response.choices[0].message.content

            except Exception as error:

                answer = f"AI connection error: {error}"

        else:

            keywords = [
                word.lower()
                for word in re.findall(r"\w+", question)
                if len(word) > 3
            ]

            matches = []

            for item in materials:

                filename = item[1]
                content = item[3] or ""

                lines = [
                    line.strip()
                    for line in content.splitlines()
                    if line.strip()
                    and any(
                        word in line.lower()
                        for word in keywords
                    )
                ]

                if lines:

                    matches.append(
                        f"**{filename}**\n"
                        + "\n".join(lines[:6])
                    )

            if matches:

                answer = "\n\n".join(matches[:4])

                answer += (
                    "\n\nKeyword search only. "
                    "Add an OpenAI API key for AI-generated answers."
                )

            else:

                answer = t(
                    "I couldn't find the answer in your uploaded files. "
                    "Upload the relevant lecture or configure an AI API key.",
                    "لم أجد الإجابة في ملفاتك. "
                    "ارفعي المحاضرة المناسبة أو أضيفي مفتاح API لتفعيل الذكاء الاصطناعي."
                )

        st.session_state.chat_history.append(
            ("assistant", answer)
        )

        st.rerun()

    if st.button(t("Clear Chat", "مسح المحادثة")):

        st.session_state.chat_history = []
        st.rerun()


# =====================================================
# 19. MY PROGRESS
# =====================================================

elif page == "Progress":

    st.title("📈 " + t("My Progress", "إنجازاتي"))

    xp = get_xp()
    level, next_level = get_level(xp)

    sessions = get_sessions()

    completed = 0
    completed_hours = 0

    if not sessions.empty:

        done = sessions[
            sessions["Status"] == "Completed"
        ]

        completed = len(done)
        completed_hours = done["Hours"].sum()

    c1, c2, c3 = st.columns(3)

    c1.metric("⭐ XP", xp)
    c2.metric("🏅 Level", level[1])
    c3.metric("🤖 Buddy", level[2])

    st.metric(
        t("Completed Sessions", "الجلسات المكتملة"),
        completed
    )

    st.metric(
        t("Completed Study Hours", "ساعات المذاكرة المكتملة"),
        f"{completed_hours:.1f}"
    )

    if next_level:

        progress = (
            (xp - level[0])
            / (next_level[0] - level[0])
        )

        st.progress(min(1.0, progress))

        st.caption(
            f"{next_level[0] - xp} XP to {next_level[1]}"
        )

    if not sessions.empty:

        st.subheader(t("Session Status", "حالة الجلسات"))

        chart = sessions.groupby("Status")["Hours"].sum()

        st.bar_chart(chart)


# =====================================================
# 20. STRESS MANAGEMENT
# =====================================================

elif page == "Stress":

    st.title("🧠 " + t("Stress Management", "إدارة التوتر"))

    with st.form("stress_form"):

        stress = st.slider(
            t("Stress Level", "مستوى التوتر"),
            1, 10, 5
        )

        sleep = st.slider(
            t("Sleep Hours", "ساعات النوم"),
            0.0, 12.0, 7.0, 0.5
        )

        focus = st.slider(
            t("Focus Level", "مستوى التركيز"),
            1, 10, 6
        )

        workload = st.slider(
            t("Workload Level", "ضغط الدراسة"),
            1, 10, 5
        )

        submitted = st.form_submit_button(
            t("Analyze My Wellbeing", "تحليل حالتي"),
            type="primary"
        )

    if submitted:

        score = round(
            stress * 0.35
            + (10 - focus) * 0.25
            + workload * 0.25
            + max(0, 8 - sleep) * 0.15,
            1
        )

        execute("""
            INSERT INTO stress_history
            (created, score, stress, sleep, focus, workload)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(timespec="minutes"),
            score,
            stress,
            sleep,
            focus,
            workload
        ))

        st.metric(
            t("Stress Indicator", "مؤشر التوتر"),
            f"{score}/10"
        )

        if score >= 7:

            st.warning(t(
                "Your indicator is high. Reduce workload and take breaks.",
                "المؤشر مرتفع. قللي ضغط الدراسة وخدي فواصل."
            ))

        elif score >= 4:

            st.info(t(
                "Your indicator is moderate. Balance study and rest.",
                "المؤشر متوسط. وازني بين المذاكرة والراحة."
            ))

        else:

            st.success(t(
                "Your indicator is relatively low. Keep your routine balanced.",
                "المؤشر منخفض نسبياً. حافظي على توازنك."
            ))

        if sleep < 7:
            st.write("🌙 " + t(
                "Try to improve your sleep routine.",
                "حاولي تحسين مواعيد نومك."
            ))

        if focus < 5:
            st.write("🎯 " + t(
                "Try shorter focused study sessions.",
                "جربي جلسات مذاكرة أقصر وأكثر تركيزاً."
            ))

        if workload > 7:
            st.write("📝 " + t(
                "Break large tasks into smaller steps.",
                "قسّمي المهام الكبيرة إلى خطوات أصغر."
            ))

        st.caption(t(
            "This is a self-check indicator, not a medical diagnosis.",
            "هذا تقييم ذاتي وليس تشخيصاً طبياً."
        ))


# =====================================================
# 21. HELP & GUIDE
# =====================================================

elif page == "Help":

    st.title("💡 " + t("Help & Guide", "المساعدة والإرشادات"))

    st.markdown("""
    ### How to use the application

    1. **Student Profile:** Add your academic information.
    2. **Upload & Analyze:** Upload lecture and timetable PDFs.
    3. **My Materials:** Review and search extracted text.
    4. **Academic Timetable:** Review your uploaded timetable.
    5. **Weekly Planner:** Add subjects and generate a study plan.
    6. **AI Study Buddy:** Ask questions about your materials.
    7. **My Progress:** Complete sessions to earn XP.
    8. **Stress Management:** Review your stress and focus indicators.
    """)

    st.warning(
        "Streamlit Cloud local SQLite storage may not be durable "
        "across redeployments. Use an external database for reliable "
        "long-term cloud storage."
    )


# =====================================================
# 22. SETTINGS
# =====================================================

elif page == "Settings":

    st.title("⚙️ " + t("Settings", "الإعدادات"))

    language = st.selectbox(
        t("Language", "اللغة"),
        ["English", "العربية"],
        index=["English", "العربية"].index(LANGUAGE)
    )

    theme = st.selectbox(
        t("Appearance", "المظهر"),
        ["Dark", "Light"],
        index=["Dark", "Light"].index(THEME)
    )

    if st.button(
        t("Save Settings", "حفظ الإعدادات"),
        type="primary"
    ):

        execute("""
            UPDATE settings
            SET language=?, theme=?
            WHERE id=1
        """, (language, theme))

        st.success(t(
            "Settings saved. Refreshing...",
            "تم حفظ الإعدادات. جاري التحديث..."
        ))

        st.rerun()

    st.divider()

    st.subheader("AI Study Buddy")

    st.write(t(
        "To enable AI answers, add OPENAI_API_KEY "
        "under Streamlit Cloud → App Settings → Secrets.",
        "لتفعيل إجابات الذكاء الاصطناعي، أضيفي OPENAI_API_KEY "
        "في Streamlit Cloud ثم App Settings ثم Secrets."
    ))


# =====================================================
# 23. FOOTER
# =====================================================

st.divider()

st.markdown(
    """
    <div class="footer">
        SMART STUDENT ASSISTANT
        <br>
        ACADEMIC & STRESS MANAGEMENT
    </div>
    """,
    unsafe_allow_html=True
)
