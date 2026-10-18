import math

import streamlit as st

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
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# Streamlit drops the state of widgets that are not rendered in the current
# run. Re-assigning keeps every answer alive while moving between steps.
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


def html(markup):
    """Render HTML without markdown treating indentation as a code block."""
    cleaned = "\n".join(line.strip() for line in markup.strip().splitlines())
    st.markdown(cleaned, unsafe_allow_html=True)


# ==================================================
# 3. DESIGN SYSTEM
# ==================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
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
}

html, body, .stApp, [class*="css"] {
    font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
}

.stApp { background: var(--bg); color: var(--text); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"], #MainMenu, footer { visibility: hidden; }

.block-container {
    max-width: 1040px;
    padding-top: 2.5rem;
    padding-bottom: 3rem;
}

h1, h2, h3, h4, p, label, span { color: var(--text); }

/* ---------- Header ---------- */
.app-header { padding-bottom: 22px; border-bottom: 1px solid var(--border); margin-bottom: 26px; }
.app-eyebrow { color: var(--accent); font-size: 12px; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; }
.app-title { font-size: 32px; font-weight: 700; letter-spacing: -0.02em; margin: 8px 0 6px; color: #f8fafc; }
.app-sub { color: var(--muted); font-size: 15px; line-height: 1.6; max-width: 640px; }

/* ---------- Stepper ---------- */
.stepper { display: flex; align-items: center; margin-bottom: 26px; }
.step { display: flex; align-items: center; gap: 10px; }
.step .dot {
    width: 28px; height: 28px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 600;
    border: 1px solid var(--border-strong); color: var(--faint); background: transparent;
}
.step .name { font-size: 13px; font-weight: 500; color: var(--faint); white-space: nowrap; }
.step.done .dot { background: var(--accent); border-color: var(--accent); color: #fff; }
.step.done .name { color: var(--muted); }
.step.current .dot { border-color: var(--accent); color: #fff; box-shadow: 0 0 0 4px rgba(99,102,241,0.18); }
.step.current .name { color: #f8fafc; font-weight: 600; }
.step-line { flex: 1; height: 1px; background: var(--border-strong); margin: 0 14px; min-width: 18px; }
.step-line.done { background: var(--accent); }
@media (max-width: 720px) { .step:not(.current) .name { display: none; } }

/* ---------- Main card ---------- */
.st-key-slide_card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 32px;
    margin: 4px 0 20px;
}
.card-eyebrow { color: var(--faint); font-size: 12px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; }
.card-title { font-size: 24px; font-weight: 700; letter-spacing: -0.01em; margin: 6px 0 6px; color: #f8fafc; }
.muted { color: var(--muted); font-size: 14px; line-height: 1.7; }

/* ---------- Metric / info cards ---------- */
.metric {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 18px 20px;
    height: 100%;
}
.metric .label { color: var(--faint); font-size: 12px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; }
.metric .value { font-size: 28px; font-weight: 700; letter-spacing: -0.02em; margin-top: 8px; color: #f8fafc; }
.metric .unit { font-size: 14px; font-weight: 500; color: var(--muted); margin-left: 4px; }

.estimate {
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 20px 22px;
    margin-top: 18px;
}
.estimate .row { display: flex; align-items: baseline; justify-content: space-between; }
.estimate .score { font-size: 30px; font-weight: 700; letter-spacing: -0.02em; }
.estimate .score small { font-size: 15px; color: var(--faint); font-weight: 500; }
.estimate .badge { font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 999px; border: 1px solid; }
.bar { height: 6px; background: var(--border); border-radius: 999px; margin: 14px 0 12px; overflow: hidden; }
.bar > div { height: 100%; border-radius: 999px; }

/* ---------- Notes & tips ---------- */
.note {
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px 16px;
    margin: 18px 0 0;
    color: var(--muted);
    font-size: 14px;
    line-height: 1.65;
}
.note b { color: var(--text); font-weight: 600; }

.tip {
    display: flex; gap: 16px; align-items: flex-start;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px 18px;
    margin: 10px 0;
    font-size: 14px; line-height: 1.65; color: var(--text);
}
.tip .num { color: var(--accent); font-weight: 700; font-size: 13px; min-width: 22px; padding-top: 1px; }

.section-title { font-size: 18px; font-weight: 600; letter-spacing: -0.01em; margin: 34px 0 12px; color: #f8fafc; }
.subject-label { font-size: 13px; font-weight: 600; color: var(--muted); letter-spacing: 0.04em; margin-bottom: 4px; }

/* ---------- Inputs ---------- */
div[data-baseweb="input"],
div[data-baseweb="base-input"],
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] {
    background-color: var(--surface-2) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 10px !important;
}
div[data-baseweb="input"]:focus-within,
div[data-baseweb="select"]:focus-within > div {
    border-color: var(--accent) !important;
}
div[data-baseweb="input"] input,
div[data-baseweb="base-input"] input,
div[data-baseweb="textarea"] textarea {
    background: transparent !important;
    color: #f8fafc !important;
    -webkit-text-fill-color: #f8fafc !important;
}
div[data-baseweb="input"] input::placeholder { color: var(--faint) !important; -webkit-text-fill-color: var(--faint) !important; }
div[data-baseweb="select"] div, div[data-baseweb="select"] span, div[data-baseweb="select"] svg { color: #f8fafc !important; fill: #f8fafc !important; }
[data-testid="stNumberInput"] button { background: var(--surface-2) !important; color: var(--text) !important; border-color: var(--border-strong) !important; }

[data-baseweb="popover"] > div, [data-baseweb="menu"], ul[role="listbox"] {
    background: #111726 !important;
    border: 1px solid var(--border-strong);
    border-radius: 10px;
}
li[role="option"] { background: transparent !important; color: var(--text) !important; }
li[role="option"]:hover, li[role="option"][aria-selected="true"] { background: rgba(99,102,241,0.18) !important; }

[data-testid="stWidgetLabel"] p { font-size: 13px; font-weight: 500; color: var(--muted); }

/* sliders: force accent colour whatever the Streamlit theme is */
[data-testid="stSlider"] div[role="group"] { filter: hue-rotate(238deg) saturate(0.9); }
[data-testid="stSlider"] [data-testid="stTickBarMin"],
[data-testid="stSlider"] [data-testid="stTickBarMax"] { color: var(--faint); }

[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: var(--border) !important;
    background: var(--surface-2);
    border-radius: 14px !important;
}

/* ---------- Buttons ---------- */
.stButton, .stDownloadButton,
[data-testid="stElementContainer"]:has(> .stButton),
[data-testid="stElementContainer"]:has(> .stDownloadButton) { width: 100% !important; }
.stButton > button, .stDownloadButton > button {
    width: 100%;
    min-height: 44px;
    border-radius: 10px;
    font-weight: 600;
    font-size: 14px;
    transition: background 0.15s ease, border-color 0.15s ease;
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {
    background: var(--accent);
    border: 1px solid var(--accent);
    color: #ffffff;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover {
    background: var(--accent-hover);
    border-color: var(--accent-hover);
    color: #ffffff;
}
.stButton > button[kind="secondary"],
.stButton > button[data-testid="stBaseButton-secondary"],
.stDownloadButton > button {
    background: transparent;
    border: 1px solid var(--border-strong);
    color: var(--text);
}
.stButton > button[kind="secondary"]:hover,
.stButton > button[data-testid="stBaseButton-secondary"]:hover,
.stDownloadButton > button:hover {
    background: var(--surface);
    border-color: var(--accent);
    color: #ffffff;
}

[data-testid="stDataFrame"] {
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
}

hr { border-color: var(--border); margin: 1.6rem 0; }
.footer { text-align: center; color: var(--faint); font-size: 12px; letter-spacing: 0.08em; padding-top: 8px; }
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
        html("""
        <div class="card-eyebrow">Step 1 · Profile</div>
        <div class="card-title">Let’s get to know you</div>
        <p class="muted">Enter your information to personalize your study plan.</p>
        """)

        st.text_input("Student name", key="student_name", placeholder="Enter your name")

        col1, col2 = st.columns(2, gap="large")

        with col1:
            st.selectbox(
                "Academic level",
                ["University student", "High school student", "Preparatory student", "Other"],
                key="study_level",
            )
            st.slider("Available study hours per day", 1, 12, key="daily_hours")

        with col2:
            st.selectbox(
                "Preferred study style",
                ["Short focused sessions", "Long focused sessions", "Mix of both"],
                key="study_style",
            )
            st.slider("Days remaining until exam or deadline", 1, 90, key="exam_days")

        html("""
        <div class="note"><b>Tip.</b> A balanced and realistic routine is easier to maintain than an overloaded schedule.</div>
        """)

    _, next_col = st.columns([3, 1])
    with next_col:
        if st.button("Continue", key="profile_next", type="primary"):
            if not st.session_state.student_name.strip():
                st.error("Please enter your name before continuing.")
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
            st.slider("How stressed do you feel about studying?", 0, 10, key="stress_score")
            st.slider("How well can you concentrate?", 0, 10, key="focus_score")
        with col2:
            st.slider("How well are you sleeping?", 0, 10, key="sleep_score")
            st.select_slider(
                "How manageable is your workload?",
                options=list(WORKLOAD_SCORES.keys()),
                key="workload",
            )

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
        <div class="muted">Calculated from your answers using simple weighted rules. It is an organizational aid, not a validated clinical scale.</div>
        </div>
        """)

    back_col, next_col = st.columns(2)
    with back_col:
        if st.button("Back", key="stress_back"):
            go_back()
            st.rerun()
    with next_col:
        if st.button("Continue", key="stress_next", type="primary"):
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

        st.number_input(
            "How many subjects do you have?",
            min_value=1,
            max_value=MAX_SUBJECTS,
            step=1,
            key="subject_count",
        )

        subjects_data = []

        for i in range(int(st.session_state.subject_count)):
            with st.container(border=True):
                html(f'<div class="subject-label">SUBJECT {i + 1}</div>')

                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    subject = st.text_input(
                        "Subject name",
                        key=f"subject_name_{i}",
                        placeholder=f"Subject {i + 1}",
                    )
                with c2:
                    difficulty = st.selectbox(
                        "Difficulty", ["Easy", "Medium", "Hard"], key=f"difficulty_{i}"
                    )
                with c3:
                    priority = st.selectbox(
                        "Priority",
                        ["Normal", "Important", "Very important"],
                        key=f"priority_{i}",
                    )

            difficulty_weight = {"Easy": 1.0, "Medium": 1.5, "Hard": 2.0}[difficulty]
            priority_weight = {"Normal": 1.0, "Important": 1.3, "Very important": 1.6}[priority]

            subjects_data.append({
                "Subject": subject.strip() or f"Subject {i + 1}",
                "Difficulty": difficulty,
                "Priority": priority,
                "Weight": difficulty_weight * priority_weight,
            })

        st.session_state.subjects_data = subjects_data

        html("""
        <div class="note"><b>How it works.</b> Harder and more important subjects receive a larger share of your available study hours.</div>
        """)

    back_col, next_col = st.columns(2)
    with back_col:
        if st.button("Back", key="subjects_back"):
            go_back()
            st.rerun()
    with next_col:
        if st.button("Generate plan", key="subjects_next", type="primary"):
            go_next()
            st.rerun()

# ==================================================
# STEP 4: RESULTS
# ==================================================
elif current_step == 3:

    saved = st.session_state.get("subjects_data", [])

    if not saved:
        st.warning("Please enter your subjects first.")
        if st.button("Back to planning", key="results_missing_back"):
            st.session_state.step = 2
            st.rerun()
        st.stop()

    import pandas as pd  # loaded lazily so the first page opens quickly

    subjects_data = [dict(s) for s in saved]

    name = st.session_state.student_name
    daily_hours = st.session_state.daily_hours
    exam_days = st.session_state.exam_days
    stress_score = compute_stress()
    level, color = stress_level(stress_score)

    total_weight = sum(s["Weight"] for s in subjects_data)
    total_hours = daily_hours * exam_days

    for s in subjects_data:
        s["Daily Hours"] = daily_hours * s["Weight"] / total_weight
        s["Total Planned Hours"] = total_hours * s["Weight"] / total_weight

    html(f"""
    <div class="card-eyebrow">Your plan</div>
    <div class="app-title" style="margin-top:6px">Study plan for {name}</div>
    <p class="muted">{st.session_state.study_level} · {st.session_state.study_style}</p>
    """)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        html(f'<div class="metric"><div class="label">Daily study</div>'
             f'<div class="value">{daily_hours}<span class="unit">hrs</span></div></div>')
    with m2:
        html(f'<div class="metric"><div class="label">Planning window</div>'
             f'<div class="value">{exam_days}<span class="unit">days</span></div></div>')
    with m3:
        html(f'<div class="metric"><div class="label">Total hours</div>'
             f'<div class="value">{total_hours}<span class="unit">hrs</span></div></div>')
    with m4:
        html(f'<div class="metric"><div class="label">Stress estimate</div>'
             f'<div class="value" style="color:{color}">{stress_score}'
             f'<span class="unit">/ 10 · {level}</span></div></div>')

    # ---- Allocation table ----
    html('<div class="section-title">Study hours allocation</div>')

    df = pd.DataFrame(subjects_data)
    display_df = df[["Subject", "Difficulty", "Priority", "Daily Hours", "Total Planned Hours"]].copy()
    display_df["Daily Hours"] = display_df["Daily Hours"].round(2)
    display_df["Total Planned Hours"] = display_df["Total Planned Hours"].round(2)

    st.dataframe(display_df, hide_index=True)

    # ---- Chart ----
    html('<div class="section-title">Daily study distribution</div>')

    import matplotlib.pyplot as plt  # loaded lazily so the first page opens instantly

    chart_df = display_df.sort_values("Daily Hours", ascending=True)

    fig, ax = plt.subplots(figsize=(10, max(2.4, 0.55 * len(chart_df) + 1)))
    fig.patch.set_facecolor("#0b0f19")
    ax.set_facecolor("#0b0f19")

    bars = ax.barh(chart_df["Subject"], chart_df["Daily Hours"], color=ACCENT, height=0.55)

    ax.set_xlabel("Hours per day", color="#94a3b8", fontsize=10)
    ax.tick_params(axis="x", colors="#94a3b8", labelsize=9)
    ax.tick_params(axis="y", colors="#e5e7eb", labelsize=10, length=0)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#1f2937")
    ax.grid(axis="x", color="#1f2937", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xlim(0, chart_df["Daily Hours"].max() * 1.18)

    for bar in bars:
        ax.text(
            bar.get_width() + chart_df["Daily Hours"].max() * 0.015,
            bar.get_y() + bar.get_height() / 2,
            f"{bar.get_width():.1f} h",
            va="center",
            color="#e5e7eb",
            fontsize=10,
        )

    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    # ---- Timetable ----
    html('<div class="section-title">Suggested daily timetable</div>')

    ordered = sorted(subjects_data, key=lambda x: x["Weight"], reverse=True)

    def format_time(hour_value):
        total_minutes = round(hour_value * 60)
        hour = (total_minutes // 60) % 24
        minute = total_minutes % 60
        suffix = "AM" if hour < 12 else "PM"
        return f"{hour % 12 or 12}:{minute:02d} {suffix}"

    timetable = []
    current_time = 9.0

    for i, s in enumerate(ordered):
        duration = s["Daily Hours"]
        end_time = current_time + duration

        timetable.append({
            "Time": f"{format_time(current_time)} - {format_time(end_time)}",
            "Activity": f"Study: {s['Subject']}",
            "Duration": f"{duration:.1f} hours",
        })
        current_time = end_time

        if i < len(ordered) - 1:
            timetable.append({
                "Time": f"{format_time(current_time)} - {format_time(current_time + 0.25)}",
                "Activity": "Short break",
                "Duration": "15 minutes",
            })
            current_time += 0.25

            if (i + 1) % 2 == 0 and i < len(ordered) - 2:
                timetable.append({
                    "Time": f"{format_time(current_time)} - {format_time(current_time + 0.5)}",
                    "Activity": "Long break / meal",
                    "Duration": "30 minutes",
                })
                current_time += 0.5

    timetable_df = pd.DataFrame(timetable)
    st.dataframe(timetable_df, hide_index=True)

    if current_time > 22:
        st.warning(
            "This timetable runs late into the evening. Consider reducing your "
            "daily hours or starting earlier to protect your sleep."
        )

    # ---- Tips ----
    html('<div class="section-title">Stress management tips</div>')

    if stress_score <= 3:
        tips = [
            "Keep your study routine consistent and balanced.",
            "Review your notes regularly instead of cramming.",
            "Protect your sleep schedule and take regular breaks.",
        ]
    elif stress_score <= 6:
        tips = [
            "Break large tasks into smaller, manageable steps.",
            "Try 25 minutes of focused work followed by a 5-minute break.",
            "Start with the most important task and leave room for flexibility.",
        ]
    else:
        tips = [
            "Focus on urgent tasks first and postpone non-essential work.",
            "Use short study sessions with frequent breaks.",
            "Make time for meals, rest, hydration, and sleep.",
            "Consider talking with someone you trust or your student support team.",
        ]

    for n, tip in enumerate(tips, start=1):
        html(f'<div class="tip"><span class="num">{n:02d}</span><span>{tip}</span></div>')

    st.caption(
        "This tool offers study-planning suggestions, not medical advice "
        "or a clinical stress diagnosis."
    )

    # ---- Downloads ----
    html('<div class="section-title">Export</div>')

    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            "Download study plan",
            data=display_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="study_plan.csv",
            mime="text/csv",
        )
    with d2:
        st.download_button(
            "Download timetable",
            data=timetable_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="daily_timetable.csv",
            mime="text/csv",
        )

    st.markdown("---")

    back_col, restart_col = st.columns(2)
    with back_col:
        if st.button("Back to planning", key="results_back"):
            go_back()
            st.rerun()
    with restart_col:
        if st.button("Start over", key="restart", type="primary"):
            st.session_state.clear()
            st.rerun()

# ==================================================
# FOOTER
# ==================================================
st.markdown("---")
html('<div class="footer">ACADEMIC &amp; STRESS MANAGEMENT EXPERT SYSTEM</div>')
