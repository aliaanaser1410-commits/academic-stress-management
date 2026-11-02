
import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import re
import math
from datetime import date, datetime, timedelta

try:
    import fitz
except ImportError:
    fitz = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# =====================================================
# 1. APP CONFIGURATION
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
# 2. DATABASE
# =====================================================

def db_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def initialize_database():
    with db_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY CHECK(id=1),
            name TEXT DEFAULT '',
            college TEXT DEFAULT '',
            major TEXT DEFAULT '',
            year TEXT DEFAULT '',
            daily_hours REAL DEFAULT 4
        );

        INSERT OR IGNORE INTO profile(id) VALUES(1);

        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            difficulty TEXT,
            priority TEXT,
            exam_date TEXT
        );

        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            subject TEXT,
            content TEXT,
            created TEXT
        );

        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY CHECK(id=1),
            content TEXT,
            confirmed INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT,
            session_date TEXT,
            start_time TEXT,
            subject TEXT,
            duration REAL,
            status TEXT DEFAULT 'Pending'
        );

        CREATE TABLE IF NOT EXISTS xp (
            event TEXT PRIMARY KEY,
            points INTEGER
        );

        CREATE TABLE IF NOT EXISTS stress_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created TEXT,
            score REAL,
            stress INTEGER,
            sleep REAL,
            focus INTEGER,
            workload INTEGER
        );

        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK(id=1),
            language TEXT DEFAULT 'English',
            theme TEXT DEFAULT 'Dark'
        );

        INSERT OR IGNORE INTO settings(id) VALUES(1);
        """)


initialize_database()


def execute_query(query, params=()):
    with db_connection() as conn:
        conn.execute(query, params)


def fetch_one(query, params=()):
    with db_connection() as conn:
        return conn.execute(query, params).fetchone()


def fetch_all(query, params=()):
    with db_connection() as conn:
        return conn.execute(query, params).fetchall()


# =====================================================
# 3. SESSION STATE
# =====================================================

defaults = {
    "page": "Home",
    "chat_history": [],
    "chat_input": "",
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


settings = fetch_one(
    "SELECT language, theme FROM settings WHERE id=1"
)

LANGUAGE = settings[0] if settings else "English"
THEME = settings[1] if settings else "Dark"

ARABIC = LANGUAGE == "العربية"
DARK = THEME == "Dark"


def text(en, ar):
    return ar if ARABIC else en


def get_profile():
    row = fetch_one(
        "SELECT name, college, major, year, daily_hours "
        "FROM profile WHERE id=1"
    )

    return {
        "name": row[0],
        "college": row[1],
        "major": row[2],
        "year": row[3],
        "daily_hours": row[4]
    }


def get_subjects():
    rows = fetch_all(
        "SELECT id, name, difficulty, priority, exam_date "
        "FROM subjects ORDER BY id"
    )

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


# =====================================================
# 4. DESIGN
# =====================================================

BACKGROUND = "#101827" if DARK else "#F3F6FC"
PANEL = "#1B293B" if DARK else "#FFFFFF"
FOREGROUND = "#F4F6FC" if DARK else "#172033"
MUTED = "#AAB7C8" if DARK else "#68758A"

st.markdown(f"""
<style>
.stApp {{
    background: {BACKGROUND};
    color: {FOREGROUND};
}}

[data-testid="stSidebar"] {{
    background: {PANEL};
}}

.block-container {{
    max-width: 1450px;
    padding-top: 1.5rem;
}}

h1, h2, h3, h4, p, label {{
    color: {FOREGROUND};
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
    padding: 15px;
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
    min-height: 140px;
}}

.feature-icon {{
    font-size: 30px;
}}

.small-muted {{
    color: {MUTED};
    font-size: 13px;
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
    border: 1px solid rgba(140,150,180,.15);
}}

.footer {{
    text-align: center;
    color: {MUTED};
    padding: 25px;
    font-size: 12px;
}}

</style>
""", unsafe_allow_html=True)


# =====================================================
# 5. ROBOT DESIGN
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
# 6. SIDEBAR NAVIGATION
# =====================================================

with st.sidebar:

    st.markdown(
        f"""
        <div class="robot-card">
            {ROBOT}
            <h3>AI Study Buddy</h3>
            <p>Always ready to help you 🤖</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.button(
        "💬  " + text("Open Study Buddy", "افتحي مساعد الدراسة"),
        use_container_width=True,
        type="primary"
    ):
        st.session_state.page = "Chat"
        st.rerun()

    st.divider()

    st.markdown("### 🎓 Smart Student Assistant")

    pages = {
        "🏠 Home": "Home",
        "👤 Student Profile": "Profile",
        "📂 Upload & Analyze": "Upload",
        "📚 My Materials": "Materials",
        "🗓️ Academic Timetable": "Timetable",
        "📅 Smart Weekly Planner": "Planner",
        "📈 My Progress": "Progress",
        "🧠 Stress Management": "Stress",
        "💡 Help & Guide": "Help",
        "⚙️ Settings": "Settings"
    }

    if ARABIC:
        pages = {
            "🏠 الرئيسية": "Home",
            "👤 الملف الشخصي": "Profile",
            "📂 رفع وتحليل الملفات": "Upload",
            "📚 ملفاتي الدراسية": "Materials",
            "🗓️ الجدول الأكاديمي": "Timetable",
            "📅 المخطط الأسبوعي الذكي": "Planner",
            "📈 إنجازاتي": "Progress",
            "🧠 إدارة التوتر": "Stress",
            "💡 المساعدة والإرشادات": "Help",
            "⚙️ الإعدادات": "Settings"
        }

    labels = list(pages.keys())

    current_label = next(
        (label for label, value in pages.items()
         if value == st.session_state.page),
        labels[0]
    )

    selected = st.radio(
        "Navigation",
        labels,
        index=labels.index(current_label),
        label_visibility="collapsed"
    )

    st.session_state.page = pages[selected]


# =====================================================
# 7. FILE TEXT EXTRACTION
# =====================================================

def extract_file(uploaded_file):

    content = uploaded_file.getvalue()

    if uploaded_file.name.lower().endswith(".pdf"):

        if fitz is None:
            raise RuntimeError(
                "PyMuPDF is not installed. Check requirements.txt."
            )

        document = fitz.open(
            stream=content,
            filetype="pdf"
        )

        pages_text = []

        for number, page in enumerate(document, start=1):

            page_text = page.get_text("text").strip()

            if not page_text:
                page_text = (
                    "[No selectable text found on this page. "
                    "OCR may be required.]"
                )

            pages_text.append(
                f"[Page {number}]\n{page_text}"
            )

        document.close()

        return "\n\n".join(pages_text)

    if Image is None or pytesseract is None:
        raise RuntimeError(
            "Image OCR requires Pillow and pytesseract."
        )

    image = Image.open(io.BytesIO(content))

    try:
        return pytesseract.image_to_string(
            image,
            lang="eng+ara"
        )
    except Exception:
        return pytesseract.image_to_string(
            image,
            lang="eng"
        )


# =====================================================
# 8. XP AND LEVELS
# =====================================================

def add_xp(event, points=20):

    execute_query(
        "INSERT OR IGNORE INTO xp(event, points) VALUES(?, ?)",
        (event, points)
    )


def get_xp():

    row = fetch_one(
        "SELECT COALESCE(SUM(points), 0) FROM xp"
    )

    return int(row[0])


def get_level(xp):

    levels = [
        (0, "Beginner", "🐣"),
        (100, "Focused Learner", "🐥"),
        (300, "Study Champion", "🦉"),
        (600, "Study Master", "🦅")
    ]

    current = levels[0]

    for level in levels:
        if xp >= level[0]:
            current = level

    next_level = next(
        (level for level in levels if level[0] > xp),
        None
    )

    return current, next_level


# =====================================================
# 9. HOME DASHBOARD
# =====================================================

page = st.session_state.page

if page == "Home":

    p = get_profile()
    subjects = get_subjects()
    sessions = get_sessions()

    xp = get_xp()
    level, next_level = get_level(xp)

    greeting = (
        f"Welcome back, {p['name']}!"
        if p["name"]
        else "Welcome to your study workspace!"
    )

    if ARABIC:
        greeting = (
            f"أهلاً بعودتك، {p['name']}!"
            if p["name"]
            else "أهلاً بك في مساعدك الدراسي الذكي!"
        )

    st.markdown(
        f"""
        <div class="hero">
            <h1>🎓 {greeting}</h1>
            <p>
                {text(
                    "Organize your study life, understand your materials, and take care of yourself.",
                    "نظّمي مذاكرتك وافهمي محاضراتك واهتمي بنفسك."
                )}
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    a, b, c, d = st.columns(4)

    a.metric(
        "📚 " + text("Subjects", "المواد"),
        len(subjects)
    )

    b.metric(
        "⏰ " + text("Daily hours", "ساعات يومية"),
        f"{p['daily_hours']} h"
    )

    c.metric(
        "📅 " + text("Study sessions", "جلسات"),
        len(sessions)
    )

    d.metric("⭐ XP", xp)

    st.subheader(text("Your Study Buddy", "مساعدك الدراسي"))

    st.markdown(
        f"""
        <div class="feature-card">
            <h2>{level[2]} {level[1]}</h2>
            <p class="small-muted">
                {text(
                    "Keep completing your study sessions to level up.",
                    "أنجزي جلسات المذاكرة لتطوير مستوى مساعدك."
                )}
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    if next_level:
        progress = (xp - level[0]) / (
            next_level[0] - level[0]
        )
        st.progress(min(1.0, progress))
        st.caption(
            f"{next_level[0] - xp} XP to {next_level[1]}"
        )

    st.subheader(text("Quick Access", "وصول سريع"))

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(
            "📂 " + text("Upload Files", "رفع الملفات"),
            use_container_width=True
        ):
            st.session_state.page = "Upload"
            st.rerun()

    with col2:
        if st.button(
            "📅 " + text("Create Weekly Plan", "إنشاء جدول أسبوعي"),
            use_container_width=True
        ):
            st.session_state.page = "Planner"
            st.rerun()

    with col3:
        if st.button(
            "🤖 " + text("Ask Study Buddy", "اسألي المساعد"),
            use_container_width=True
        ):
            st.session_state.page = "Chat"
            st.rerun()

    if not sessions.empty:
        st.subheader(text("Your Current Plan", "خطتك الحالية"))
        st.dataframe(
            sessions.drop(columns=["ID"]),
            use_container_width=True,
            hide_index=True
        )


# =====================================================
# 10. STUDENT PROFILE
# =====================================================

elif page == "Profile":

    st.title("👤 " + text("Student Profile", "الملف الشخصي"))

    p = get_profile()

    with st.form("profile_form"):

        name = st.text_input(
            text("Student Name", "اسم الطالب"),
            p["name"]
        )

        college = st.text_input(
            text("University / College", "الجامعة / الكلية"),
            p["college"]
        )

        major = st.text_input(
            text("Major", "التخصص"),
            p["major"]
        )

        years = [
            "1st year", "2nd year", "3rd year",
            "4th year", "Other"
        ]

        year = st.selectbox(
            text("Academic Year", "السنة الدراسية"),
            years,
            index=(
                years.index(p["year"])
                if p["year"] in years else 0
            )
        )

        daily_hours = st.slider(
            text(
                "Available Study Hours Per Day",
                "ساعات المذاكرة المتاحة يومياً"
            ),
            1, 12,
            int(p["daily_hours"])
        )

        submitted = st.form_submit_button(
            text("Save Profile", "حفظ البيانات"),
            type="primary"
        )

        if submitted:

            execute_query("""
                UPDATE profile
                SET name=?, college=?, major=?,
                    year=?, daily_hours=?
                WHERE id=1
            """, (
                name, college, major,
                year, daily_hours
            ))

            st.success(
                text("Profile saved!", "تم حفظ البيانات!")
            )


# =====================================================
# 11. UPLOAD FILES
# =====================================================

elif page == "Upload":

    st.title("📂 " + text("Upload & Analyze", "رفع وتحليل الملفات"))

    st.info(
        text(
            "Upload lecture PDFs and academic timetable files. "
            "Review the extracted text before relying on it.",
            "ارفعي ملفات المحاضرات والجداول الأكاديمية، "
            "وراجعي النص المستخرج قبل الاعتماد عليه."
        )
    )

    col1, col2 = st.columns(2)

    with col1:
        lecture_files = st.file_uploader(
            text("Lecture Files", "ملفات المحاضرات"),
            type=["pdf", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            key="lectures"
        )

    with col2:
        schedule_files = st.file_uploader(
            text("Timetable / Exam Files", "ملفات الجدول والامتحانات"),
            type=["pdf", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            key="schedule"
        )

    if st.button(
        "🔍 " + text("Extract Text", "استخراج النص"),
        type="primary",
        use_container_width=True
    ):

        files = (
            [(f, "Lecture") for f in (lecture_files or [])]
            + [(f, "Academic Schedule") for f in (schedule_files or [])]
        )

        if not files:
            st.warning(
                text("Choose files first.", "اختاري الملفات أولاً.")
            )

        for uploaded, kind in files:

            try:

                extracted = extract_file(uploaded)

                execute_query("""
                    INSERT INTO materials
                    (filename, subject, content, created)
                    VALUES (?, ?, ?, ?)
                """, (
                    uploaded.name,
                    kind,
                    extracted,
                    datetime.now().isoformat(timespec="minutes")
                ))

                if kind == "Academic Schedule":

                    execute_query("""
                        INSERT INTO timetable(id, content, confirmed)
                        VALUES(1, ?, 0)
                        ON CONFLICT(id)
                        DO UPDATE SET
                        content=excluded.content,
                        confirmed=0
                    """, (extracted,))

                st.success(uploaded.name + " ✓")

            except Exception as error:
                st.error(f"{uploaded.name}: {error}")

    st.caption(
        "Note: scanned PDF pages require OCR. "
        "Normal text-based PDFs can be extracted directly."
    )


# =====================================================
# 12. MY MATERIALS
# =====================================================

elif page == "Materials":

    st.title("📚 " + text("My Materials", "ملفاتي الدراسية"))

    search = st.text_input(
        text("Search your materials", "ابحثي في ملفاتك")
    )

    materials = fetch_all("""
        SELECT id, filename, subject, content, created
        FROM materials
        ORDER BY id DESC
    """)

    if not materials:
        st.info(
            text("No materials uploaded yet.", "لم يتم رفع ملفات بعد.")
        )

    for material in materials:

        material_id, filename, subject, content, created = material

        if search and search.lower() not in (
            filename + subject + content
        ).lower():
            continue

        with st.expander(f"📄 {filename}"):

            st.caption(f"{subject} · {created}")

            edited_text = st.text_area(
                "Extracted Text",
                content,
                height=250,
                key=f"material_{material_id}"
            )

            if st.button(
                "Save Corrections",
                key=f"save_material_{material_id}"
            ):

                execute_query(
                    "UPDATE materials SET content=? WHERE id=?",
                    (edited_text, material_id)
                )

                st.success("Saved.")

            if st.button(
                "Delete Material",
                key=f"delete_material_{material_id}"
            ):

                execute_query(
                    "DELETE FROM materials WHERE id=?",
                    (material_id,)
                )

                st.rerun()


# =====================================================
# 13. ACADEMIC TIMETABLE
# =====================================================

elif page == "Timetable":

    st.title("🗓️ " + text("Academic Timetable", "الجدول الأكاديمي"))

    timetable = fetch_one(
        "SELECT content, confirmed FROM timetable WHERE id=1"
    )

    if timetable:

        corrected = st.text_area(
            text(
                "Review and correct your extracted timetable",
                "راجعي وصححي نص الجدول المستخرج"
            ),
            timetable[0],
            height=320
        )

        if st.button(
            text("Confirm Timetable", "تأكيد الجدول"),
            type="primary"
        ):

            execute_query("""
                UPDATE timetable
                SET content=?, confirmed=1
                WHERE id=1
            """, (corrected,))

            st.success(
                text("Timetable confirmed.", "تم تأكيد الجدول.")
            )

        st.warning(
            text(
                "The extracted timetable is stored as text. "
                "Automatic conversion into calendar events is not enabled yet.",
                "يتم حفظ الجدول كنص للمراجعة. "
                "التحويل التلقائي إلى مواعيد داخل التقويم غير مفعّل بعد."
            )
        )

    else:

        st.info(
            text(
                "Upload your academic timetable first.",
                "ارفعي الجدول الأكاديمي أولاً."
            )
        )


# =====================================================
# 14. SMART WEEKLY PLANNER
# =====================================================

elif page == "Planner":

    st.title("📅 " + text("Smart Weekly Planner", "المخطط الأسبوعي الذكي"))

    st.caption(
        text(
            "Sessions: 30, 60, 90 or 120 minutes. "
            "15-minute breaks. Maximum 3 subjects per day.",
            "الجلسات: 30 أو 60 أو 90 أو 120 دقيقة. "
            "راحة 15 دقيقة. بحد أقصى 3 مواد يومياً."
        )
    )

    with st.form("add_subject_form", clear_on_submit=True):

        subject_name = st.text_input(
            text("Subject Name", "اسم المادة")
        )

        c1, c2 = st.columns(2)

        with c1:
            difficulty = st.selectbox(
                text("Difficulty", "الصعوبة"),
                ["Easy", "Medium", "Hard"]
            )

        with c2:
            priority = st.selectbox(
                text("Priority", "الأولوية"),
                ["Low", "Normal", "High"]
            )

        exam_date = st.date_input(
            text("Exam Date", "تاريخ الامتحان"),
            value=None
        )

        add_subject = st.form_submit_button(
            "➕ " + text("Add Subject", "إضافة مادة")
        )

        if add_subject:

            if not subject_name.strip():

                st.error(
                    text("Enter a subject name.", "اكتبي اسم المادة.")
                )

            else:

                try:

                    execute_query("""
                        INSERT INTO subjects
                        (name, difficulty, priority, exam_date)
                        VALUES (?, ?, ?, ?)
                    """, (
                        subject_name.strip(),
                        difficulty,
                        priority,
                        exam_date.isoformat() if exam_date else ""
                    ))

                    st.success(
                        text("Subject added.", "تمت إضافة المادة.")
                    )

                    st.rerun()

                except sqlite3.IntegrityError:

                    st.error(
                        text("Subject already exists.", "المادة موجودة بالفعل.")
                    )

    subjects = get_subjects()

    if not subjects.empty:

        st.subheader(text("Your Subjects", "موادك الدراسية"))

        st.dataframe(
            subjects.drop(columns=["ID"]),
            use_container_width=True,
            hide_index=True
        )

        hours = st.slider(
            text("Daily Study Hours", "ساعات المذاكرة اليومية"),
            1, 12,
            int(get_profile()["daily_hours"])
        )

        if st.button(
            "✨ " + text("Generate Weekly Plan", "إنشاء الجدول الأسبوعي"),
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

            for _, subject in subjects.iterrows():

                weight = (
                    difficulty_weight[subject["Difficulty"]] * 0.5
                    + priority_weight[subject["Priority"]] * 0.5
                )

                if subject["Exam Date"]:

                    try:
                        days_left = (
                            date.fromisoformat(subject["Exam Date"])
                            - date.today()
                        ).days

                        if 0 <= days_left <= 14:
                            weight += (15 - days_left) / 5

                    except ValueError:
                        pass

                items.append({
                    "name": subject["Subject"],
                    "weight": weight
                })

            total_weight = sum(
                item["weight"] for item in items
            )

            remaining = {
                item["name"]: max(
                    0.5,
                    round(
                        (
                            hours * 7
                            * item["weight"]
                            / total_weight
                        ) * 2
                    ) / 2
                )
                for item in items
            }

            today = date.today()

            # Start from the next Saturday
            days_until_saturday = (5 - today.weekday()) % 7

            if days_until_saturday == 0:
                days_until_saturday = 7

            week_start = today + timedelta(
                days=days_until_saturday
            )

            generated = []

            for day_index, day_name in enumerate(DAYS):

                current_date = week_start + timedelta(
                    days=day_index
                )

                used_hours = 0
                used_subjects = set()
                minute_of_day = 9 * 60

                while used_hours + 0.5 <= hours:

                    choices = [
                        item for item in items
                        if remaining[item["name"]] >= 0.5
                        and item["name"] not in used_subjects
                    ]

                    if not choices:
                        break

                    chosen = max(
                        choices,
                        key=lambda x: (
                            x["weight"],
                            remaining[x["name"]]
                        )
                    )

                    duration = min(
                        2,
                        hours - used_hours,
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

            execute_query("DELETE FROM sessions")

            with db_connection() as conn:

                for row in generated:

                    conn.execute("""
                        INSERT INTO sessions
                        (day, session_date, start_time,
                         subject, duration, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, row)

            st.success(
                text("Your weekly plan is ready!", "تم إنشاء جدولك الأسبوعي!")
            )

            st.rerun()

    sessions = get_sessions()

    if not sessions.empty:

        st.divider()

        st.subheader(text("Your Weekly Schedule", "جدولك الأسبوعي"))

        st.dataframe(
            sessions.drop(columns=["ID"]),
            use_container_width=True,
            hide_index=True
        )

        csv_data = sessions.drop(
            columns=["ID"]
        ).to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            "⬇️ " + text("Download CSV", "تحميل الجدول"),
            csv_data,
            "weekly_study_plan.csv",
            "text/csv"
        )

        pending = sessions[
            sessions["Status"] == "Pending"
        ]

        if not pending.empty:

            selected = st.multiselect(
                text(
                    "Select completed sessions",
                    "اختاري الجلسات التي أنجزتيها"
                ),
                pending["ID"].tolist()
            )

            if st.button(
                "✅ " + text("Mark as Completed", "تحديد كمكتملة")
            ):

                for session_id in selected:

                    execute_query("""
                        UPDATE sessions
                        SET status='Completed'
                        WHERE id=? AND status='Pending'
                    """, (session_id,))

                    add_xp(f"session-{session_id}", 20)

                st.success(
                    text(
                        "Progress updated. XP is awarded once per session.",
                        "تم تحديث الإنجاز وإضافة النقاط مرة واحدة لكل جلسة."
                    )
                )

                st.rerun()

        if st.button(
            "🗑️ " + text("Clear Weekly Plan", "مسح الجدول الأسبوعي")
        ):

            execute_query("DELETE FROM sessions")
            st.rerun()


# =====================================================
# 15. AI STUDY BUDDY
# =====================================================

elif page == "Chat":

    st.title("🤖 " + text("AI Study Buddy", "مساعد الدراسة الذكي"))

    st.markdown(
        f"""
        <div class="robot-card">
            {ROBOT}
            <h3>Study Buddy</h3>
            <p>
                {text(
                    "Your friendly academic companion.",
                    "رفيقك الدراسي الذكي."
                )}
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.write(
        text(
            "Ask questions about your uploaded lecture materials.",
            "اسألي عن المحاضرات والملفات التي رفعتيها."
        )
    )

    materials = fetch_all("""
        SELECT filename, content
        FROM materials
    """)

    for role, message in st.session_state.chat_history:

        with st.chat_message(
            role,
            avatar="🤖" if role == "assistant" else "🧑‍🎓"
        ):
            st.markdown(message)

    question = st.chat_input(
        text(
            "Ask your study buddy...",
            "اسألي مساعد الدراسة..."
        )
    )

    if question:

        st.session_state.chat_history.append(
            ("user", question)
        )

        api_key = ""

        try:
            api_key = st.secrets.get("OPENAI_API_KEY", "")
        except Exception:
            api_key = os.getenv("OPENAI_API_KEY", "")

        answer = ""

        if api_key and OpenAI:

            try:

                client = OpenAI(api_key=api_key)

                context = "\n\n".join(
                    f"FILE: {filename}\n{content}"
                    for filename, content in materials
                )

                context = context[:25000]

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    temperature=0.2,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a careful bilingual study assistant. "
                                "Use uploaded materials as the main source. "
                                "If the answer is not in the materials, "
                                "clearly say so. Do not invent facts."
                            )
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Uploaded materials:\n{context}\n\n"
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

            for filename, content in materials:

                matching_lines = [
                    line.strip()
                    for line in content.splitlines()
                    if line.strip()
                    and any(
                        word in line.lower()
                        for word in keywords
                    )
                ]

                if matching_lines:

                    matches.append(
                        f"**{filename}**\n"
                        + "\n".join(matching_lines[:6])
                    )

            if matches:

                answer = "\n\n".join(matches[:4])

                answer += (
                    "\n\n*Note: this is keyword search. "
                    "Configure an OpenAI API key for AI-generated answers.*"
                )

            else:

                answer = text(
                    "I couldn't find the answer in your uploaded files. "
                    "Upload the relevant lecture or configure an OpenAI API key.",
                    "لم أجد الإجابة في الملفات المرفوعة. "
                    "ارفعي المحاضرة المناسبة أو أضيفي مفتاح OpenAI لتفعيل الشات الذكي."
                )

        st.session_state.chat_history.append(
            ("assistant", answer)
        )

        st.rerun()

    if st.button(
        text("Clear Chat", "مسح المحادثة")
    ):

        st.session_state.chat_history = []
        st.rerun()


# =====================================================
# 16. PROGRESS
# =====================================================

elif page == "Progress":

    st.title("📈 " + text("My Progress", "إنجازاتي"))

    xp = get_xp()
    level, next_level = get_level(xp)

    sessions = get_sessions()

    completed = 0
    completed_hours = 0

    if not sessions.empty:

        completed_rows = sessions[
            sessions["Status"] == "Completed"
        ]

        completed = len(completed_rows)

        completed_hours = completed_rows["Hours"].sum()

    col1, col2, col3 = st.columns(3)

    col1.metric("⭐ Total XP", xp)
    col2.metric("🏅 Level", level[1])
    col3.metric("🤖 Buddy", level[2])

    st.metric(
        text("Completed Sessions", "الجلسات المكتملة"),
        completed
    )

    st.metric(
        text("Completed Study Hours", "ساعات المذاكرة المكتملة"),
        f"{completed_hours:.1f}"
    )

    if next_level:

        progress = (
            xp - level[0]
        ) / (
            next_level[0] - level[0]
        )

        st.progress(min(1, progress))

        st.caption(
            f"{next_level[0] - xp} XP to {next_level[1]}"
        )

    if not sessions.empty:

        st.subheader(
            text("Session Status", "حالة الجلسات")
        )

        chart_data = (
            sessions.groupby("Status")["Hours"]
            .sum()
        )

        st.bar_chart(chart_data)


# =====================================================
# 17. STRESS MANAGEMENT
# =====================================================

elif page == "Stress":

    st.title("🧠 " + text("Stress Management", "إدارة التوتر"))

    with st.form("stress_form"):

        stress = st.slider(
            text("Stress Level", "مستوى التوتر"),
            1, 10, 5
        )

        sleep = st.slider(
            text("Sleep Hours", "ساعات النوم"),
            0.0, 12.0, 7.0, 0.5
        )

        focus = st.slider(
            text("Focus Level", "مستوى التركيز"),
            1, 10, 6
        )

        workload = st.slider(
            text("Workload Level", "ضغط الدراسة"),
            1, 10, 5
        )

        submitted = st.form_submit_button(
            text("Analyze My Wellbeing", "تحليل حالتي"),
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

        execute_query("""
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
            text("Stress Indicator", "مؤشر التوتر"),
            f"{score}/10"
        )

        if score >= 7:

            st.warning(
                text(
                    "Your indicator is high. Reduce workload, take breaks, "
                    "and consider talking to someone you trust.",
                    "المؤشر مرتفع. قللي الضغط وخدي فواصل، "
                    "وفكري تتكلمي مع شخص تثقين به."
                )
            )

        elif score >= 4:

            st.info(
                text(
                    "Your indicator is moderate. Balance study and rest.",
                    "المؤشر متوسط. حاولي توازني بين المذاكرة والراحة."
                )
            )

        else:

            st.success(
                text(
                    "Your indicator is relatively low. Keep your routine balanced.",
                    "المؤشر منخفض نسبياً. حافظي على توازنك."
                )
            )

        if sleep < 7:
            st.write("🌙 " + text(
                "Try to improve your sleep routine.",
                "حاولي تحسين مواعيد نومك."
            ))

        if focus < 5:
            st.write("🎯 " + text(
                "Try shorter focused study sessions.",
                "جربي جلسات مذاكرة أقصر وأكثر تركيزاً."
            ))

        if workload > 7:
            st.write("📝 " + text(
                "Break large tasks into smaller steps.",
                "قسّمي المهام الكبيرة إلى خطوات أصغر."
            ))

        st.caption(
            text(
                "This is a self-check indicator, not a medical diagnosis.",
                "هذا تقييم ذاتي وليس تشخيصاً طبياً."
            )
        )


# =====================================================
# 18. HELP & GUIDE
# =====================================================

elif page == "Help":

    st.title("💡 " + text("Help & Guide", "المساعدة والإرشادات"))

    st.markdown("""
    ### How to use the application

    1. **Student Profile:** Add your academic information and available study hours.
    2. **Upload & Analyze:** Upload lecture PDFs and academic schedule files.
    3. **My Materials:** Review, search and correct extracted lecture text.
    4. **Academic Timetable:** Review and confirm the extracted timetable.
    5. **Weekly Planner:** Add subjects, difficulty, priority and exam dates.
    6. **AI Study Buddy:** Ask questions about your uploaded materials.
    7. **My Progress:** Complete sessions to earn XP.
    8. **Stress Management:** Check your stress, sleep and focus indicators.
    """)

    st.warning(
        "On Streamlit Cloud, local SQLite storage may not be durable "
        "across redeployments or environment recycling. Use an external "
        "database for reliable long-term cloud storage."
    )


# =====================================================
# 19. SETTINGS
# =====================================================

elif page == "Settings":

    st.title("⚙️ " + text("Settings", "الإعدادات"))

    language = st.selectbox(
        text("Language", "اللغة"),
        ["English", "العربية"],
        index=["English", "العربية"].index(LANGUAGE)
    )

    theme = st.selectbox(
        text("Appearance", "المظهر"),
        ["Dark", "Light"],
        index=["Dark", "Light"].index(THEME)
    )

    if st.button(
        text("Save Settings", "حفظ الإعدادات"),
        type="primary"
    ):

        execute_query("""
            UPDATE settings
            SET language=?, theme=?
            WHERE id=1
        """, (language, theme))

        st.success(
            text("Settings saved. Refreshing...", "تم الحفظ. جاري التحديث...")
        )

        st.rerun()

    st.divider()

    st.subheader("AI Study Buddy Configuration")

    st.write(
        text(
            "To enable AI-generated chat answers, add OPENAI_API_KEY "
            "to Streamlit Cloud → App Settings → Secrets.",
            "لتفعيل إجابات الشات بالذكاء الاصطناعي، أضيفي OPENAI_API_KEY "
            "في إعدادات التطبيق على Streamlit Cloud ثم Secrets."
        )
    )


# =====================================================
# 20. FOOTER
# =====================================================

st.divider()

st.markdown(
    f"""
    <div class="footer">
        SMART STUDENT ASSISTANT
        <br>
        ACADEMIC & STRESS MANAGEMENT
    </div>
    """,
    unsafe_allow_html=True
)

