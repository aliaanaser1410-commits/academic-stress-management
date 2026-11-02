from google import genai
import math
from pathlib import Path
import pypdf
import io

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

# --------------------------------------------------
# Theme config
# --------------------------------------------------
try:
    _cfg_dir = Path(__file__).resolve().parent / ".streamlit"
    _cfg = _cfg_dir / "config.toml"
    if not _cfg.exists():
        _cfg_dir.mkdir(exist_ok=True)
        _cfg.write_text(
            '[theme]\n'
            'base = "dark"\n'
            'primaryColor = "#6366f1"\n'
            'backgroundColor = "#0b0f19"\n'
            'secondaryBackgroundColor = "#121826"\n'
            'textColor = "#e5e7eb"\n'
            'font = "sans serif"\n',
            encoding="utf-8",
        )
except Exception:
    pass

# ==================================================
# 1. PAGE CONFIG
# ==================================================
st.set_page_config(
    page_title="Academic & Stress Management",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ==================================================
# 2. SESSION STATE
# ==================================================
defaults = {
    "step": 0,
    "language": "English",
    "theme_mode": "Dark",
    "student_name": "",
    "study_level": "University student",
    "daily_hours": 4,
    "exam_days": 14,
    "study_style": "Short focused sessions",
    "stress_score": 5,
    "sleep_score": 6,
    "focus_score": 6,
    "workload": "Moderate",
    "subject_count": 3,
    "missed_hours": 0,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

MAX_SUBJECTS = 10

for key in defaults:
    st.session_state[key] = st.session_state[key]

for i in range(MAX_SUBJECTS):
    for prefix in ("subject_name_", "difficulty_", "priority_"):
        k = f"{prefix}{i}"
        if k in st.session_state:
            st.session_state[k] = st.session_state[k]

STEPS = ["Profile", "Assessment", "Planning", "Your plan"]
LAST_STEP = len(STEPS) - 1

WORKLOAD_SCORES = {
    "Not manageable": 10,
    "Difficult": 8,
    "Moderate": 5,
    "Manageable": 3,
    "Very manageable": 1,
}

ACCENT = "#6366f1"


def go_next():
    st.session_state.step = min(st.session_state.step + 1, LAST_STEP)


def go_back():
    st.session_state.step = max(st.session_state.step - 1, 0)


def compute_stress():
    raw = (
        0.50 * st.session_state.stress_score
        + 0.25 * (10 - st.session_state.sleep_score)
        + 0.15 * (10 - st.session_state.focus_score)
        + 0.10 * WORKLOAD_SCORES[st.session_state.workload]
    )
    return max(0, min(10, math.floor(raw + 0.5)))


def stress_level(score):
    if score <= 3:
        return "Low", "#34d399"
    if score <= 6:
        return "Moderate", "#fbbf24"
    return "High", "#f87171"


TRANSLATIONS = {
    "Smart Student Assistant": "مساعد الطالب الذكي",
    "Academic & Stress Management": "إدارة الدراسة والتوتر",
    "Academic &amp; Stress Management": "إدارة الدراسة والتوتر",
    "Plan your study time, organize your subjects, and get practical guidance for managing academic pressure.": "نظّم وقت مذاكرتك وموادك واحصل على إرشادات عملية للتعامل مع الضغط الدراسي.",
    "Profile": "البيانات الشخصية",
    "Assessment": "تقييم التوتر",
    "Planning": "تنظيم المذاكرة",
    "Your plan": "خطتك الدراسية",
    "Step 1 · Profile": "الخطوة 1 · البيانات الشخصية",
    "Let’s get to know you": "خلّينا نتعرّف عليك",
    "Enter your information to personalize your study plan.": "أدخل بياناتك لتخصيص خطة المذاكرة المناسبة لك.",
    "Student name": "اسم الطالب",
    "Enter your name": "اكتب اسمك",
    "Academic level": "المرحلة الدراسية",
    "University student": "طالب جامعي",
    "High school student": "طالب ثانوي",
    "Preparatory student": "طالب إعدادي",
    "Other": "أخرى",
    "Available study hours per day": "عدد ساعات المذاكرة المتاحة يوميًا",
    "Preferred study style": "أسلوب المذاكرة المفضل",
    "Short focused sessions": "جلسات قصيرة بتركيز",
    "Long focused sessions": "جلسات طويلة بتركيز",
    "Mix of both": "مزيج من الاثنين",
    "Days remaining until exam or deadline": "الأيام المتبقية للامتحان أو الموعد النهائي",
    "Tip.": "نصيحة.",
    "A balanced and realistic routine is easier to maintain than an overloaded schedule.": "الجدول المتوازن والواقعي أسهل في الالتزام من الجدول المزدحم.",
    "Continue": "التالي",
    "Please enter your name before continuing.": "من فضلك اكتبي اسمك قبل المتابعة.",
    "Step 2 · Well-being": "الخطوة 2 · حالتك العامة",
    "How are you feeling?": "كيف تشعر الآن؟",
    "Rate your current experience. This is a self-reflection tool, not a medical diagnosis.": "قيّم حالتك الحالية. هذا للتقييم الذاتي وليس تشخيصًا طبيًا.",
    "How stressed do you feel about studying?": "ما مستوى التوتر الذي تشعر به بسبب المذاكرة؟",
    "How well can you concentrate?": "ما مدى قدرتك على التركيز؟",
    "How well are you sleeping?": "ما مدى جودة نومك؟",
    "How manageable is your workload?": "ما مدى قدرتك على التعامل مع عبء الدراسة؟",
    "Not manageable": "صعب جدًا",
    "Difficult": "صعب",
    "Moderate": "متوسط",
    "Manageable": "يمكن التعامل معه",
    "Very manageable": "يمكن التعامل معه بسهولة",
    "Your stress estimate": "تقدير مستوى التوتر",
    "Calculated from your answers using simple weighted rules. It is an organizational aid, not a validated clinical scale.": "تم حسابه من إجاباتك باستخدام قواعد بسيطة. وهو أداة تنظيمية وليس مقياسًا طبيًا معتمدًا.",
    "Step 3 · Study planning": "الخطوة 3 · تنظيم المذاكرة",
    "Organize your subjects": "نظّم موادك الدراسية",
    "Add each subject and set its difficulty and priority.": "أضف كل مادة وحدد مستوى صعوبتها وأهميتها.",
    "How many subjects do you have?": "كم مادة لديك؟",
    "SUBJECT": "المادة",
    "Subject name": "اسم المادة",
    "Difficulty": "الصعوبة",
    "Easy": "سهلة",
    "Medium": "متوسطة",
    "Hard": "صعبة",
    "Priority": "الأولوية",
    "Normal": "عادية",
    "Important": "مهمة",
    "Very important": "مهمة جدًا",
    "How it works.": "كيف تعمل الخطة.",
    "Harder and more important subjects receive a larger share of your available study hours.": "المواد الأصعب والأكثر أهمية تحصل على وقت مذاكرة أكبر.",
    "Generate plan": "إنشاء الخطة",
    "Please enter your subjects first.": "من فضلك أدخل المواد أولًا.",
    "Back to planning": "العودة لتنظيم المذاكرة",
    "Study plan for": "خطة المذاكرة لـ",
    "Daily study": "المذاكرة يوميًا",
    "hrs": "ساعات",
    "Planning window": "مدة التخطيط",
    "days": "يوم",
    "Total hours": "إجمالي الساعات",
    "Stress estimate": "تقدير التوتر",
    "Low": "منخفض",
    "High": "مرتفع",
    "Study hours allocation": "توزيع ساعات المذاكرة",
    "Daily study distribution": "توزيع المذاكرة اليومية",
    "Hours per day": "ساعات يوميًا",
    "Suggested daily timetable": "الجدول اليومي المقترح",
    "Study: ": "مذاكرة: ",
    "Short break": "استراحة قصيرة",
    "Long break / meal": "استراحة طويلة / وجبة",
    "This timetable runs late into the evening. Consider reducing your daily hours or starting earlier to protect your sleep.": "هذا الجدول يمتد لوقت متأخر. فكّر في تقليل ساعات المذاكرة أو البدء مبكرًا للحفاظ على نومك.",
    "Stress management tips": "نصائح لإدارة التوتر",
    "Keep your study routine consistent and balanced.": "حافظ على روتين مذاكرة ثابت ومتوازن.",
    "Review your notes regularly instead of cramming.": "راجع ملاحظاتك بانتظام بدلًا من المذاكرة المكثفة في آخر لحظة.",
    "Protect your sleep schedule and take regular breaks.": "حافظ على مواعيد نومك وخذ فترات راحة منتظمة.",
    "Break large tasks into smaller, manageable steps.": "قسّم المهام الكبيرة إلى خطوات صغيرة يمكن إنجازها.",
    "Try 25 minutes of focused work followed by a 5-minute break.": "جرّب 25 دقيقة من التركيز ثم استراحة لمدة 5 دقائق.",
    "Start with the most important task and leave room for flexibility.": "ابدأ بالمهمة الأكثر أهمية واترك مساحة للتغييرات.",
    "Focus on urgent tasks first and postpone non-essential work.": "ابدأ بالمهام العاجلة وأجّل ما ليس ضروريًا.",
    "Use short study sessions with frequent breaks.": "استخدم جلسات مذاكرة قصيرة مع استراحات متكررة.",
    "Make time for meals, rest, hydration, and sleep.": "خصص وقتًا للطعام والراحة وشرب الماء والنوم.",
    "Consider talking with someone you trust or your student support team.": "فكّر في التحدث مع شخص تثق به أو فريق دعم الطلاب.",
    "This tool offers study-planning suggestions, not medical advice or a clinical stress diagnosis.": "تقدم هذه الأداة اقتراحات لتنظيم المذاكرة، وليست نصيحة طبية أو تشخيصًا للتوتر.",
    "Export": "تصدير",
    "Download study plan": "تحميل خطة المذاكرة",
    "Download timetable": "تحميل الجدول اليومي",
    "Back": "السابق",
    "Start over": "البدء من جديد",
    "ACADEMIC &amp; STRESS MANAGEMENT EXPERT SYSTEM": "نظام خبير لإدارة الدراسة والتوتر",
    "☀️ Light theme": "☀️ الوضع الفاتح",
    "hours": "ساعات",
    "hours per day": "ساعات يوميًا",
    "minutes": "دقيقة",
    "🌙 Dark theme": "🌙 الوضع الداكن",
}

def tr(value):
    if not isinstance(value, str):
        return value
    if st.session_state.get("language", "English") != "Arabic":
        return value
    result = value
    for en, ar in sorted(TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True):
        result = result.replace(en, ar)
    return result

def html(markup):
    cleaned = "\n".join(line.strip() for line in markup.strip().splitlines())
    cleaned = tr(cleaned)
    st.markdown(cleaned, unsafe_allow_html=True)

# ==================================================
# 3. DESIGN SYSTEM
# ==================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root {
    --bg: #0b0f19; --surface: #111726; --surface-2: #0d1320;
    --border: #1f2937; --border-strong: #2b3648;
    --text: #e5e7eb; --muted: #94a3b8; --faint: #64748b;
    --accent: #6366f1; --accent-hover: #4f46e5;
}
html, body, .stApp, [class*="css"] { font-family: 'Inter', system-ui, sans-serif; }
.stApp { background: var(--bg); color: var(--text); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"], #MainMenu, footer { visibility: hidden; }
.block-container { max-width: 1040px; padding-top: 2.5rem; padding-bottom: 3rem; }
.app-header { padding-bottom: 22px; border-bottom: 1px solid var(--border); margin-bottom: 26px; }
.app-eyebrow { color: var(--accent); font-size: 12px; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; }
.app-title { font-size: 32px; font-weight: 700; margin: 8px 0 6px; color: #f8fafc; }
.app-sub { color: var(--muted); font-size: 15px; line-height: 1.6; max-width: 640px; }
.stepper { display: flex; align-items: center; margin-bottom: 26px; }
.step { display: flex; align-items: center; gap: 10px; }
.step .dot {
    width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 600; border: 1px solid var(--border-strong); color: var(--faint); background: transparent;
}
.step .name { font-size: 13px; font-weight: 500; color: var(--faint); white-space: nowrap; }
.step.done .dot { background: var(--accent); border-color: var(--accent); color: #fff; }
.step.done .name { color: var(--muted); }
.step.current .dot { border-color: var(--accent); color: #fff; box-shadow: 0 0 0 4px rgba(99,102,241,0.18); }
.step.current .name { color: #f8fafc; font-weight: 600; }
.step-line { flex: 1; height: 1px; background: var(--border-strong); margin: 0 14px; min-width: 18px; }
.step-line.done { background: var(--accent); }
.st-key-slide_card { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 32px; margin: 4px 0 20px; }
.card-eyebrow { color: var(--faint); font-size: 12px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; }
.card-title { font-size: 24px; font-weight: 700; margin: 6px 0 6px; color: #f8fafc; }
.muted { color: var(--muted); font-size: 14px; line-height: 1.7; }
.metric { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 18px 20px; height: 100%; }
.metric .label { color: var(--faint); font-size: 12px; font-weight: 600; text-transform: uppercase; }
.metric .value { font-size: 28px; font-weight: 700; margin-top: 8px; color: #f8fafc; }
.metric .unit { font-size: 14px; font-weight: 500; color: var(--muted); margin-left: 4px; }
.estimate { background: var(--surface-2); border: 1px solid var(--border); border-radius: 14px; padding: 20px 22px; margin-top: 18px; }
.estimate .row { display: flex; align-items: baseline; justify-content: space-between; }
.estimate .score { font-size: 30px; font-weight: 700; }
.estimate .score small { font-size: 15px; color: var(--faint); font-weight: 500; }
.estimate .badge { font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 999px; border: 1px solid; }
.bar { height: 6px; background: var(--border); border-radius: 999px; margin: 14px 0 12px; overflow: hidden; }
.bar > div { height: 100%; border-radius: 999px; }
.note { background: var(--surface-2); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px; margin: 18px 0 0; color: var(--muted); font-size: 14px; }
.tip { display: flex; gap: 16px; align-items: flex-start; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 14px 18px; margin: 10px 0; font-size: 14px; color: var(--text); }
.tip .num { color: var(--accent); font-weight: 700; font-size: 13px; min-width: 22px; }
.section-title { font-size: 18px; font-weight: 600; margin: 34px 0 12px; color: #f8fafc; }
.subject-label { font-size: 13px; font-weight: 600; color: var(--muted); margin-bottom: 4px; }
div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="textarea"] { background-color: var(--surface-2) !important; border-color: var(--border-strong) !important; border-radius: 10px !important; }
div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea { color: #f8fafc !important; }
.stButton > button, .stDownloadButton > button { width: 100%; min-height: 44px; border-radius: 10px; font-weight: 600; font-size: 14px; }
.stButton > button[kind="primary"] { background: var(--accent); border: 1px solid var(--accent); color: #fff; }
.stButton > button[kind="primary"]:hover { background: var(--accent-hover); }
.footer { text-align: center; color: var(--faint); font-size: 12px; padding-top: 8px; }
</style>
""", unsafe_allow_html=True)

toolbar_left, toolbar_right = st.columns([1, 1])
with toolbar_left:
    lang_label = "🌐 العربية" if st.session_state.language == "English" else "🌐 English"
    if st.button(lang_label, key="toggle_language"):
        st.session_state.language = "Arabic" if st.session_state.language == "English" else "English"
        st.rerun()

with toolbar_right:
    theme_label = "☀️ Light theme" if st.session_state.theme_mode == "Dark" else "🌙 Dark theme"
    if st.button(tr(theme_label), key="toggle_theme"):
        st.session_state.theme_mode = "Light" if st.session_state.theme_mode == "Dark" else "Dark"
        st.rerun()

if st.session_state.theme_mode == "Light":
    st.markdown("""
    <style>
    :root { --bg: #f4f6fb; --surface: #ffffff; --surface-2: #edf1f8; --border: #d8deea; --border-strong: #c4ccdc; --text: #172033; --muted: #475569; --faint: #64748b; }
    .stApp { background: var(--bg) !important; color: var(--text) !important; }
    h1, h2, h3, h4, p, label, span { color: var(--text); }
    .app-title, .card-title, .step.current .name { color: #172033 !important; }
    .st-key-slide_card, .metric, .tip { background: #ffffff !important; }
    .estimate, .note { background: #edf1f8 !important; }
    </style>
    """, unsafe_allow_html=True)

if st.session_state.language == "Arabic":
    st.markdown("""
    <style>
    .stApp { direction: rtl; }
    .block-container { text-align: right; }
    .app-header, .card-title, .card-eyebrow, .muted, .note, .tip { text-align: right; }
    .stepper { direction: rtl; }
    </style>
    """, unsafe_allow_html=True)

# ==================================================
# 4. HEADER AND STEPPER
# ==================================================
html("""
<div class="app-header">
<div class="app-eyebrow">Smart Student Assistant</div>
<div class="app-title">Academic &amp; Stress Management</div>
<div class="app-sub">Plan your study time, organize your subjects, and get practical guidance for managing academic pressure.</div>
</div>
""")

current_step = st.session_state.step
parts = []
for i, label in enumerate(STEPS):
    state = "done" if i < current_step else "current" if i == current_step else ""
    parts.append(f'<div class="step {state}"><span class="dot">{i + 1}</span><span class="name">{label}</span></div>')
    if i < len(STEPS) - 1:
        line_state = "done" if i < current_step else ""
        parts.append(f'<div class="step-line {line_state}"></div>')

html(f'<div class="stepper">{"".join(parts)}</div>')

# ==================================================
# STEP 1: STUDENT PROFILE
# ==================================================
if current_step == 0:
    with st.container(key="slide_card"):
        html("""
        <div class="card-eyebrow">Step 1 · Profile</div>
        <div class="card-title">Let’s get to know you</div>
        <p class="muted">Enter your information to personalize your study plan.</p>
        """)
        st.text_input(tr("Student name"), key="student_name", placeholder=tr("Enter your name"))
        
        col1, col2 = st.columns(2, gap="large")
        with col1:
            st.selectbox(tr("Academic level"), ["University student", "High school student", "Preparatory student", "Other"], format_func=tr, key="study_level")
            st.slider(tr("Available study hours per day"), 1, 12, key="daily_hours")
        with col2:
            st.selectbox(tr("Preferred study style"), ["Short focused sessions", "Long focused sessions", "Mix of both"], format_func=tr, key="study_style")
            st.slider(tr("Days remaining until exam or deadline"), 1, 90, key="exam_days")

        uploaded_pdf = st.file_uploader("📂 (اختياري) ارفع ملف المنهج أو المذكرة (PDF) ليقوم الذكاء الاصطناعي بتحليله", type=["pdf"])
        if uploaded_pdf is not None:
            try:
                reader = pypdf.PdfReader(uploaded_pdf)
                pdf_text = "".join([page.extract_text() for page in reader.pages[:3]])
                st.session_state.pdf_extracted_text = pdf_text
                st.success("✨ تم قراءة ملف المنهج بنجاح وسيتم الاستعانة به في توجيهات المساعد الذكي!")
            except Exception as e:
                st.warning(f"تعذر قراءة الملف: {e}")

        html("""<div class="note"><b>Tip.</b> A balanced and realistic routine is easier to maintain than an overloaded schedule.</div>""")

    _, next_col = st.columns([3, 1])
    with next_col:
        if st.button(tr("Continue"), key="profile_next", type="primary"):
            if not st.session_state.student_name.strip():
                st.error(tr("Please enter your name before continuing."))
            else:
                go_next()
                st.rerun()

# ==================================================
# STEP 2: STRESS ASSESSMENT
# ==================================================
elif current_step == 1:
    with st.container(key="slide_card"):
        html("""
        <div class="card-eyebrow">Step 2 · Well-being</div>
        <div class="card-title">How are you feeling?</div>
        <p class="muted">Rate your current experience. This is a self-reflection tool, not a medical diagnosis.</p>
        """)
        col1, col2 = st.columns(2, gap="large")
        with col1:
            st.slider(tr("How stressed do you feel about studying?"), 0, 10, key="stress_score")
            st.slider(tr("How well can you concentrate?"), 0, 10, key="focus_score")
        with col2:
            st.slider(tr("How well are you sleeping?"), 0, 10, key="sleep_score")
            st.select_slider(tr("How manageable is your workload?"), options=list(WORKLOAD_SCORES.keys()), format_func=tr, key="workload")

        score = compute_stress()
        level, color = stress_level(score)
        html(f"""
        <div class="estimate">
        <div class="row">
        <div>
        <div class="card-eyebrow">Your stress estimate</div>
        <div class="score" style="color:{color}">{score}<small> / 10</small></div>
        </div>
        <span class="badge" style="color:{color};border-color:{color}55;background:{color}14">{level}</span>
        </div>
        <div class="bar"><div style="width:{score * 10}%;background:{color}"></div></div>
        <div class="muted">Calculated from your answers using simple weighted rules.</div>
        </div>
        """)

    back_col, next_col = st.columns(2)
    with back_col:
        if st.button(tr("Back"), key="stress_back"):
            go_back()
            st.rerun()
    with next_col:
        if st.button(tr("Continue"), key="stress_next", type="primary"):
            go_next()
            st.rerun()

# ==================================================
# STEP 3: SUBJECT PLANNING
# ==================================================
elif current_step == 2:
    with st.container(key="slide_card"):
        html("""
        <div class="card-eyebrow">Step 3 · Study planning</div>
        <div class="card-title">Organize your subjects</div>
        <p class="muted">Add each subject and set its difficulty and priority.</p>
        """)
        st.number_input(tr("How many subjects do you have?"), min_value=1, max_value=MAX_SUBJECTS, step=1, key="subject_count")
        subjects_data = []
        for i in range(int(st.session_state.subject_count)):
            with st.container(border=True):
                html(f'<div class="subject-label">{tr("SUBJECT")} {i + 1}</div>')
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    subject = st.text_input(tr("Subject name"), key=f"subject_name_{i}", placeholder=f"{tr('Subject name')} {i + 1}")
                with c2:
                    difficulty = st.selectbox(tr("Difficulty"), ["Easy", "Medium", "Hard"], format_func=tr, key=f"difficulty_{i}")
                with c3:
                    priority = st.selectbox(tr("Priority"), ["Normal", "Important", "Very important"], format_func=tr, key=f"priority_{i}")

            difficulty_weight = {"Easy": 1.0, "Medium": 1.5, "Hard": 2.0}[difficulty]
            priority_weight = {"Normal": 1.0, "Important": 1.3, "Very important": 1.6}[priority]
            subjects_data.append({"Subject": subject.strip() or f"Subject {i + 1}", "Difficulty": difficulty, "Priority": priority, "Weight": difficulty_weight * priority_weight})

        st.session_state.subjects_data = subjects_data
        html("""<div class="note"><b>How it works.</b> Harder and more important subjects receive a larger share of your available study hours.</div>""")

    back_col, next_col = st.columns(2)
    with back_col:
        if st.button(tr("Back"), key="subjects_back"):
            go_back()
            st.rerun()
    with next_col:
        if st.button(tr("Generate plan"), key="subjects_next", type="primary"):
            go_next()
            st.rerun()

# ==================================================
# STEP 4: RESULTS
# ==================================================
elif current_step == 3:
    saved = st.session_state.get("subjects_data", [])
    if not saved:
        st.warning(tr("Please enter your subjects first."))
        if st.button(tr("Back to planning"), key="results_missing_back"):
            st.session_state.step = 2
            st.rerun()
        st.stop()

    subjects_data = [dict(s) for s in saved]
    name = st.session_state.student_name
    daily_hours = st.session_state.daily_hours
    exam_days = st.session_state.exam_days
    stress_score = compute_stress()
    level, color = stress_level(stress_score)

    missed = st.session_state.get("missed_hours", 0)
    effective_days = max(1, exam_days - (missed // daily_hours))

    total_weight = sum(s["Weight"] for s in subjects_data)
    total_hours = daily_hours * effective_days

    for s in subjects_data:
        s["Daily Hours"] = daily_hours * s["Weight"] / total_weight
        s["Total Planned Hours"] = total_hours * s["Weight"] / total_weight

    html(f"""
    <div class="card-eyebrow">Your plan</div>
    <div class="app-title" style="margin-top:6px">Study plan for {name}</div>
    <p class="muted">{tr(st.session_state.study_level)} · {tr(st.session_state.study_style)}</p>
    """)

    with st.expander("🚨 هل فاتتك أيام مذاكرة وتحتاج لخطة طوارئ لإعادة الجدولة؟"):
        missed_input = st.number_input("كم عدد الساعات التي فاتتك وتريد تعويضها؟", 0, 48, key="missed_hours")
        if st.button("تحديث الخطة تلقائياً"):
            st.rerun()

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        html(f'<div class="metric"><div class="label">Daily study</div><div class="value">{daily_hours}<span class="unit">hrs</span></div></div>')
    with m2:
        html(f'<div class="metric"><div class="label">Planning window</div><div class="value">{effective_days}<span class="unit">days</span></div></div>')
    with m3:
        html(f'<div class="metric"><div class="label">Total hours</div><div class="value">{total_hours:.1f}<span class="unit">hrs</span></div></div>')
    with m4:
        html(f'<div class="metric"><div class="label">Stress estimate</div><div class="value" style="color:{color}">{stress_score}<span class="unit">/ 10 · {level}</span></div></div>')

    html('<div class="section-title">Study hours allocation</div>')
    df = pd.DataFrame(subjects_data)
    display_df = df[["Subject", "Difficulty", "Priority", "Daily Hours", "Total Planned Hours"]].copy()
    display_df["Daily Hours"] = display_df["Daily Hours"].round(2)
    display_df["Total Planned Hours"] = display_df["Total Planned Hours"].round(2)

    if st.session_state.language == "Arabic":
        display_df["Difficulty"] = display_df["Difficulty"].map({"Easy": "سهلة", "Medium": "متوسطة", "Hard": "صعبة"})
        display_df["Priority"] = display_df["Priority"].map({"Normal": "عادية", "Important": "مهمة", "Very important": "مهمة جدًا"})
        display_df = display_df.rename(columns={"Subject": "المادة", "Difficulty": "الصعوبة", "Priority": "الأولوية", "Daily Hours": "ساعات يوميًا", "Total Planned Hours": "إجمالي الساعات"})
    st.dataframe(display_df, hide_index=True)

    # ---- Chatbot Integration ----
    html('<div class="section-title">🤖 مساعد الذكاء الاصطناعي (المستشار الأكاديمي)</div>')
    
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            if "chat_messages" not in st.session_state:
                st.session_state.chat_messages = []
                st.session_state.chat = client.chats.create(model="gemini-2.5-flash")
                pdf_context = st.session_state.get("pdf_extracted_text", "لا يوجد ملف مرفق")
                context_prompt = f"""
                أنت مساعد أكاديمي ومستشار لإدارة التوتر. اسم الطالب هو {name}، 
                مستواه الدراسي {st.session_state.study_level}، ومستوى التوتر الحالي {stress_score}/10 ({level}).
                مواده الدراسية: {subjects_data}
                محتوى المنهج المرفق إن وجد: {pdf_context[:1000]}
                أجب على أسئلة الطالب واقترح نصائح تحفيزية وعلمية لمساعدته في التفوق والتخلص من الضغط.
                """
                st.session_state.chat.send_message(context_prompt)

            for message in st.session_state.chat_messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            if user_query := st.chat_input("اسأل المستشار الذكي عن جدولك أو استفسر عن أي نقطة صعبة..."):
                st.session_state.chat_messages.append({"role": "user", "content": user_query})
                with st.chat_message("user"):
                    st.markdown(user_query)

                with st.chat_message("assistant"):
                    with st.spinner("جاري التفكير..."):
                        response = st.session_state.chat.send_message(user_query)
                        bot_reply = response.text
                        st.markdown(bot_reply)
                        st.session_state.chat_messages.append({"role": "assistant", "content": bot_reply})
        except Exception as e:
            st.info("💡 تم تفعيل الشات بوت، تأكد من صحة مفتاح الـ API في إعدادات Streamlit Secrets.")
    else:
        st.info("💡 لتمكين المساعد الذكي التفاعلي، أضف مفتاح Gemini API في إعدادات التطبيق (Streamlit Secrets).")

    # ---- Export Calendar ----
    html('<div class="section-title">📅 تصدير إلى التقويم</div>')
    ics_data = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Study Planner//EN\n"
    ics_data += f"SUMMARY:Study Plan for {name}\nDESCRIPTION:Generated by Smart Student Assistant\n"
    ics_data += "END:VCALENDAR"
    
    st.download_button(
        label="📥 تحميل ملف التقويم (Add to Google/Apple Calendar)",
        data=ics_data.encode("utf-8"),
        file_name="study_plan.ics",
        mime="text/calendar"
    )

    st.markdown("---")
    back_col, restart_col = st.columns(2)
    with back_col:
        if st.button(tr("Back to planning"), key="results_back"):
            go_back()
            st.rerun()
    with restart_col:
        if st.button(tr("Start over"), key="restart", type="primary"):
            st.session_state.clear()
            st.rerun()

# ==================================================
# FOOTER
# ==================================================
st.markdown("---")
html('<div class="footer">ACADEMIC &amp; STRESS MANAGEMENT EXPERT SYSTEM</div>')
