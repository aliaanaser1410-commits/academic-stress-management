import math
from datetime import date, timedelta
from pathlib import Path
import time
import random

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

# --------------------------------------------------
# Theme config (written once, next to this file).
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
    initial_sidebar_state="expanded",
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
    "rest_days": [],
    "xp_points": 0,
    "daily_logs": [],
    "quick_tasks": [],
    "chat_history": [
        {"role": "assistant", "content": "أهلاً بك! أنا مساعدك الدراسي الذكي. كيف يمكنني مساعدتك في المذاكرة اليوم؟ 🎓"}
    ],
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

MAX_SUBJECTS = 10

for key in defaults:
    st.session_state[key] = st.session_state[key]

for i in range(MAX_SUBJECTS):
    for prefix in (
        "subject_name_",
        "exam_date_",
        "total_chapters_",
        "completed_chapters_",
        "difficulty_",
        "priority_",
        "student_level_",
        "hours_per_chapter_",
    ):
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

MOTIVATIONAL_TIPS = [
    "✨ النجاح ليس صدفة، بل هو نتيجة العمل الجاد والالتزام المستمر.",
    "💡 قسّم أهدافك الكبيرة إلى خطوات صغيرة يسهل إنجازها.",
    "🌿 خذ قسطاً من الراحة عندما تحتاجه، فالعقل المريح يستوعب أكثر.",
    "🎯 ابدأ بالمهام الصعبة أولاً وأنت بكامل طاقتك وركزك.",
    "⭐ لا تتقن العظمة بين عشية وضحاها، بل بالاستمرارية اليومية.",
    "💪 أنت قادرة على تحقيق أهدافك الدراسية وتجاوز كل الصعاب!"
]


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


def get_student_rank(xp):
    if xp < 50:
        return "🐣 مبتدئ (Beginner)"
    elif xp < 150:
        return "🐥 متعلم مركز (Focused Learner)"
    elif xp < 300:
        return "🦉 بطل الدراسة (Study Champion)"
    else:
        return "🦅 أستاذ المذاكرة (Study Master)"


def get_smart_bot_response(user_input):
    text = user_input.lower()
    if any(w in text for w in ["متوتر", "خائف", "ضغط", "قلق", "stress"]):
        return "خذ نفساً عميقاً! التوتر أمر طبيعي قبل الامتحانات. أنصحك باستراحة لمدة 10 دقائق واستخدام مؤقت البومودورو المتاح في القائمة الجانبية لتوزيع وقتك."
    elif any(w in text for w in ["تعبان", "محتار", "أبدأ إزاي", "صعب", "مستصعب"]):
        return "عندما تستصعب مادة، ابدأ بأسهل جزء فيها لمدة 15 دقيقة فقط لبناء الزخم. الخطة الموضوعة لك في التطبيق توازن تلقائياً."
    elif any(w in text for w in ["الوقت ضيق", "امتحان", "الامتحان", "الوقت"]):
        return "التركيز على الجودة أهم من الكمية! ركز على الفصول ذات الأولوية العالية والمواد الصعبة أولاً بناءً على الجدول المحدد لك."
    elif any(w in text for w in ["شكراً", "شكرا", "تسلم", "حلو"]):
        return "العفو! أنا دائماً هنا لمساعدتك. استمري في الإنجاز وجمع نقاط الـ XP! 🌟"
    else:
        return "سؤال ممتاز! للحصول على أفضل نتيجة، أنصحك بالالتزام بالجدول اليومي المقترح وتدوين يومياتك. هل تريد الاستفسار عن شيء آخر؟"


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
    "Organize your subjects": "نظّم موادك الدراسية ومناهجها",
    "Add each subject and set its difficulty and priority.": "أدخل تفاصيل المواد والفصول والمواعيد لتصميم جدول حقيقي.",
    "How many subjects do you have?": "كم مادة لديك؟",
    "SUBJECT": "المادة",
    "Subject name": "اسم المادة",
    "Exam Date": "تاريخ الامتحان",
    "Total Chapters / Lectures": "إجمالي عدد الفصول / المحاضرات",
    "Completed Chapters": "الفصول التي تم انتهائها",
    "Difficulty": "الصعوبة",
    "Easy": "سهلة",
    "Medium": "متوسطة",
    "Hard": "صعبة",
    "Priority": "الأولوية",
    "Normal": "عادية",
    "Important": "مهمة",
    "Very important": "مهمة جدًا",
    "Student Level in Subject": "مستواك الحالي في المادة",
    "Good": "جيد",
    "Average": "متوسط",
    "Weak": "ضعيف",
    "Hours per Chapter": "الساعات المتوقعة للفصل الواحد",
    "Rest Days (No Study)": "أيام الراحة (لا يوجد مذاكرة فيها)",
    "Monday": "الإثنين",
    "Tuesday": "الثلاثاء",
    "Wednesday": "الأربعاء",
    "Thursday": "الخميس",
    "Friday": "الجمعة",
    "Saturday": "السبت",
    "Sunday": "الأحد",
    "How it works.": "كيف تعمل الخطة.",
    "Harder and more important subjects receive a larger share of your available study hours.": "المواد الأصعب والأكثر أهمية تحصل على وقت مذاكرة أكبر.",
    "Generate plan": "إنشاء الخطة",
    "Please enter your subjects first.": "من فضلك أدخل المواد أولًا.",
    "Back to planning": "العودة لتنظيم المذاكرة",
    "Your plan": "خطتك الدراسية",
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
    "Suggested daily timetable": "الجدول اليومي المقترح لكل يوم",
    "Short break": "استراحة قصيرة",
    "Long break / meal": "استراحة طويلة / وجبة",
    "Stress management tips": "نصائح لإدارة التوتر",
    "Keep your study routine consistent and balanced.": "حافظ على روتين مذاكرة ثابت ومتوازن.",
    "Review your notes regularly instead of cramming.": "راجع ملاحظاتك بانتظام بدلًا من المذاكرة المكثفة في آخر لحظة.",
    "Protect your sleep schedule and take regular breaks.": "حافظ على مواعيد نومك وخذ فترات راحة منتظمة.",
    "Break large tasks into smaller, manageable steps.": "قسّم المهام الكبيرة إلى خطوات صغيرة يمكن إنجازها.",
    "Export": "تصدير",
    "Download study plan": "تحميل خطة المذاكرة",
    "Download timetable": "تحميل الجدول اليومي",
    "Back": "السابق",
    "Back to planning": "السابق: تنظيم المذاكرة",
    "Start over": "البدء من جديد",
    "ACADEMIC &amp; STRESS MANAGEMENT EXPERT SYSTEM": "نظام خبير لإدارة الدراسة والتوتر",
    "Smart Student Assistant": "مساعد الطالب الذكي",
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
    for en, ar in sorted(
        TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True
    ):
        result = result.replace(en, ar)
    return result


def html(markup):
    cleaned = "\n".join(line.strip() for line in markup.strip().splitlines())
    cleaned = tr(cleaned)
    st.markdown(cleaned, unsafe_allow_html=True)


# ==================================================
# 3. DESIGN SYSTEM & DYNAMIC DIRECTION FIX
# ==================================================
is_arabic = st.session_state.get("language", "English") == "Arabic"

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {{
    --bg: #0b0f19;
    --surface: #111726;
    --surface-2: #0d1320;
    --border: #1f2937;
    --border-strong: #2b3648;
    --text: #e5e7eb;
    --muted: #94a3b8;
    --faint: #64748b;
    --accent: #6366f1;
    --accent-hover: #4f46e5;
}}

html, body, .stApp, [class*="css"] {{
    font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
    direction: {"rtl" if is_arabic else "ltr"};
}}

.stApp {{ background: var(--bg); color: var(--text); }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stToolbar"], #MainMenu, footer {{ visibility: hidden; }}

.block-container {{
    max-width: 1040px;
    padding-top: 2.5rem;
    padding-bottom: 3rem;
    text-align: {"right" if is_arabic else "left"};
}}

h1, h2, h3, h4, p, label, span {{ color: var(--text); text-align: {"right" if is_arabic else "left"}; }}

.app-header {{ padding-bottom: 22px; border-bottom: 1px solid var(--border); margin-bottom: 26px; text-align: {"right" if is_arabic else "left"}; }}
.app-eyebrow {{ color: var(--accent); font-size: 12px; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; }}
.app-title {{ font-size: 32px; font-weight: 700; letter-spacing: -0.02em; margin: 8px 0 6px; color: #f8fafc; }}
.app-sub {{ color: var(--muted); font-size: 15px; line-height: 1.6; max-width: 640px; }}

.stepper {{ display: flex; align-items: center; margin-bottom: 26px; direction: {"rtl" if is_arabic else "ltr"}; }}
.step {{ display: flex; align-items: center; gap: 10px; }}
.step .dot {{
    width: 28px; height: 28px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 600;
    border: 1px solid var(--border-strong); color: var(--faint); background: transparent;
}}
.step .name {{ font-size: 13px; font-weight: 500; color: var(--faint); white-space: nowrap; }}
.step.done .dot {{ background: var(--accent); border-color: var(--accent); color: #fff; }}
.step.done .name {{ color: var(--muted); }}
.step.current .dot {{ border-color: var(--accent); color: #fff; box-shadow: 0 0 0 4px rgba(99,102,241,0.18); }}
.step.current .name {{ color: #f8fafc; font-weight: 600; }}
.step-line {{ flex: 1; height: 1px; background: var(--border-strong); margin: 0 14px; min-width: 18px; }}
.step-line.done {{ background: var(--accent); }}

.st-key-slide_card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 32px;
    margin: 4px 0 20px;
}}
.card-eyebrow {{ color: var(--faint); font-size: 12px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; }}
.card-title {{ font-size: 24px; font-weight: 700; letter-spacing: -0.01em; margin: 6px 0 6px; color: #f8fafc; }}
.muted {{ color: var(--muted); font-size: 14px; line-height: 1.7; }}

.metric {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 18px 20px;
    height: 100%;
}}
.metric .label {{ color: var(--faint); font-size: 12px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; }}
.metric .value {{ font-size: 28px; font-weight: 700; letter-spacing: -0.02em; margin-top: 8px; color: #f8fafc; }}
.metric .unit {{ font-size: 14px; font-weight: 500; color: var(--muted); margin-left: 4px; }}

.estimate {{
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 20px 22px;
    margin-top: 18px;
}}
.estimate .row {{ display: flex; align-items: baseline; justify-content: space-between; }}
.estimate .score {{ font-size: 30px; font-weight: 700; letter-spacing: -0.02em; }}
.estimate .score small {{ font-size: 15px; color: var(--faint); font-weight: 500; }}
.estimate .badge {{ font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 999px; border: 1px solid; }}
.bar {{ height: 6px; background: var(--border); border-radius: 999px; margin: 14px 0 12px; overflow: hidden; }}
.bar > div {{ height: 100%; border-radius: 999px; }}

.note {{
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px 16px;
    margin: 18px 0 0;
    color: var(--muted);
    font-size: 14px;
    line-height: 1.65;
}}
.note b {{ color: var(--text); font-weight: 600; }}

.tip {{
    display: flex; gap: 16px; align-items: flex-start;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px 18px;
    margin: 10px 0;
    font-size: 14px; line-height: 1.65; color: var(--text);
}}
.tip .num {{ color: var(--accent); font-weight: 700; font-size: 13px; min-width: 22px; padding-top: 1px; }}

.section-title {{ font-size: 18px; font-weight: 600; letter-spacing: -0.01em; margin: 34px 0 12px; color: #f8fafc; }}
.subject-label {{ font-size: 13px; font-weight: 600; color: var(--muted); letter-spacing: 0.04em; margin-bottom: 4px; }}

div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="textarea"] {{
    background-color: var(--surface-2) !important;
    border-color: var(--border-strong) !important;
    border-radius: 10px !important;
}}
div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea {{ color: #f8fafc !important; }}
[data-testid="stWidgetLabel"] p {{ font-size: 13px; font-weight: 500; color: var(--muted); }}

[data-testid="stVerticalBlockBorderWrapper"] {{
    border-color: var(--border) !important;
    background: var(--surface-2);
    border-radius: 14px !important;
}}

.stButton > button, .stDownloadButton > button {{
    width: 100%;
    min-height: 44px;
    border-radius: 10px;
    font-weight: 600;
    font-size: 14px;
    transition: background 0.15s ease, border-color 0.15s ease;
}}
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {{
    background: var(--accent);
    border: 1px solid var(--accent);
    color: #ffffff;
}}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover {{
    background: var(--accent-hover);
    border-color: var(--accent-hover);
    color: #ffffff;
}}
.stButton > button[kind="secondary"],
.stButton > button[data-testid="stBaseButton-secondary"],
.stDownloadButton > button {{
    background: transparent;
    border: 1px solid var(--border-strong);
    color: var(--text);
}}
.stButton > button[kind="secondary"]:hover,
.stButton > button[data-testid="stBaseButton-secondary"]:hover,
.stDownloadButton > button:hover {{
    background: var(--surface);
    border-color: var(--accent);
    color: #ffffff;
}}

[data-testid="stDataFrame"] {{
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
}}

hr {{ border-color: var(--border); margin: 1.6rem 0; }}
.footer {{ text-align: center; color: var(--faint); font-size: 12px; letter-spacing: 0.08em; padding-top: 8px; }}
</style>
""",
    unsafe_allow_html=True,
)

# ==================================================
# 4. SIDEBAR: CHATBOT, POMODORO, XP & QUICK TASKS
# ==================================================
with st.sidebar:
    st.markdown("### 🤖 المساعد الدراسي الذكي (AI Bot)")
    with st.expander("💬 دردش مع المساعد", expanded=False):
        for msg in st.session_state.chat_history:
            st.chat_message(msg["role"]).write(msg["content"])
        
        user_msg = st.chat_input("اسأل المساعد نصيحة...")
        if user_msg:
            st.session_state.chat_history.append({"role": "user", "content": user_msg})
            bot_ans = get_smart_bot_response(user_msg)
            st.session_state.chat_history.append({"role": "assistant", "content": bot_ans})
            st.rerun()

    st.markdown("---")
    st.markdown("### 🏆 لوحة إنجاز الطالب (XP)")
    current_xp = st.session_state.get("xp_points", 0)
    current_rank = get_student_rank(current_xp)
    st.metric(label="نقاطك الحالية (XP)", value=current_xp)
    st.markdown(f"**المستوى الدراسي:** {current_rank}")
    st.markdown("---")

    # QUICK TASKS (قائمة المهام السريعة)
    st.markdown("### ✅ قائمة المهام السريعة")
    new_task = st.text_input("أضف مهمة سريعة جديدة:", placeholder="مثال: تسليم البحث...")
    if st.button("➕ إضافة مهمة"):
        if new_task.strip():
            st.session_state.quick_tasks.append({"task": new_task.strip(), "done": False})
            st.rerun()

    if st.session_state.quick_tasks:
        st.markdown("#### المهام المعلقة:")
        tasks_to_remove = []
        for idx, t in enumerate(st.session_state.quick_tasks):
            col_t1, col_t2 = st.columns([4, 1])
            with col_t1:
                is_checked = st.checkbox(t["task"], value=t["done"], key=f"q_task_{idx}")
                if is_checked != t["done"]:
                    st.session_state.quick_tasks[idx]["done"] = is_checked
                    if is_checked:
                        st.session_state.xp_points += 5
                        st.toast("🌟 أحسنت! تم إنجاز مهمة سريعة (+5 XP).")
            with col_t2:
                if st.button("❌", key=f"del_task_{idx}"):
                    tasks_to_remove.append(idx)
        
        if tasks_to_remove:
            for idx in reversed(tasks_to_remove):
                st.session_state.quick_tasks.pop(idx)
            st.rerun()

    st.markdown("---")

    # MOTIVATIONAL TIPS SECTION (قسم النصائح والإلهام)
    st.markdown("### 💡 حصن الإلهام والنصائح")
    if "current_tip" not in st.session_state:
        st.session_state.current_tip = random.choice(MOTIVATIONAL_TIPS)
    
    st.info(st.session_state.current_tip)
    if st.button("🔄 نصيحة جديدة"):
        st.session_state.current_tip = random.choice(MOTIVATIONAL_TIPS)
        st.rerun()

    st.markdown("---")

    st.markdown("### ⏱️ مؤقت البومودورو للمذاكرة")
    pomodoro_mode = st.radio(
        "وضع المؤقت",
        ["جلسة تركيز (25 دقيقة)", "استراحة قصيرة (5 دقائق)", "استراحة طويلة (15 دقيقة)"],
        index=0,
    )

    if "25" in pomodoro_mode:
        default_secs = 25 * 60
    elif "5" in pomodoro_mode:
        default_secs = 5 * 60
    else:
        default_secs = 15 * 60

    if "pomo_time_left" not in st.session_state:
        st.session_state.pomo_time_left = default_secs
    if "pomo_running" not in st.session_state:
        st.session_state.pomo_running = False

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("▶️ ابدأ"):
            st.session_state.pomo_running = True
    with col_s2:
        if st.button("⏸️ إيقاف"):
            st.session_state.pomo_running = False

    if st.button("🔄 إعادة ضبط"):
        st.session_state.pomo_running = False
        st.session_state.pomo_time_left = default_secs

    mins, secs = divmod(st.session_state.pomo_time_left, 60)
    timer_placeholder = st.empty()
    timer_placeholder.markdown(
        f"<h1 style='text-align: center; color: #6366f1;'>{mins:02d}:{secs:02d}</h1>",
        unsafe_allow_html=True,
    )

    if st.session_state.pomo_running and st.session_state.pomo_time_left > 0:
        time.sleep(1)
        st.session_state.pomo_time_left -= 1
        st.rerun()
    elif st.session_state.pomo_time_left == 0 and st.session_state.pomo_running:
        st.session_state.pomo_running = False
        st.session_state.xp_points += 20
        st.success("🎉 انتهت الجلسة بنجاح! تم منحك +20 نقطة XP.")

    st.markdown("---")

# ==================================================
# 5. FIXED NAVBAR & CONTROLS (أزرار اللغة والثيم فقط بشكل منظم)
# ==================================================
nav_col1, nav_col2 = st.columns([1, 1])

with nav_col1:
    lang_label = "🌐 العربية" if st.session_state.language == "English" else "🌐 English"
    if st.button(lang_label, key="toggle_language", help="Switch interface language"):
        st.session_state.language = "Arabic" if st.session_state.language == "English" else "English"
        st.rerun()

with nav_col2:
    theme_label = "☀️ Light theme" if st.session_state.theme_mode == "Dark" else "🌙 Dark theme"
    if st.button(tr(theme_label), key="toggle_theme", help="Switch between dark and light themes"):
        st.session_state.theme_mode = "Light" if st.session_state.theme_mode == "Dark" else "Dark"
        st.rerun()

if st.session_state.theme_mode == "Light":
    st.markdown(
        """
    <style>
    :root {
        --bg: #f4f6fb;
        --surface: #ffffff;
        --surface-2: #edf1f8;
        --border: #d8deea;
        --border-strong: #c4ccdc;
        --text: #172033;
        --muted: #475569;
        --faint: #64748b;
        --accent: #6366f1;
        --accent-hover: #4f46e5;
    }
    .stApp { background: var(--bg) !important; color: var(--text) !important; }
    h1, h2, h3, h4, p, label, span { color: var(--text); }
    .app-title, .card-title, .step.current .name { color: #172033 !important; }
    .st-key-slide_card, .metric, .tip { background: #ffffff !important; }
    .estimate, .note, [data-testid="stVerticalBlockBorderWrapper"] { background: #edf1f8 !important; }
    div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea { color: #172033 !important; }
    .stButton > button[data-testid="stBaseButton-secondary"],
    .stDownloadButton > button { color: #172033 !important; }
    </style>
    """,
        unsafe_allow_html=True,
    )

# ==================================================
# 6. HEADER AND STEPPER
# ==================================================
html(
    """
<div class="app-header">
<div class="app-eyebrow">Smart Student Assistant</div>
<div class="app-title">Academic &amp; Stress Management</div>
<div class="app-sub">Plan your study time, organize your subjects, and get practical guidance for managing academic pressure.</div>
</div>
"""
)

current_step = st.session_state.step

parts = []
for i, label in enumerate(STEPS):
    state = "done" if i < current_step else "current" if i == current_step else ""
    parts.append(
        f'<div class="step {state}"><span class="dot">{i + 1}</span>'
        f'<span class="name">{label}</span></div>'
    )
    if i < len(STEPS) - 1:
        line_state = "done" if i < current_step else ""
        parts.append(f'<div class="step-line {line_state}"></div>')

html(f'<div class="stepper">{"".join(parts)}</div>')

# ==================================================
# STEP 1: STUDENT PROFILE
# ==================================================
if current_step == 0:
    with st.container(key="slide_card"):
        html(
            """
        <div class="card-eyebrow">Step 1 · Profile</div>
        <div class="card-title">Let’s get to know you</div>
        <p class="muted">Enter your information to personalize your study plan.</p>
        """
        )

        st.text_input(
            tr("Student name"),
            key="student_name",
            placeholder=tr("Enter your name"),
        )

        col1, col2 = st.columns(2, gap="large")

        with col1:
            st.selectbox(
                tr("Academic level"),
                [
                    "University student",
                    "High school student",
                    "Preparatory student",
                    "Other",
                ],
                format_func=tr,
                key="study_level",
            )
            st.slider(
                tr("Available study hours per day"), 1, 12, key="daily_hours"
            )

        with col2:
            st.selectbox(
                tr("Preferred study style"),
                [
                    "Short focused sessions",
                    "Long focused sessions",
                    "Mix of both",
                ],
                format_func=tr,
                key="study_style",
            )
            st.slider(
                tr("Days remaining until exam or deadline"),
                1,
                90,
                key="exam_days",
            )

        html(
            """
        <div class="note"><b>Tip.</b> A balanced and realistic routine is easier to maintain than an overloaded schedule.</div>
        """
        )

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
        html(
            """
        <div class="card-eyebrow">Step 2 · Well-being</div>
        <div class="card-title">How are you feeling?</div>
        <p class="muted">Rate your current experience. This is a self-reflection tool, not a medical diagnosis.</p>
        """
        )

        col1, col2 = st.columns(2, gap="large")
        with col1:
            st.slider(
                tr("How stressed do you feel about studying?"),
                0,
                10,
                key="stress_score",
            )
            st.slider(
                tr("How well can you concentrate?"), 0, 10, key="focus_score"
            )
        with col2:
            st.slider(tr("How well are you sleeping?"), 0, 10, key="sleep_score")
            st.select_slider(
                tr("How manageable is your workload?"),
                options=list(WORKLOAD_SCORES.keys()),
                format_func=tr,
                key="workload",
            )

        score = compute_stress()
        level, color = stress_level(score)

        html(
            f"""
        <div class="estimate">
        <div class="row">
        <div>
        <div class="card-eyebrow">Your stress estimate</div>
        <div class="score" style="color:{color}">{score}<small> / 10</small></div>
        </div>
        <span class="badge" style="color:{color};border-color:{color}55;background:{color}14">{level}</span>
        </div>
        <div class="bar"><div style="width:{score * 10}%;background:{color}"></div></div>
        <div class="muted">Calculated from your answers using simple weighted rules. It is an organizational aid, not a validated clinical scale.</div>
        </div>
        """
        )

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
# STEP 3: SUBJECT PLANNING & ADVANCED INPUTS
# ==================================================
elif current_step == 2:
    with st.container(key="slide_card"):
        html(
            """
        <div class="card-eyebrow">Step 3 · Study planning</div>
        <div class="card-title">Organize your subjects</div>
        <p class="muted">Add each subject and set its difficulty, chapters, and exam schedule.</p>
        """
        )

        st.number_input(
            tr("How many subjects do you have?"),
            min_value=1,
            max_value=MAX_SUBJECTS,
            step=1,
            key="subject_count",
        )

        rest_days_options = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        st.multiselect(
            tr("Rest Days (No Study)"),
            options=rest_days_options,
            format_func=tr,
            key="rest_days",
        )

        subjects_data = []

        for i in range(int(st.session_state.subject_count)):
            with st.container(border=True):
                html(
                    f'<div class="subject-label">{tr("SUBJECT")} {i + 1}</div>'
                )

                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    subject = st.text_input(
                        tr("Subject name"),
                        key=f"subject_name_{i}",
                        placeholder=f"{tr('Subject name')} {i + 1}",
                    )
                with c2:
                    exam_date = st.date_input(
                        tr("Exam Date"),
                        value=date.today()
                        + timedelta(days=st.session_state.exam_days),
                        key=f"exam_date_{i}",
                    )
                with c3:
                    hours_per_chapter = st.number_input(
                        tr("Hours per Chapter"),
                        min_value=0.5,
                        max_value=10.0,
                        value=2.0,
                        step=0.5,
                        key=f"hours_per_chapter_{i}",
                    )

                c4, c5, c6, c7 = st.columns(4)
                with c4:
                    total_chapters = st.number_input(
                        tr("Total Chapters / Lectures"),
                        min_value=1,
                        max_value=50,
                        value=6,
                        step=1,
                        key=f"total_chapters_{i}",
                    )
                with c5:
                    completed_chapters = st.number_input(
                        tr("Completed Chapters"),
                        min_value=0,
                        max_value=50,
                        value=0,
                        step=1,
                        key=f"completed_chapters_{i}",
                    )
                with c6:
                    difficulty = st.selectbox(
                        tr("Difficulty"),
                        ["Easy", "Medium", "Hard"],
                        format_func=tr,
                        key=f"difficulty_{i}",
                    )
                with c7:
                    priority = st.selectbox(
                        tr("Priority"),
                        ["Normal", "Important", "Very important"],
                        format_func=tr,
                        key=f"priority_{i}",
                    )

                c8, _ = st.columns(2)
                with c8:
                    student_lvl = st.selectbox(
                        tr("Student Level in Subject"),
                        ["Good", "Average", "Weak"],
                        format_func=tr,
                        key=f"student_level_{i}",
                    )

            rem_chapters = max(0, total_chapters - completed_chapters)
            diff_w = {"Easy": 1.0, "Medium": 1.5, "Hard": 2.0}[difficulty]
            prio_w = {"Normal": 1.0, "Important": 1.3, "Very important": 1.6}[
                priority
            ]
            lvl_w = {"Good": 0.9, "Average": 1.2, "Weak": 1.6}[student_lvl]
            weight = diff_w * prio_w * lvl_w

            subjects_data.append(
                {
                    "Subject": subject.strip() or f"Subject {i + 1}",
                    "Exam Date": exam_date,
                    "Total Chapters": total_chapters,
                    "Completed Chapters": completed_chapters,
                    "Remaining Chapters": rem_chapters,
                    "Difficulty": difficulty,
                    "Priority": priority,
                    "Student Level": student_lvl,
                    "Hours Per Chapter": hours_per_chapter,
                    "Total Required Hours": rem_chapters * hours_per_chapter,
                    "Weight": weight,
                }
            )

        st.session_state.subjects_data = subjects_data

        html(
            """
        <div class="note"><b>How it works.</b> Harder and more important subjects receive priority in your daily study schedule.</div>
        """
        )

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
# STEP 4: RESULTS, DAILY REFLECTION LOG & SCHEDULE
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

    total_weight = sum(s["Weight"] for s in subjects_data)
    total_hours = daily_hours * exam_days

    for s in subjects_data:
        s["Daily Hours"] = (
            daily_hours * s["Weight"] / total_weight
            if total_weight > 0
            else 0
        )
        s["Total Planned Hours"] = (
            total_hours * s["Weight"] / total_weight if total_weight > 0 else 0
        )

    html(
        f"""
    <div class="card-eyebrow">Your plan</div>
    <div class="app-title" style="margin-top:6px">Study plan for {name}</div>
    <p class="muted">{tr(st.session_state.study_level)} · {tr(st.session_state.study_style)}</p>
    """
    )

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        html(
            f'<div class="metric"><div class="label">Daily study</div>'
            f'<div class="value">{daily_hours}<span class="unit">hrs</span></div></div>'
        )
    with m2:
        html(
            f'<div class="metric"><div class="label">Planning window</div>'
            f'<div class="value">{exam_days}<span class="unit">days</span></div></div>'
        )
    with m3:
        html(
            f'<div class="metric"><div class="label">Total hours</div>'
            f'<div class="value">{total_hours}<span class="unit">hrs</span></div></div>'
        )
    with m4:
        html(
            f'<div class="metric"><div class="label">Stress estimate</div>'
            f'<div class="value" style="color:{color}">{stress_score}'
            f'<span class="unit">/ 10 · {level}</span></div></div>'
        )

    # DAILY STUDY REFLECTION LOG (يوميّة المذاكرة)
    html('<div class="section-title">📝 يوميّة المتابعة اليومية (ماذا أخذت وذاكرت اليوم؟)</div>')
    with st.form(key="daily_log_form"):
        st.write("سجّل إنجازك اليومي لتبقى على اطلاع تام بمستواك:")
        log_date = st.date_input("تاريخ اليوم", value=date.today())
        
        subj_list = [s["Subject"] for s in subjects_data]
        selected_sub = st.selectbox("المادة الدراسية", options=subj_list)
        
        col_l1, col_l2 = st.columns(2)
        with col_l1:
            lectures_taken = st.number_input("عدد المحاضرات أو الفصول التي أخذتها اليوم:", min_value=0, max_value=10, value=1)
        with col_l2:
            lectures_studied = st.number_input("عدد المحاضرات أو الفصول التي ذاكرتها بالفعل:", min_value=0, max_value=10, value=1)

        what_studied = st.text_area("ماذا ذاكرت اليوم بالتحديد؟ (أهم النقاط):")
        what_not_studied = st.text_area("ماذا لم تذاكره اليوم وبقي مؤجلاً؟ (ولماذا؟):")

        submit_log = st.form_submit_button("💾 حفظ السجل اليومي (+20 XP)")
        if submit_log:
            st.session_state.daily_logs.append({
                "Date": str(log_date),
                "Subject": selected_sub,
                "Taken": lectures_taken,
                "Studied": lectures_studied,
                "Studied Notes": what_studied,
                "Not Studied Notes": what_not_studied
            })
            st.session_state.xp_points += 20
            st.success("✨ تم حفظ سجلك اليومي بنجاح وإضافة +20 نقطة XP إلى رصيدك!")

    if st.session_state.daily_logs:
        with st.expander("📖 عرض سجلات المذاكرة السابقة"):
            logs_df = pd.DataFrame(st.session_state.daily_logs)
            st.dataframe(logs_df, hide_index=True)

    # PROGRESS DASHBOARD (لوحة تتبع نسبة الإتمام)
    html('<div class="section-title">📊 لوحة تتبع نسبة إتمام المناهج</div>')
    for sub in subjects_data:
        tot = sub["Total Chapters"]
        comp = sub["Completed Chapters"]
        pct = int((comp / tot) * 100) if tot > 0 else 0
        st.write(
            f"**{sub['Subject']}** — الإنجاز: {comp}/{tot} فصل ({pct}%)"
        )
        st.progress(pct / 100)

    # Warnings
    total_needed_hours = sum(s["Total Required Hours"] for s in subjects_data)
    if total_needed_hours > total_hours:
        st.warning(
            f"⚠️ **تنبيه هام:** إجمالي ساعات المنهج المطلوبة ({total_needed_hours} ساعة) أكبر من الساعات المتاحة ({total_hours} ساعة). ننصح بزيادة ساعات المذاكرة اليومية أو تمديد فترة التخطيط!"
        )
    else:
        st.success(
            "✅ الوقت المتاح كافٍ تمامًا لإنهاء المناهج ومراجعتها قبل الامتحانات بناءً على معدلك اليومي."
        )

    # Allocation table
    html('<div class="section-title">Study hours allocation</div>')

    df = pd.DataFrame(subjects_data)
    display_df = df[
        [
            "Subject",
            "Exam Date",
            "Remaining Chapters",
            "Difficulty",
            "Priority",
            "Student Level",
            "Total Required Hours",
        ]
    ].copy()
    display_df["Total Required Hours"] = display_df[
        "Total Required Hours"
    ].round(2)

    if st.session_state.language == "Arabic":
        display_df["Difficulty"] = display_df["Difficulty"].map(
            {"Easy": "سهلة", "Medium": "متوسطة", "Hard": "صعبة"}
        )
        display_df["Priority"] = display_df["Priority"].map(
            {
                "Normal": "عادية",
                "Important": "مهمة",
                "Very important": "مهمة جدًا",
            }
        )
        display_df["Student Level"] = display_df["Student Level"].map(
            {"Good": "جيد", "Average": "متوسط", "Weak": "ضعيف"}
        )
        display_df = display_df.rename(
            columns={
                "Subject": "المادة",
                "Exam Date": "تاريخ الامتحان",
                "Remaining Chapters": "الفصول المتبقية",
                "Difficulty": "الصعوبة",
                "Priority": "الأولوية",
                "Student Level": "المستوى",
                "Total Required Hours": "الساعات المطلوبة للمنهج",
            }
        )
    st.dataframe(display_df, hide_index=True)

    # SEPARATE DAY-BY-DAY SCHEDULE WITH CHECKBOXES & XP REWARD
    html(
        '<div class="section-title">📅 الجدول اليومي المفصل (مع منح نقاط XP عند الإنجاز)</div>'
    )
    st.write(
        "حدد المهام عند انتهائك منها لكسب نقاط XP ورفع مستواك الدراسي تلقائياً:"
    )

    rest_days = st.session_state.get("rest_days", [])
    today = date.today()
    sorted_subjects = sorted(
        subjects_data, key=lambda x: (x["Exam Date"], -x["Weight"])
    )

    day_names_en = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    day_names_ar_map = {
        "Monday": "الإثنين",
        "Tuesday": "الثلاثاء",
        "Wednesday": "الأربعاء",
        "Thursday": "الخميس",
        "Friday": "الجمعة",
        "Saturday": "السبت",
        "Sunday": "الأحد",
    }

    for day_offset in range(min(exam_days, 14)):
        target_day = today + timedelta(days=day_offset)
        day_name_str = day_names_en[target_day.weekday()]
        day_name_display = (
            day_names_ar_map[day_name_str]
            if st.session_state.language == "Arabic"
            else day_name_str
        )

        with st.container(border=True):
            st.markdown(
                f"### 🗓️ اليوم {day_offset + 1}: {day_name_display} ({target_day.strftime('%Y-%m-%d')})"
            )

            if day_name_str in rest_days:
                st.info(
                    "🌴 **يوم راحة محدد:** استمتع بوقتك ولا تقم بأي مهام دراسية اليوم لتجديد نشاطك."
                )
                continue

            hours_left_today = daily_hours
            day_has_tasks = False

            for sub in sorted_subjects:
                if target_day >= sub["Exam Date"]:
                    continue
                if sub["Remaining Chapters"] > 0 and hours_left_today > 0:
                    allocated_hrs = min(
                        hours_left_today,
                        max(1.5, sub["Hours Per Chapter"]),
                        sub["Remaining Chapters"] * sub["Hours Per Chapter"],
                    )
                    chapters_to_cover = max(
                        1, round(allocated_hrs / sub["Hours Per Chapter"], 1)
                    )

                    checkbox_key = f"task_{day_offset}_{sub['Subject']}"
                    
                    was_checked = st.session_state.get(f"prev_{checkbox_key}", False)
                    is_done = st.checkbox(
                        f"📚 مذاكرة مادة **{sub['Subject']}** — حوالي {chapters_to_cover} فصل/محاضرة ({round(allocated_hrs, 1)} ساعات)",
                        key=checkbox_key,
                    )

                    if is_done and not was_checked:
                        st.session_state.xp_points += 15
                        st.session_state[f"prev_{checkbox_key}"] = True
                        st.toast("🎉 أحسنتِ! تم إضافة +15 نقطة XP لرصيدك.", icon="⭐")
                    elif not is_done and was_checked:
                        st.session_state.xp_points = max(0, st.session_state.xp_points - 15)
                        st.session_state[f"prev_{checkbox_key}"] = False

                    hours_left_today -= allocated_hrs
                    sub["Remaining Chapters"] = max(
                        0, sub["Remaining Chapters"] - chapters_to_cover
                    )
                    day_has_tasks = True

            if not day_has_tasks:
                st.success(
                    "✨ لقد أتممت جميع فصول المناهج المتاحة لهذا النطاق بنجاح! مبروك، وقت للمراجعة الشاملة."
                )

    # ---- Chart ----
    html('<div class="section-title">Daily study distribution</div>')

    chart_df = (
        df[["Subject", "Daily Hours"]]
        .copy()
        .sort_values("Daily Hours", ascending=True)
    )
    fig, ax = plt.subplots(
        figsize=(10, max(2.4, 0.55 * len(chart_df) + 1))
    )
    fig.patch.set_facecolor(
        "#f4f6fb" if st.session_state.theme_mode == "Light" else "#0b0f19"
    )
    ax.set_facecolor(
        "#f4f6fb" if st.session_state.theme_mode == "Light" else "#0b0f19"
    )

    bars = ax.barh(
        chart_df["Subject"], chart_df["Daily Hours"], color=ACCENT, height=0.55
    )
    ax.set_xlabel(
        tr("Hours per day"),
        color=(
            "#475569" if st.session_state.theme_mode == "Light" else "#94a3b8"
        ),
        fontsize=10,
    )
    ax.tick_params(
        axis="x",
        colors=(
            "#475569" if st.session_state.theme_mode == "Light" else "#94a3b8"
        ),
        labelsize=9,
    )
    ax.tick_params(
        axis="y",
        colors=(
            "#172033" if st.session_state.theme_mode == "Light" else "#e5e7eb"
        ),
        labelsize=10,
        length=0,
    )
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(
        "#d8deea" if st.session_state.theme_mode == "Light" else "#1f2937"
    )
    ax.grid(
        axis="x",
        color=(
            "#d8deea" if st.session_state.theme_mode == "Light" else "#1f2937"
        ),
        linewidth=0.8,
    )
    ax.set_axisbelow(True)
    ax.set_xlim(0, chart_df["Daily Hours"].max() * 1.18)

    for bar in bars:
        ax.text(
            bar.get_width() + chart_df["Daily Hours"].max() * 0.015,
            bar.get_y() + bar.get_height() / 2,
            f"{bar.get_width():.1f} h",
            va="center",
            color=(
                "#172033"
                if st.session_state.theme_mode == "Light"
                else "#e5e7eb"
            ),
            fontsize=10,
        )

    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    # ---- Recommendations & Stress Tips ----
    html('<div class="section-title">Stress management tips</div>')
    tips = [
        "Keep your study routine consistent and balanced.",
        "Review your notes regularly instead of cramming.",
        "Protect your sleep schedule and take regular breaks.",
        "Break large tasks into smaller, manageable steps.",
        "Try 25 minutes of focused work followed by a 5-minute break.",
    ]
    for idx, t in enumerate(tips, 1):
        html(
            f'<div class="tip"><div class="num">{idx:02d}</div><div>{tr(t)}</div></div>'
        )

    html(
        f'<div class="note">{tr("This tool offers study-planning suggestions, not medical advice or a clinical stress diagnosis.")}</div>'
    )

    # ---- Export Button ----
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=tr("Download study plan"),
            data=csv_data,
            file_name="study_plan.csv",
            mime="text/csv",
        )
    with col_dl2:
        st.download_button(
            label=tr("Download timetable"),
            data=csv_data,
            file_name="daily_timetable.csv",
            mime="text/csv",
        )

    st.markdown("---")
    c_back, c_restart = st.columns(2)
    with c_back:
        if st.button(tr("Back to planning"), key="results_back"):
            st.session_state.step = 2
            st.rerun()
    with c_restart:
        if st.button(tr("Start over"), key="results_restart"):
            st.session_state.step, st.session_state.subjects_data = 0, []
            st.rerun()

html(
    '<div class="footer">ACADEMIC &amp; STRESS MANAGEMENT EXPERT SYSTEM</div>'
)
