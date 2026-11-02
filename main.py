

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime, timedelta

# ==================================================
# PAGE CONFIGURATION
# ==================================================
st.set_page_config(
    page_title="Smart Student Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================================================
# SESSION STATE
# ==================================================
defaults = {
    "language": "English",
    "theme": "Dark",
    "page": "Home",
    "student_name": "",
    "level": "University",
    "daily_hours": 4,
    "days_left": 14,
    "study_style": "Pomodoro",
    "stress": 5,
    "sleep": 7,
    "focus": 5,
    "workload": 5,
    "subjects": [],
    "study_plan": [],
    "plan_generated": False,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ==================================================
# LANGUAGE
# ==================================================
TEXT = {
    "English": {
        "home": "Home",
        "profile": "Student Profile",
        "stress": "Stress Management",
        "planning": "Study Planning",
        "plan": "My Study Plan",
        "settings": "Settings",
        "welcome": "Welcome to your Smart Study Assistant 🎓",
        "subtitle": "Organize your studies, manage your stress, and reach your goals.",
        "overview": "Your Study Overview",
        "hours": "Daily Study Hours",
        "days": "Days Remaining",
        "subjects": "Total Subjects",
        "status": "Plan Status",
        "quick": "Quick Access",
        "profile_title": "Student Profile",
        "name": "Student Name",
        "level": "Academic Level",
        "daily": "Available Study Hours Per Day",
        "remaining": "Days Until Exams",
        "style": "Preferred Study Style",
        "save": "Save Profile",
        "saved": "Profile saved successfully!",
        "stress_title": "Stress Assessment",
        "stress_level": "Stress Level",
        "sleep": "Sleep Hours",
        "focus": "Focus Level",
        "workload": "Workload Level",
        "assess": "Analyze My Condition",
        "result": "Your Assessment",
        "planning_title": "Study Planning",
        "subject_name": "Subject Name",
        "difficulty": "Difficulty",
        "priority": "Priority",
        "add": "Add Subject",
        "added": "Subject added successfully!",
        "your_subjects": "Your Subjects",
        "generate": "Generate Study Plan",
        "plan_title": "Your Study Plan",
        "no_plan": "You haven't generated a study plan yet.",
        "export": "Download Study Plan (CSV)",
        "clear": "Clear All Subjects",
        "light": "Light",
        "dark": "Dark",
        "language": "Language",
        "theme": "Appearance",
        "easy": "Easy",
        "medium": "Medium",
        "hard": "Hard",
        "low": "Low",
        "normal": "Normal",
        "high": "High",
        "footer": "SMART STUDENT ASSISTANT",
        "no_subjects": "Add at least one subject first.",
        "recommendation": "Recommendations",
        "total_hours": "Total Planned Hours",
        "daily_schedule": "Daily Study Schedule",
        "remove": "Remove",
        "reset": "Reset Study Plan",
    },
    "العربية": {
        "home": "الرئيسية",
        "profile": "الملف الشخصي",
        "stress": "إدارة التوتر",
        "planning": "تخطيط المذاكرة",
        "plan": "جدول المذاكرة",
        "settings": "الإعدادات",
        "welcome": "أهلاً بك في مساعدك الدراسي الذكي 🎓",
        "subtitle": "نظّم مذاكرتك، وأدر توترك، وحقق أهدافك.",
        "overview": "ملخص دراستك",
        "hours": "ساعات المذاكرة اليومية",
        "days": "الأيام المتبقية",
        "subjects": "عدد المواد",
        "status": "حالة الجدول",
        "quick": "الوصول السريع",
        "profile_title": "الملف الشخصي للطالب",
        "name": "اسم الطالب",
        "level": "المستوى الدراسي",
        "daily": "ساعات المذاكرة المتاحة يومياً",
        "remaining": "الأيام المتبقية للامتحانات",
        "style": "طريقة المذاكرة المفضلة",
        "save": "حفظ البيانات",
        "saved": "تم حفظ البيانات بنجاح!",
        "stress_title": "تقييم مستوى التوتر",
        "stress_level": "مستوى التوتر",
        "sleep": "عدد ساعات النوم",
        "focus": "مستوى التركيز",
        "workload": "حجم ضغط الدراسة",
        "assess": "تحليل حالتي",
        "result": "نتيجة التقييم",
        "planning_title": "تخطيط المذاكرة",
        "subject_name": "اسم المادة",
        "difficulty": "مستوى الصعوبة",
        "priority": "الأولوية",
        "add": "إضافة مادة",
        "added": "تمت إضافة المادة بنجاح!",
        "your_subjects": "المواد الدراسية",
        "generate": "إنشاء جدول المذاكرة",
        "plan_title": "جدول المذاكرة الخاص بك",
        "no_plan": "لم تقومي بإنشاء جدول مذاكرة بعد.",
        "export": "تحميل الجدول CSV",
        "clear": "مسح جميع المواد",
        "light": "فاتح",
        "dark": "داكن",
        "language": "اللغة",
        "theme": "المظهر",
        "easy": "سهل",
        "medium": "متوسط",
        "hard": "صعب",
        "low": "منخفضة",
        "normal": "متوسطة",
        "high": "عالية",
        "footer": "مساعد الطالب الذكي",
        "no_subjects": "أضيفي مادة واحدة على الأقل أولاً.",
        "recommendation": "نصائح وتوصيات",
        "total_hours": "إجمالي ساعات المذاكرة",
        "daily_schedule": "جدول المذاكرة اليومي",
        "remove": "حذف",
        "reset": "إعادة ضبط الجدول",
    }
}

def t(key):
    return TEXT[st.session_state.language][key]

is_ar = st.session_state.language == "العربية"

# ==================================================
# THEME
# ==================================================
if st.session_state.theme == "Dark":
    bg = "#101827"
    card = "#1c293b"
    text_color = "#f1f5f9"
    muted = "#aab7c8"
    accent = "#7c9cff"
else:
    bg = "#f4f7fb"
    card = "#ffffff"
    text_color = "#172033"
    muted = "#667085"
    accent = "#4263eb"

st.markdown(f"""
<style>
.stApp {{
    background: {bg};
    color: {text_color};
}}
[data-testid="stSidebar"] {{
    background: {card};
}}
h1, h2, h3, p, label {{
    color: {text_color};
}}
.dashboard-card {{
    background: {card};
    padding: 22px;
    border-radius: 15px;
    border: 1px solid rgba(130,150,180,0.18);
    margin-bottom: 12px;
}}
.metric-number {{
    font-size: 30px;
    font-weight: 700;
    color: {accent};
}}
.metric-label {{
    color: {muted};
    font-size: 14px;
}}
.hero {{
    background: linear-gradient(120deg, #253c75, #526fc2);
    padding: 30px;
    border-radius: 18px;
    color: white;
    margin-bottom: 25px;
}}
.hero h1, .hero p {{
    color: white !important;
}}
.stButton > button {{
    border-radius: 9px;
    min-height: 42px;
}}
.footer {{
    text-align: center;
    color: {muted};
    font-size: 12px;
    padding: 20px;
}}
</style>
""", unsafe_allow_html=True)

# ==================================================
# SIDEBAR NAVIGATION
# ==================================================
pages = [
    t("home"),
    t("profile"),
    t("stress"),
    t("planning"),
    t("plan"),
    t("settings")
]

with st.sidebar:
    st.markdown("## 🎓 Smart Assistant")
    st.caption("Academic & Stress Management")
    st.divider()

    selected = st.radio(
        "Navigation",
        pages,
        index=pages.index(
            t(st.session_state.page.lower())
            if st.session_state.page.lower() in TEXT["English"]
            else pages[0]
        ) if False else 0,
        label_visibility="collapsed"
    )

    st.session_state.page = selected

    st.divider()

    st.markdown("### 📊 Study Summary")
    st.write(f"📚 {len(st.session_state.subjects)} subjects")
    st.write(f"⏰ {st.session_state.daily_hours} hours/day")

    if st.session_state.student_name:
        st.caption(f"Student: {st.session_state.student_name}")

# ==================================================
# HOME
# ==================================================
if selected == t("home"):

    name = st.session_state.student_name
    greeting = f", {name}" if name else ""

    st.markdown(f"""
    <div class="hero">
        <h1>{t("welcome")}{greeting}</h1>
        <p>{t("subtitle")}</p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader(t("overview"))

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="metric-label">{t("hours")}</div>
            <div class="metric-number">{st.session_state.daily_hours}</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="metric-label">{t("days")}</div>
            <div class="metric-number">{st.session_state.days_left}</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="metric-label">{t("subjects")}</div>
            <div class="metric-number">{len(st.session_state.subjects)}</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        status = "Ready" if st.session_state.plan_generated else "Not created"
        if is_ar:
            status = "جاهز" if st.session_state.plan_generated else "لم يُنشأ"
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="metric-label">{t("status")}</div>
            <div class="metric-number" style="font-size:22px">{status}</div>
        </div>
        """, unsafe_allow_html=True)

    st.subheader(t("quick"))

    q1, q2, q3 = st.columns(3)

    with q1:
        if st.button("👤 " + t("profile"), use_container_width=True):
            st.session_state.page = t("profile")
            st.rerun()

    with q2:
        if st.button("🧠 " + t("stress"), use_container_width=True):
            st.session_state.page = t("stress")
            st.rerun()

    with q3:
        if st.button("📅 " + t("planning"), use_container_width=True):
            st.session_state.page = t("planning")
            st.rerun()

    st.divider()
    st.info(
        "Start by completing your profile and adding your subjects."
        if not is_ar else
        "ابدئي بإكمال بياناتك الشخصية وإضافة المواد الدراسية."
    )

# ==================================================
# STUDENT PROFILE
# ==================================================
elif selected == t("profile"):

    st.title("👤 " + t("profile_title"))

    with st.form("profile_form"):
        name = st.text_input(
            t("name"),
            value=st.session_state.student_name
        )

        level = st.selectbox(
            t("level"),
            ["School", "University", "Postgraduate"],
            index=["School", "University", "Postgraduate"].index(
                st.session_state.level
            )
        )

        daily_hours = st.slider(
            t("daily"), 1, 12,
            st.session_state.daily_hours
        )

        days_left = st.number_input(
            t("remaining"), 1, 365,
            st.session_state.days_left
        )

        style = st.selectbox(
            t("style"),
            ["Pomodoro", "Time Blocking", "Traditional"],
            index=["Pomodoro", "Time Blocking", "Traditional"].index(
                st.session_state.study_style
            )
        )

        submitted = st.form_submit_button(
            "💾 " + t("save"),
            use_container_width=True
        )

        if submitted:
            st.session_state.student_name = name
            st.session_state.level = level
            st.session_state.daily_hours = daily_hours
            st.session_state.days_left = int(days_left)
            st.session_state.study_style = style
            st.success(t("saved"))

# ==================================================
# STRESS MANAGEMENT
# ==================================================
elif selected == t("stress"):

    st.title("🧠 " + t("stress_title"))
    st.write(
        "Answer the following questions to understand your current condition."
        if not is_ar else
        "أجيبي عن الأسئلة التالية لفهم حالتك الحالية."
    )

    st.session_state.stress = st.slider(
        t("stress_level"), 1, 10,
        st.session_state.stress
    )

    st.session_state.sleep = st.slider(
        t("sleep"), 0, 12,
        st.session_state.sleep
    )

    st.session_state.focus = st.slider(
        t("focus"), 1, 10,
        st.session_state.focus
    )

    st.session_state.workload = st.slider(
        t("workload"), 1, 10,
        st.session_state.workload
    )

    if st.button("🔍 " + t("assess"), use_container_width=True):

        stress_score = (
            st.session_state.stress * 0.35
            + (10 - st.session_state.focus) * 0.25
            + st.session_state.workload * 0.25
            + max(0, 8 - st.session_state.sleep) * 0.15
        )

        st.subheader(t("result"))

        st.metric(
            "Stress Indicator" if not is_ar else "مؤشر التوتر",
            f"{stress_score:.1f}/10"
        )

        if stress_score >= 7:
            st.warning(
                "Your current stress indicator is high. Consider reducing your workload."
                if not is_ar else
                "مؤشر التوتر مرتفع. حاولي تقليل ضغط الدراسة وأخذ فترات راحة."
            )
        elif stress_score >= 4:
            st.info(
                "Your stress indicator is moderate. Keep a balanced routine."
                if not is_ar else
                "مؤشر التوتر متوسط. حاولي الحفاظ على روتين متوازن."
            )
        else:
            st.success(
                "Your stress indicator is relatively low. Keep it up!"
                if not is_ar else
                "مؤشر التوتر منخفض نسبيًا. استمري في الحفاظ على توازنك!"
            )

        st.subheader(t("recommendation"))

        recommendations = []

        if st.session_state.sleep < 7:
            recommendations.append(
                "Try to get enough sleep."
                if not is_ar else
                "حاولي الحصول على ساعات نوم كافية."
            )

        if st.session_state.focus < 5:
            recommendations.append(
                "Study in short focused sessions."
                if not is_ar else
                "استخدمي جلسات مذاكرة قصيرة ومركزة."
            )

        if st.session_state.workload > 7:
            recommendations.append(
                "Break large tasks into smaller tasks."
                if not is_ar else
                "قسّمي المهام الكبيرة إلى مهام أصغر."
            )

        if not recommendations:
            recommendations.append(
                "Maintain your current healthy study routine."
                if not is_ar else
                "حافظي على روتين المذاكرة الحالي."
            )

        for item in recommendations:
            st.write("• " + item)

        st.caption(
            "This is a self-assessment indicator, not a medical diagnosis."
            if not is_ar else
            "هذا التقييم مؤشر إرشادي وليس تشخيصًا طبيًا."
        )

# ==================================================
# STUDY PLANNING
# ==================================================
elif selected == t("planning"):

    st.title("📚 " + t("planning_title"))

    with st.form("subject_form", clear_on_submit=True):

        subject_name = st.text_input(t("subject_name"))

        difficulty = st.selectbox(
            t("difficulty"),
            [t("easy"), t("medium"), t("hard")]
        )

        priority = st.selectbox(
            t("priority"),
            [t("low"), t("normal"), t("high")]
        )

        add_subject = st.form_submit_button(
            "➕ " + t("add"),
            use_container_width=True
        )

        if add_subject:
            if subject_name.strip():
                st.session_state.subjects.append({
                    "Subject": subject_name.strip(),
                    "Difficulty": difficulty,
                    "Priority": priority
                })
                st.session_state.plan_generated = False
                st.session_state.study_plan = []
                st.success(t("added"))
            else:
                st.error(
                    "Please enter a subject name."
                    if not is_ar else
                    "من فضلك أدخلي اسم المادة."
                )

    st.divider()
    st.subheader(t("your_subjects"))

    if st.session_state.subjects:

        df = pd.DataFrame(st.session_state.subjects)
        st.dataframe(df, use_container_width=True, hide_index=True)

        if st.button("🗑️ " + t("clear")):
            st.session_state.subjects = []
            st.session_state.study_plan = []
            st.session_state.plan_generated = False
            st.rerun()

        st.caption(
            "You can add up to 10 subjects."
            if not is_ar else
            "يمكنك إضافة 10 مواد كحد أقصى."
        )

        if len(st.session_state.subjects) > 10:
            st.warning(
                "You have exceeded the recommended 10 subjects."
                if not is_ar else
                "لقد تجاوزتِ الحد المقترح وهو 10 مواد."
            )

    else:
        st.info(
            "No subjects added yet."
            if not is_ar else
            "لم تتم إضافة أي مواد حتى الآن."
        )

    if st.button(
        "✨ " + t("generate"),
        type="primary",
        use_container_width=True
    ):

        if not st.session_state.subjects:
            st.error(t("no_subjects"))

        else:
            subjects = st.session_state.subjects[:10]

            difficulty_weights = {
                t("easy"): 1,
                t("medium"): 2,
                t("hard"): 3
            }

            priority_weights = {
                t("low"): 1,
                t("normal"): 2,
                t("high"): 3
            }

            weights = []

            for subject in subjects:
                weight = (
                    difficulty_weights.get(subject["Difficulty"], 2)
                    * 0.5
                    + priority_weights.get(subject["Priority"], 2)
                    * 0.5
                )
                weights.append(weight)

            total_weight = sum(weights)

            total_hours = (
                st.session_state.daily_hours
                * st.session_state.days_left
            )

            plan = []

            for subject, weight in zip(subjects, weights):
                allocated = total_hours * weight / total_weight

                plan.append({
                    "Subject": subject["Subject"],
                    "Difficulty": subject["Difficulty"],
                    "Priority": subject["Priority"],
                    "Planned Hours": round(allocated, 2),
                    "Daily Hours": round(
                        allocated / st.session_state.days_left, 2
                    )
                })

            st.session_state.study_plan = plan
            st.session_state.plan_generated = True

            st.success(
                "Your study plan has been generated!"
                if not is_ar else
                "تم إنشاء جدول المذاكرة بنجاح!"
            )

# ==================================================
# MY STUDY PLAN
# ==================================================
elif selected == t("plan"):

    st.title("📅 " + t("plan_title"))

    if not st.session_state.plan_generated:
        st.info(t("no_plan"))

    else:
        df = pd.DataFrame(st.session_state.study_plan)

        col1, col2 = st.columns(2)

        total = df["Planned Hours"].sum()

        with col1:
            st.metric(t("total_hours"), f"{total:.1f} h")

        with col2:
            st.metric(
                t("subjects"),
                len(df)
            )

        st.subheader(
            "Hours Distribution"
            if not is_ar else
            "توزيع ساعات المذاكرة"
        )

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(
            df["Subject"],
            df["Planned Hours"]
        )
        ax.set_ylabel("Hours")
        ax.set_xlabel("Subjects")
        ax.tick_params(axis="x", rotation=25)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

        st.subheader(t("daily_schedule"))

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            "📥 " + t("export"),
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name="study_plan.csv",
            mime="text/csv",
            use_container_width=True
        )

        # Simple daily timetable
        st.subheader(
            "Suggested Daily Allocation"
            if not is_ar else
            "التوزيع اليومي المقترح"
        )

        daily_rows = []

        for item in st.session_state.study_plan:
            daily_rows.append({
                "Subject": item["Subject"],
                "Daily Hours": item["Daily Hours"]
            })

        daily_df = pd.DataFrame(daily_rows)
        st.dataframe(
            daily_df,
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            "This is an estimated allocation, not a timetable based on lecture times or exam dates."
            if not is_ar else
            "هذا توزيع تقديري للساعات، وليس جدولًا مبنيًا على مواعيد المحاضرات أو الامتحانات."
        )

        if st.button("🔄 " + t("reset")):
            st.session_state.study_plan = []
            st.session_state.plan_generated = False
            st.rerun()

# ==================================================
# SETTINGS
# ==================================================
elif selected == t("settings"):

    st.title("⚙️ " + t("settings"))

    language_options = ["English", "العربية"]

    current_language = st.selectbox(
        t("language"),
        language_options,
        index=language_options.index(st.session_state.language)
    )

    current_theme = st.selectbox(
        t("theme"),
        ["Dark", "Light"],
        index=["Dark", "Light"].index(st.session_state.theme)
    )

    if (
        current_language != st.session_state.language
        or current_theme != st.session_state.theme
    ):
        st.session_state.language = current_language
        st.session_state.theme = current_theme
        st.rerun()

    st.divider()

    st.markdown("### About")
    st.write(
        "Smart Student Assistant helps students organize study time "
        "and monitor academic stress."
        if not is_ar else
        "يساعد مساعد الطالب الذكي على تنظيم وقت المذاكرة ومتابعة مؤشرات الضغط الدراسي."
    )

# ==================================================
# FOOTER
# ==================================================
st.markdown("---")
st.markdown(
    f'<div class="footer">{t("footer")} © 2026</div>',
    unsafe_allow_html=True
)
