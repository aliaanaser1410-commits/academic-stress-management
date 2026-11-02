

import streamlit as st
import sqlite3
import json
from pathlib import Path
from datetime import date, datetime, timedelta

import pandas as pd

# =========================================================
# STUDY BUDDY - SMART STUDENT EXPERT SYSTEM
# =========================================================

st.set_page_config(
    page_title="Study Buddy | Expert System",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = Path(__file__).with_name("study_buddy.db")

# =========================================================
# DATABASE
# =========================================================

def connect():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_database():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS sb_settings (
                id INTEGER PRIMARY KEY CHECK(id=1),
                name TEXT DEFAULT '',
                accent TEXT DEFAULT '#8956E8',
                mode TEXT DEFAULT 'Dark',
                language TEXT DEFAULT 'English',
                daily_hours REAL DEFAULT 3
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS sb_subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                difficulty INTEGER,
                priority INTEGER,
                exam_date TEXT
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS sb_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_date TEXT,
                subject TEXT,
                start_time TEXT,
                duration REAL,
                status TEXT DEFAULT 'Pending'
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS sb_assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                stress INTEGER,
                sleep REAL,
                focus INTEGER,
                workload INTEGER,
                exam_days INTEGER,
                risk TEXT,
                rules TEXT
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS sb_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                subject TEXT,
                content TEXT,
                uploaded_at TEXT
            )
        """)

        con.execute("INSERT OR IGNORE INTO sb_settings(id) VALUES(1)")


init_database()


def get_settings():
    with connect() as con:
        return dict(con.execute(
            "SELECT * FROM sb_settings WHERE id=1"
        ).fetchone())


def save_settings(name, accent, mode, language, hours):
    with connect() as con:
        con.execute("""
            UPDATE sb_settings
            SET name=?, accent=?, mode=?, language=?, daily_hours=?
            WHERE id=1
        """, (name, accent, mode, language, hours))


def query(sql, params=()):
    with connect() as con:
        return [dict(r) for r in con.execute(sql, params).fetchall()]


def execute(sql, params=()):
    with connect() as con:
        cur = con.execute(sql, params)
        return cur.lastrowid


settings = get_settings()

# =========================================================
# THEME SETTINGS
# =========================================================

THEMES = {
    "Purple": "#8956E8",
    "Blue": "#3988E8",
    "Pink": "#DB65A6",
    "Green": "#269C7A",
    "Orange": "#E58B42",
    "Teal": "#269CA5",
    "Red": "#D95765",
    "Indigo": "#5965D9"
}

accent = settings["accent"]
mode = settings["mode"]

dark = mode == "Dark"

background = "#171426" if dark else "#F6F4FB"
surface = "#211D35" if dark else "#FFFFFF"
text_color = "#F7F3FF" if dark else "#26213A"
muted = "#B8B1CA" if dark else "#777187"
border = "#39324F" if dark else "#E7E1F0"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Cairo:wght@400;600;700;800&display=swap');

html, body, [class*="css"] {{
    font-family: Inter, Cairo, sans-serif;
}}

.stApp {{
    background: {background};
    color: {text_color};
}}

.block-container {{
    padding-top: 1.6rem;
    max-width: 1450px;
}}

section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg,#17132B,#282047);
}}

section[data-testid="stSidebar"] * {{
    color: #FFFFFF !important;
}}

section[data-testid="stSidebar"] .stButton button {{
    background: rgba(255,255,255,.07);
    border: 1px solid rgba(255,255,255,.10);
    color: white;
    border-radius: 12px;
    text-align: left;
}}

section[data-testid="stSidebar"] .stButton button:hover {{
    background: {accent};
}}

.stButton button[kind="primary"] {{
    background: {accent};
    border: none;
    color: white;
    border-radius: 12px;
}}

.hero {{
    background: linear-gradient(115deg,#39256F,{accent});
    padding: 30px;
    border-radius: 24px;
    color: white;
    margin-bottom: 24px;
}}

.hero h1 {{
    color: white;
    font-size: 32px;
}}

.hero p {{
    color: #EEE7FF;
}}

.card {{
    background: {surface};
    border: 1px solid {border};
    border-radius: 18px;
    padding: 20px;
    margin-bottom: 12px;
}}

.metric {{
    font-size: 30px;
    font-weight: 800;
    color: {accent};
}}

.muted {{
    color: {muted};
    font-size: 13px;
}}

.rule {{
    background: {surface};
    border: 1px solid {border};
    border-left: 4px solid {accent};
    border-radius: 14px;
    padding: 17px;
    margin: 10px 0;
}}

h1, h2, h3 {{
    color: {text_color};
}}

</style>
""", unsafe_allow_html=True)

# =========================================================
# EXPERT SYSTEM - KNOWLEDGE BASE
# =========================================================

KNOWLEDGE_BASE = [

    {
        "id": "R01",
        "name": "High Stress",
        "condition": lambda x:
            x["stress"] >= 8,
        "recommendation":
            "خففي ضغط المذاكرة وابدئي بالمهام الأكثر أهمية.",
        "reason":
            "مستوى التوتر مرتفع.",
        "action":
            "جلسات قصيرة مع فواصل منتظمة."
    },

    {
        "id": "R02",
        "name": "Low Sleep",
        "condition": lambda x:
            x["sleep"] < 6,
        "recommendation":
            "حاولي تحسين ساعات النوم قبل زيادة ساعات المذاكرة.",
        "reason":
            "عدد ساعات النوم أقل من المستوى المستهدف.",
        "action":
            "تجنبي السهر الطويل وخففي حمل اليوم."
    },

    {
        "id": "R03",
        "name": "Low Focus",
        "condition": lambda x:
            x["focus"] <= 3,
        "recommendation":
            "ابدئي بمهمة صغيرة وسهلة لتستعيدي تركيزك.",
        "reason":
            "مستوى التركيز منخفض.",
        "action":
            "جلسة 30 دقيقة ثم راحة 10 دقائق."
    },

    {
        "id": "R04",
        "name": "High Workload",
        "condition": lambda x:
            x["workload"] >= 8,
        "recommendation":
            "رتبي المهام حسب الأولوية ولا تحاولي إنهاء كل شيء مرة واحدة.",
        "reason":
            "حجم المهام مرتفع.",
        "action":
            "اختاري أهم 2 أو 3 مهام."
    },

    {
        "id": "R05",
        "name": "Exam Approaching",
        "condition": lambda x:
            x["exam_days"] <= 3,
        "recommendation":
            "ركزي على المادة التي اقترب موعد امتحانها.",
        "reason":
            "يوجد امتحان خلال ثلاثة أيام أو أقل.",
        "action":
            "مراجعة وحل أسئلة وتحديد نقاط الضعف."
    },

    {
        "id": "R06",
        "name": "Good Study Condition",
        "condition": lambda x:
            x["stress"] <= 5
            and x["sleep"] >= 7
            and x["focus"] >= 6,
        "recommendation":
            "حالتك مناسبة لجلسات مذاكرة منتظمة.",
        "reason":
            "النوم والتركيز جيدان والتوتر منخفض نسبيًا.",
        "action":
            "ابدئي بالمواد الأصعب."
    }
]


def inference_engine(facts):
    """
    Forward-style rule evaluation:
    Student facts -> IF conditions -> THEN conclusions
    """

    matched_rules = []

    for rule in KNOWLEDGE_BASE:
        if rule["condition"](facts):
            matched_rules.append(rule)

    if not matched_rules:
        matched_rules.append({
            "id": "R00",
            "name": "General Recommendation",
            "recommendation":
                "قسمي وقتك إلى جلسات واضحة وابدئي بأعلى مادة في الأولوية.",
            "reason":
                "لم تنطبق قاعدة متخصصة على بيانات التقييم الحالية.",
            "action":
                "حددي هدفًا صغيرًا لكل جلسة."
        })

    return matched_rules


def calculate_risk(stress, sleep, focus, workload):

    score = (
        stress * 0.35
        + (10 - min(sleep, 10)) * 0.20
        + (10 - focus) * 0.20
        + workload * 0.25
    )

    if score >= 7:
        return "High"

    if score >= 4.5:
        return "Moderate"

    return "Low"


# =========================================================
# SESSION STATE
# =========================================================

if "page" not in st.session_state:
    st.session_state.page = "Home"

if "last_result" not in st.session_state:
    st.session_state.last_result = None

if "chat" not in st.session_state:
    st.session_state.chat = [
        {
            "role": "assistant",
            "content": "أهلًا! أنا Study Buddy 🤖 اسأليني عن المذاكرة أو التوتر أو خطتك الدراسية."
        }
    ]


# =========================================================
# SIDEBAR NAVIGATION
# =========================================================

PAGES = [
    ("🏠", "Home"),
    ("👤", "Student Profile"),
    ("🧠", "Expert Assessment"),
    ("📚", "Knowledge Base"),
    ("📖", "My Materials"),
    ("🗓️", "Smart Planner"),
    ("🤖", "AI Study Buddy"),
    ("📊", "My Progress"),
    ("💜", "Stress Management"),
    ("⚙️", "Settings")
]

with st.sidebar:

    st.markdown("""
    <div style="text-align:center;padding:15px">
        <div style="font-size:55px">🤖</div>
        <h2 style="color:white">Study Buddy</h2>
        <p style="color:#C9BCEB">EXPERT SYSTEM</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    for icon, label in PAGES:

        if st.button(
            f"{icon}  {label}",
            key="nav_" + label,
            use_container_width=True
        ):
            st.session_state.page = label
            st.rerun()

    st.markdown("---")

    st.caption("Your Personal Academic Assistant")
    st.caption("Knowledge Base • Inference Engine")


page = st.session_state.page

# =========================================================
# GENERAL DATA
# =========================================================

subjects = query(
    "SELECT * FROM sb_subjects ORDER BY priority DESC"
)

sessions = query(
    "SELECT * FROM sb_sessions ORDER BY session_date,start_time"
)

completed = sum(
    1 for s in sessions
    if s["status"] == "Completed"
)

pending = sum(
    1 for s in sessions
    if s["status"] != "Completed"
)

study_hours = sum(
    float(s["duration"])
    for s in sessions
    if s["status"] == "Completed"
)

progress = (
    completed / len(sessions)
    if sessions else 0
)

# =========================================================
# HOME DASHBOARD
# =========================================================

if page == "Home":

    name = settings["name"] or "Student"

    st.markdown(f"""
    <div class="hero">
        <div style="font-size:13px">
            YOUR PERSONAL ACADEMIC EXPERT SYSTEM
        </div>
        <h1>Welcome back, {name} 👋</h1>
        <p>Your study journey, organized and guided by expert rules.</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)

    metrics = [
        ("📚 Subjects", len(subjects)),
        ("✅ Completed", completed),
        ("⏳ Pending", pending),
        ("⏱️ Study Hours", f"{study_hours:g}h")
    ]

    for col, (label, value) in zip(
        [c1, c2, c3, c4], metrics
    ):
        with col:
            st.markdown(f"""
            <div class="card">
                <div class="muted">{label}</div>
                <div class="metric">{value}</div>
            </div>
            """, unsafe_allow_html=True)

    left, right = st.columns([1.4, 1])

    with left:

        st.markdown("### 📈 Study Progress")

        st.markdown('<div class="card">', unsafe_allow_html=True)

        st.progress(progress)

        st.write(f"**{progress * 100:.0f}% Completed**")

        st.caption(
            "Your progress is based on completed study sessions."
        )

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("### ⚡ Quick Actions")

        a, b, c = st.columns(3)

        with a:
            if st.button("🧠 Assessment", use_container_width=True):
                st.session_state.page = "Expert Assessment"
                st.rerun()

        with b:
            if st.button("🗓️ Planner", use_container_width=True):
                st.session_state.page = "Smart Planner"
                st.rerun()

        with c:
            if st.button("🤖 Chat", use_container_width=True):
                st.session_state.page = "AI Study Buddy"
                st.rerun()

    with right:

        st.markdown("### 🔔 Upcoming Tasks")

        upcoming = [
            s for s in sessions
            if s["session_date"] >= date.today().isoformat()
            and s["status"] != "Completed"
        ][:5]

        if upcoming:

            for s in upcoming:

                st.markdown(f"""
                <div class="card">
                    <b>{s["subject"]}</b>
                    <div class="muted">
                        {s["session_date"]} · {s["start_time"]}
                        · {s["duration"]}h
                    </div>
                </div>
                """, unsafe_allow_html=True)

        else:
            st.info("No upcoming tasks. Build your study plan!")

    st.markdown("### 🧠 How the Expert System Works")

    a, b, c = st.columns(3)

    with a:
        st.markdown("""
        <div class="card">
            <h3>📚 Knowledge Base</h3>
            <p class="muted">
            Stores expert IF–THEN rules about studying and stress.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with b:
        st.markdown("""
        <div class="card">
            <h3>🧠 Inference Engine</h3>
            <p class="muted">
            Matches student facts against the knowledge base.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with c:
        st.markdown("""
        <div class="card">
            <h3>💡 Explanation</h3>
            <p class="muted">
            Explains which rules were activated and why.
            </p>
        </div>
        """, unsafe_allow_html=True)


# =========================================================
# STUDENT PROFILE
# =========================================================

elif page == "Student Profile":

    st.title("👤 Student Profile")

    st.write("Manage your academic information.")

    with st.form("profile_form"):

        name = st.text_input(
            "Student Name",
            settings["name"]
        )

        hours = st.number_input(
            "Daily Study Hours",
            min_value=0.5,
            max_value=16.0,
            value=float(settings["daily_hours"]),
            step=0.5
        )

        language = st.selectbox(
            "Language",
            ["English", "العربية"],
            index=0 if settings["language"] == "English" else 1
        )

        if st.form_submit_button("Save Profile", type="primary"):

            save_settings(
                name,
                settings["accent"],
                settings["mode"],
                language,
                hours
            )

            st.success("Profile saved successfully.")


# =========================================================
# EXPERT ASSESSMENT
# =========================================================

elif page == "Expert Assessment":

    st.title("🧠 Expert Assessment")

    st.write(
        "Answer these questions so the expert system can evaluate your condition."
    )

    with st.form("assessment_form"):

        c1, c2 = st.columns(2)

        with c1:

            stress = st.slider(
                "Stress Level",
                0, 10, 5
            )

            sleep = st.slider(
                "Sleep Hours",
                0.0, 12.0, 7.0, 0.5
            )

            focus = st.slider(
                "Focus Level",
                0, 10, 6
            )

        with c2:

            workload = st.slider(
                "Workload Level",
                0, 10, 5
            )

            exam_days = st.number_input(
                "Days Until Next Exam",
                min_value=0,
                max_value=365,
                value=7
            )

        submit = st.form_submit_button(
            "Run Expert Assessment",
            type="primary"
        )

    if submit:

        facts = {
            "stress": stress,
            "sleep": sleep,
            "focus": focus,
            "workload": workload,
            "exam_days": int(exam_days)
        }

        matched = inference_engine(facts)

        risk = calculate_risk(
            stress, sleep, focus, workload
        )

        st.session_state.last_result = {
            "facts": facts,
            "rules": [r["id"] for r in matched],
            "risk": risk
        }

        execute("""
            INSERT INTO sb_assessments
            (created_at,stress,sleep,focus,workload,exam_days,risk,rules)
            VALUES(?,?,?,?,?,?,?,?)
        """, (
            datetime.now().isoformat(),
            stress,
            sleep,
            focus,
            workload,
            int(exam_days),
            risk,
            json.dumps([r["id"] for r in matched])
        ))

    result = st.session_state.last_result

    if result:

        st.markdown("### Your Assessment Result")

        c1, c2 = st.columns(2)

        c1.metric("Study Strain", result["risk"])
        c2.metric("Activated Rules", len(result["rules"]))

        for rule in inference_engine(result["facts"]):

            st.markdown(f"""
            <div class="rule">
                <b>{rule["id"]} · {rule["name"]}</b>
                <p>{rule["recommendation"]}</p>
                <div class="muted">
                    Why: {rule["reason"]}
                </div>
                <div class="muted">
                    Action: {rule["action"]}
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.caption(
            "Educational recommendations only; not a medical diagnosis."
        )


# =========================================================
# KNOWLEDGE BASE
# =========================================================

elif page == "Knowledge Base":

    st.title("📚 Knowledge Base")

    st.write(
        "These IF–THEN rules represent the system's stored expert knowledge."
    )

    for rule in KNOWLEDGE_BASE:

        st.markdown(f"""
        <div class="rule">
            <b>{rule["id"]} · {rule["name"]}</b>
            <p><b>IF:</b> {rule["reason"]}</p>
            <p><b>THEN:</b> {rule["recommendation"]}</p>
            <div class="muted">
                Suggested action: {rule["action"]}
            </div>
        </div>
        """, unsafe_allow_html=True)


# =========================================================
# MY MATERIALS
# =========================================================

elif page == "My Materials":

    st.title("📖 My Materials")

    st.write("Upload and organize your lecture files.")

    uploaded = st.file_uploader(
        "Upload PDF or TXT files",
        type=["pdf", "txt"],
        accept_multiple_files=True
    )

    subject_options = ["General"] + [
        s["name"] for s in subjects
    ]

    subject = st.selectbox(
        "Select Subject",
        subject_options
    )

    if uploaded and st.button("Save Files", type="primary"):

        for file in uploaded:

            content = ""

            if file.name.lower().endswith(".txt"):

                content = file.getvalue().decode(
                    "utf-8",
                    errors="ignore"
                )

            else:

                try:
                    import fitz

                    pdf = fitz.open(
                        stream=file.getvalue(),
                        filetype="pdf"
                    )

                    content = "\n".join(
                        page.get_text() for page in pdf
                    )

                except ImportError:
                    content = (
                        "PDF uploaded. Install PyMuPDF "
                        "to extract its text."
                    )

                except Exception as e:
                    content = f"Could not extract PDF text: {e}"

            execute("""
                INSERT INTO sb_materials
                (filename,subject,content,uploaded_at)
                VALUES(?,?,?,?)
            """, (
                file.name,
                subject,
                content,
                datetime.now().isoformat()
            ))

        st.success("Files saved successfully!")
        st.rerun()

    materials = query(
        "SELECT id,filename,subject,uploaded_at FROM sb_materials ORDER BY id DESC"
    )

    if materials:

        st.dataframe(
            pd.DataFrame(materials),
            use_container_width=True,
            hide_index=True
        )

        selected = st.selectbox(
            "Preview File",
            ["Select"] + [
                f'{m["id"]} - {m["filename"]}'
                for m in materials
            ]
        )

        if selected != "Select":

            material_id = int(selected.split(" - ")[0])

            item = query(
                "SELECT content FROM sb_materials WHERE id=?",
                (material_id,)
            )

            st.text_area(
                "Extracted Text",
                item[0]["content"],
                height=250
            )

    else:
        st.info("No materials uploaded yet.")


# =========================================================
# SMART PLANNER
# =========================================================

elif page == "Smart Planner":

    st.title("🗓️ Smart Weekly Planner")

    st.write(
        "Add your subjects and generate a basic weekly study schedule."
    )

    with st.form("subject_form"):

        name = st.text_input("Subject Name")

        c1, c2 = st.columns(2)

        with c1:
            difficulty = st.slider(
                "Difficulty", 1, 5, 3
            )

        with c2:
            priority = st.slider(
                "Priority", 1, 5, 3
            )

        exam = st.date_input(
            "Exam Date",
            value=date.today() + timedelta(days=14)
        )

        add_subject = st.form_submit_button(
            "Add Subject",
            type="primary"
        )

    if add_subject:

        if name.strip():

            execute("""
                INSERT INTO sb_subjects
                (name,difficulty,priority,exam_date)
                VALUES(?,?,?,?)
            """, (
                name.strip(),
                difficulty,
                priority,
                exam.isoformat()
            ))

            st.success("Subject added.")
            st.rerun()

        else:
            st.warning("Enter a subject name.")

    subjects = query(
        "SELECT * FROM sb_subjects ORDER BY priority DESC,difficulty DESC"
    )

    if subjects:

        st.markdown("### Your Subjects")

        st.dataframe(
            pd.DataFrame(subjects),
            use_container_width=True,
            hide_index=True
        )

        if st.button("Generate 7-Day Plan", type="primary"):

            today = date.today()

            with connect() as con:
                con.execute("""
                    DELETE FROM sb_sessions
                    WHERE session_date >= ?
                    AND status = 'Pending'
                """, (today.isoformat(),))

            daily_hours = float(get_settings()["daily_hours"])

            for day_number in range(7):

                current_day = today + timedelta(
                    days=day_number
                )

                available = daily_hours
                start_hour = 9

                # Maximum 3 subjects per day
                daily_subjects = subjects[:3]

                for subject in daily_subjects:

                    if available < 0.5:
                        break

                    duration = min(1.0, available)

                    start = f"{start_hour:02d}:00"

                    execute("""
                        INSERT INTO sb_sessions
                        (session_date,subject,start_time,duration,status)
                        VALUES(?,?,?,?,?)
                    """, (
                        current_day.isoformat(),
                        subject["name"],
                        start,
                        duration,
                        "Pending"
                    ))

                    available -= duration
                    start_hour += int(duration) + 1

            st.success("Your weekly plan has been generated.")
            st.rerun()

    st.markdown("### Study Sessions")

    sessions = query("""
        SELECT * FROM sb_sessions
        ORDER BY session_date,start_time
    """)

    if sessions:

        for session in sessions:

            a, b, c, d = st.columns([2, 2, 1, 1])

            a.write(f"**{session['subject']}**")

            b.caption(
                f"{session['session_date']} · {session['start_time']}"
            )

            c.write(f"{session['duration']}h")

            if session["status"] == "Completed":

                d.success("Completed")

            elif d.button(
                "Complete",
                key=f"done_{session['id']}"
            ):

                execute("""
                    UPDATE sb_sessions
                    SET status='Completed'
                    WHERE id=?
                """, (session["id"],))

                st.rerun()

    else:
        st.info("Add subjects and generate your plan.")


# =========================================================
# AI STUDY BUDDY - RULE BASED CHAT
# =========================================================

elif page == "AI Study Buddy":

    st.title("🤖 AI Study Buddy")

    st.write(
        "Talk to your academic expert assistant."
    )

    for message in st.session_state.chat:

        with st.chat_message(
            message["role"],
            avatar="🤖" if message["role"] == "assistant" else "🧑‍🎓"
        ):

            st.markdown(message["content"])

    prompt = st.chat_input(
        "Ask me about your study plan, focus or stress..."
    )

    if prompt:

        st.session_state.chat.append({
            "role": "user",
            "content": prompt
        })

        lower = prompt.lower()

        if any(word in lower for word in [
            "stress", "توتر", "ضغط", "قلق"
        ]):

            result = st.session_state.last_result

            if result:

                rules = inference_engine(result["facts"])

                answer = "\n\n".join([
                    f"**{r['name']}**\n"
                    f"{r['recommendation']}\n"
                    f"Reason: {r['reason']}"
                    for r in rules
                ])

            else:

                answer = (
                    "ابدئي بصفحة Expert Assessment "
                    "وسجلي مستوى التوتر والنوم والتركيز."
                )

        elif any(word in lower for word in [
            "plan", "schedule", "جدول", "خطة", "مذاكرة"
        ]):

            answer = (
                f"عندك {len(subjects)} مادة و"
                f"{pending} جلسة معلقة. "
                "افتحي Smart Planner لتنظيم جدولك."
            )

        elif any(word in lower for word in [
            "rule", "expert", "قاعدة", "استدلال"
        ]):

            answer = (
                "النظام يستخدم Knowledge Base تحتوي على "
                "قواعد IF–THEN. يقوم Inference Engine "
                "بمطابقة بيانات الطالب مع القواعد، "
                "ثم يعرض التوصية وسببها."
            )

        elif any(word in lower for word in [
            "sleep", "نوم", "نمت"
        ]):

            answer = (
                "النوم جزء مهم من تنظيم المذاكرة. "
                "سجلي عدد ساعات نومك في Expert Assessment "
                "للحصول على توصية مبنية على قواعد النظام."
            )

        else:

            answer = (
                "أقدر أساعدك في تنظيم المذاكرة والتوتر "
                "والتركيز وفهم النظام الخبير. "
                "جربي تشغيل Expert Assessment للحصول "
                "على توصية شخصية."
            )

        st.session_state.chat.append({
            "role": "assistant",
            "content": answer
        })

        st.rerun()

    st.caption(
        "Current chat uses rule-based responses. "
        "Generative AI API integration is a separate future feature."
    )


# =========================================================
# MY PROGRESS
# =========================================================

elif page == "My Progress":

    st.title("📊 My Progress")

    a, b, c = st.columns(3)

    a.metric("Completed Sessions", completed)

    b.metric("Pending Sessions", pending)

    c.metric("Study Hours", f"{study_hours:g}h")

    st.markdown("### Overall Progress")

    st.progress(progress)

    st.write(f"{progress * 100:.1f}% completed")

    if sessions:

        df = pd.DataFrame(sessions)

        df["session_date"] = pd.to_datetime(
            df["session_date"]
        )

        summary = df.groupby("session_date").agg(
            Total=("id", "count"),
            Completed=(
                "status",
                lambda x: (x == "Completed").sum()
            )
        )

        st.markdown("### Daily Sessions")

        st.line_chart(summary)

    else:
        st.info("Your progress will appear after creating a study plan.")


# =========================================================
# STRESS MANAGEMENT
# =========================================================

elif page == "Stress Management":

    st.title("💜 Stress Management")

    st.write(
        "Personalized suggestions based on your latest assessment."
    )

    latest = query("""
        SELECT * FROM sb_assessments
        ORDER BY id DESC LIMIT 1
    """)

    if latest:

        item = latest[0]

        st.metric(
            "Latest Study Strain",
            item["risk"]
        )

        rules = json.loads(item["rules"])

        for rule_id in rules:

            matched = [
                r for r in KNOWLEDGE_BASE
                if r["id"] == rule_id
            ]

            for rule in matched:

                st.markdown(f"""
                <div class="rule">
                    <b>{rule["name"]}</b>
                    <p>{rule["recommendation"]}</p>
                    <div class="muted">
                        {rule["reason"]}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    else:

        st.info(
            "Complete Expert Assessment to receive suggestions."
        )

    st.warning(
        "These educational suggestions are not medical advice."
    )


# =========================================================
# SETTINGS - CUSTOM THEMES
# =========================================================

elif page == "Settings":

    st.title("⚙️ Settings")

    st.markdown("### 🎨 Appearance & Themes")

    theme_names = list(THEMES.keys())

    current_theme = next(
        (
            name for name, color in THEMES.items()
            if color == settings["accent"]
        ),
        "Purple"
    )

    with st.form("appearance_form"):

        selected_theme = st.selectbox(
            "Choose your favorite color",
            theme_names,
            index=theme_names.index(current_theme)
        )

        selected_mode = st.radio(
            "Display Mode",
            ["Dark", "Light"],
            index=0 if settings["mode"] == "Dark" else 1,
            horizontal=True
        )

        st.markdown(
            f"""
            <div class="card">
                <b>Theme Preview</b>
                <div style="
                    background:{THEMES[selected_theme]};
                    padding:20px;
                    border-radius:14px;
                    color:white;
                    margin-top:12px;
                ">
                    <h3 style="color:white">Study Buddy 🤖</h3>
                    Your personal study assistant
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        save_theme = st.form_submit_button(
            "Save Appearance",
            type="primary"
        )

    if save_theme:

        save_settings(
            settings["name"],
            THEMES[selected_theme],
            selected_mode,
            settings["language"],
            settings["daily_hours"]
        )

        st.success(
            "Theme saved! The new appearance will be applied after rerun."
        )

        st.rerun()

    st.markdown("---")

    st.markdown("### 🌐 Language")

    st.write(
        "Current language: " + settings["language"]
    )

    st.markdown("### ℹ️ About")

    st.markdown("""
    <div class="card">
        <h3>Study Buddy</h3>
        <p class="muted">
        Academic & Stress Management Expert System
        </p>
        <p>
        Built using Python, Streamlit, SQLite,
        Knowledge Base and Rule-Based Inference.
        </p>
    </div>
    """, unsafe_allow_html=True)


# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.markdown(
    """
    <div style="text-align:center;color:gray;font-size:12px">
        STUDY BUDDY · ACADEMIC & STRESS MANAGEMENT EXPERT SYSTEM
    </div>
    """,
    unsafe_allow_html=True
)
