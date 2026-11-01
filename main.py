
"""
Smart Student Assistant – Academic & Stress Management
=======================================================
Upgraded version of the original Streamlit project.

Run:  streamlit run smart_student_assistant.py

File layout (top to bottom):
  1. Imports + theme config (original)
  2. LOGIC LAYER  - pure Python, no Streamlit: scheduling, rescheduling,
                    SQLite persistence, XP / badges, statistics
  3. UI TEXT      - original TRANSLATIONS + new bilingual UI strings
  4. DESIGN SYSTEM (CSS) and the original Step 1-3 wizard
  5. RESULTS      - Dashboard / Daily schedule / Analytics / Plan overview
"""
import json
import math
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from html import escape as esc
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

# Optional: proper Arabic shaping inside Matplotlib charts.
#   pip install arabic-reshaper python-bidi
# Without them the app still works; chart text simply stays in English.
try:
    import arabic_reshaper
    from bidi.algorithm import get_display

    HAS_SHAPING = True
except Exception:  # pragma: no cover
    HAS_SHAPING = False

# --------------------------------------------------
# Theme config (written once, next to this file).
# It makes sliders / focus rings use the accent colour.
# Takes effect from the next launch of the app.
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

# ##################################################
# ##########  LOGIC LAYER  (no Streamlit)  #########
# ##################################################
# ===== LOGIC START =====

MAX_SUBJECTS = 10
MAX_SUBJECTS_PER_DAY = 3          # rule: at most 3 different subjects per day
SESSION_OPTIONS = (1.0, 1.5, 2.0)  # allowed session lengths (hours)
DAY_START_HOUR = 9.0               # timetable starts at 9:00 AM
SHORT_BREAK_H = 0.25               # 15 minutes
LONG_BREAK_H = 0.5                 # 30 minutes (after every 2nd session)
LATE_HOUR = 22.0                   # warn if a day ends after 10 PM
XP_SESSION = 10
XP_DAY_BONUS = 20
EPS = 1e-9

DB_PATH = Path(__file__).resolve().parent / "student_assistant.db"

DIFFICULTY_WEIGHT = {"Easy": 1.0, "Medium": 1.5, "Hard": 2.0}
PRIORITY_WEIGHT = {"Normal": 1.0, "Important": 1.3, "Very important": 1.6}

# (key, minimum XP, buddy emoji)
LEVELS = [
    ("beginner", 0, "🐣"),
    ("focused", 100, "🐥"),
    ("champion", 300, "🦉"),
    ("master", 600, "🦅"),
]
BADGE_KEYS = ["first_session", "five_sessions", "ten_sessions", "first_day", "plan_complete"]
BADGE_EMOJI = {
    "first_session": "🌱", "five_sessions": "⭐", "ten_sessions": "🔟",
    "first_day": "🏅", "plan_complete": "🏆",
}


# ---------------------------------------------------------------- helpers
def norm_name(name):
    """Canonical key used to tell students apart (case/space-insensitive)."""
    return " ".join(str(name or "").split()).casefold()


def day_capacity(daily_hours):
    """Usable hours per day, rounded down to a half hour (sessions are 0.5h-based)."""
    return math.floor(float(daily_hours) * 2 + EPS) / 2


def fmt_h(x):
    return f"{x:g}"


def format_time(hour_value):
    total_minutes = round(hour_value * 60)
    hour = (total_minutes // 60) % 24
    minute = total_minutes % 60
    suffix = "AM" if hour < 12 else "PM"
    return f"{hour % 12 or 12}:{minute:02d} {suffix}"


def build_subjects(raw):
    """raw = [(name, difficulty, priority), ...] -> (subjects, error).
    error is None, 'empty' (no real name typed) or 'duplicate'."""
    subjects, seen, named, dup = [], set(), 0, False
    for i, (name, diff, prio) in enumerate(raw):
        clean = " ".join(str(name or "").split())[:40]
        if clean:
            named += 1
        else:
            clean = f"Subject {i + 1}"
        if diff not in DIFFICULTY_WEIGHT:
            diff = "Easy"
        if prio not in PRIORITY_WEIGHT:
            prio = "Normal"
        if clean.casefold() in seen:
            dup = True
        seen.add(clean.casefold())
        subjects.append({
            "Subject": clean, "Difficulty": diff, "Priority": prio,
            "Weight": DIFFICULTY_WEIGHT[diff] * PRIORITY_WEIGHT[prio],
        })
    error = "duplicate" if dup else ("empty" if named == 0 else None)
    return subjects, error


# ------------------------------------------------------------- scheduling
def split_hours(x, order):
    """Split x hours (multiple of 0.5, >= 1) into pieces from SESSION_OPTIONS.
    No piece is ever shorter than 1 hour. `order` = preferred piece lengths."""
    pieces = []
    x = round(x * 2) / 2
    while x > 2 + EPS:
        for p in order:
            rem = x - p
            if rem < EPS or rem >= 1 - EPS:
                pieces.append(p)
                x = rem
                break
    if x > EPS:
        pieces.append(x)
    return pieces


def allocate_units(total_units, k, shares):
    """Distribute `total_units` half-hours over k subjects. Everybody gets at
    least 2 units (1 hour); the rest follows `shares` (largest remainder)."""
    base = [2] * k
    rest = total_units - 2 * k
    if rest <= 0:
        return base
    s = sum(shares) or float(k)
    shares = shares if sum(shares) > 0 else [1.0] * k
    ideal = [rest * sh / s for sh in shares]
    add = [int(math.floor(v)) for v in ideal]
    left = rest - sum(add)
    for i in sorted(range(k), key=lambda i: ideal[i] - add[i], reverse=True)[:left]:
        add[i] += 1
    return [b + a for b, a in zip(base, add)]


def piece_order(style, day):
    if style == "Short focused sessions":
        return (1.0, 1.5, 2.0)
    if style == "Long focused sessions":
        return (2.0, 1.5, 1.0)
    return (1.5, 1.0, 2.0) if day % 2 else (2.0, 1.5, 1.0)  # mix of both


def generate_schedule(subjects, daily_hours, exam_days, style):
    """Build the day-by-day schedule.
    Each day: pick the (up to 3) subjects with the largest remaining target,
    share the day's hours between them by remaining need, and cut each share
    into 1 / 1.5 / 2 hour sessions. Returns a list of dicts
    {subject, day, slot, duration}; the total equals daily_hours * exam_days."""
    cap = day_capacity(daily_hours)
    n = len(subjects)
    exam_days = int(exam_days)
    if n == 0 or exam_days < 1 or cap < 1:
        return []
    names = [s["Subject"] for s in subjects]
    weights = [max(float(s["Weight"]), 1e-6) for s in subjects]
    total_hours = cap * exam_days
    remaining = [total_hours * w / sum(weights) for w in weights]
    out = []
    for day in range(1, exam_days + 1):
        k = min(MAX_SUBJECTS_PER_DAY, n, int(cap // 1))
        chosen = sorted(range(n), key=lambda i: (-remaining[i], -weights[i], i))[:k]
        shares = [max(remaining[i], 0.0) for i in chosen]
        if sum(shares) <= EPS:
            shares = [weights[i] for i in chosen]
        units = allocate_units(int(round(cap * 2)), k, shares)
        slot = 0
        for i, u in sorted(zip(chosen, units), key=lambda t: -weights[t[0]]):
            for piece in split_hours(u / 2, piece_order(style, day)):
                out.append({"subject": names[i], "day": day, "slot": slot, "duration": piece})
                slot += 1
            remaining[i] -= u / 2
    return out


def validate_schedule(sessions, cap):
    """Self-check used by the tests. Returns a list of problems (empty = OK)."""
    problems, by_day, ids = [], {}, set()
    for s in sessions:
        if s["id"] in ids:
            problems.append(f"duplicate id {s['id']}")
        ids.add(s["id"])
        if s["duration"] not in SESSION_OPTIONS:
            problems.append(f"bad duration {s['duration']}")
        if s["day"] is not None:
            by_day.setdefault(s["day"], []).append(s)
    for d, rows in by_day.items():
        if sum(r["duration"] for r in rows) > cap + EPS:
            problems.append(f"day {d} over capacity")
        if len({r["subject"] for r in rows}) > MAX_SUBJECTS_PER_DAY:
            problems.append(f"day {d} has more than 3 subjects")
    return problems


def day_timetable(day_sessions, start=DAY_START_HOUR):
    """Lay one day's sessions on a clock with breaks between them.
    Returns (items, end_hour); item kinds: session / short / long."""
    items, t = [], start
    ordered = sorted(day_sessions, key=lambda s: s["slot"])
    for idx, s in enumerate(ordered):
        items.append({"kind": "session", "start": t, "end": t + s["duration"], "session": s})
        t += s["duration"]
        if idx < len(ordered) - 1:
            long_break = (idx + 1) % 2 == 0
            gap = LONG_BREAK_H if long_break else SHORT_BREAK_H
            items.append({"kind": "long" if long_break else "short",
                          "start": t, "end": t + gap, "session": None})
            t += gap
    return items, t


def plan_reschedule(sessions, current_day, exam_days, cap, locked_days=()):
    """Catch-up planner (pure function).
    Movers = unfinished sessions from days before `current_day` + the backlog.
    Each is placed on the earliest day >= current_day that still has free
    hours and (3-subject rule) room for that subject. Completed sessions are
    never touched. Returns (placed {id: (day, slot)}, unplaced [ids], n_movers)."""
    current_day = max(1, min(int(current_day), int(exam_days)))
    movers = [s for s in sessions
              if not s["completed"] and (s["day"] is None or s["day"] < current_day)]
    movers.sort(key=lambda s: (s["day"] or 0, s["slot"], s["id"]))
    mover_ids = {s["id"] for s in movers}
    load, subs, nxt = {}, {}, {}
    for s in sessions:
        if s["id"] in mover_ids or s["day"] is None:
            continue
        d = s["day"]
        load[d] = load.get(d, 0.0) + s["duration"]
        subs.setdefault(d, set()).add(s["subject"])
        nxt[d] = max(nxt.get(d, 0), s["slot"] + 1)
    placed, unplaced = {}, []
    for s in movers:
        for d in range(current_day, int(exam_days) + 1):
            if d in locked_days:
                continue
            if load.get(d, 0.0) + s["duration"] > cap + EPS:
                continue
            ds = subs.setdefault(d, set())
            if s["subject"] not in ds and len(ds) >= MAX_SUBJECTS_PER_DAY:
                continue
            placed[s["id"]] = (d, nxt.get(d, 0))
            load[d] = load.get(d, 0.0) + s["duration"]
            ds.add(s["subject"])
            nxt[d] = nxt.get(d, 0) + 1
            break
        else:
            unplaced.append(s["id"])
    return placed, unplaced, len(movers)


# ------------------------------------------------------------ persistence
SCHEMA = """
CREATE TABLE IF NOT EXISTS students(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    name_key   TEXT NOT NULL UNIQUE,
    profile    TEXT NOT NULL DEFAULT '{}',
    draft      TEXT NOT NULL DEFAULT '{}',
    language   TEXT NOT NULL DEFAULT 'English',
    theme      TEXT NOT NULL DEFAULT 'Dark',
    created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS plans(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(id),
    status      TEXT NOT NULL DEFAULT 'active',
    start_date  TEXT NOT NULL,
    exam_days   INTEGER NOT NULL,
    daily_hours REAL NOT NULL,
    study_style TEXT,
    subjects    TEXT NOT NULL,
    stress      INTEGER,
    current_day INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT
);
CREATE TABLE IF NOT EXISTS sessions(
    id           TEXT PRIMARY KEY,
    plan_id      INTEGER NOT NULL REFERENCES plans(id),
    subject      TEXT NOT NULL,
    day          INTEGER,                 -- NULL = backlog
    slot         INTEGER NOT NULL,
    duration     REAL NOT NULL,
    completed    INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    original_day INTEGER,
    rescheduled  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS rewards(      -- XP ledger: one row per reward, ever
    student_id INTEGER NOT NULL REFERENCES students(id),
    reward_key TEXT NOT NULL,
    xp         INTEGER NOT NULL,
    created_at TEXT,
    PRIMARY KEY(student_id, reward_key)
);
CREATE TABLE IF NOT EXISTS badges(
    student_id INTEGER NOT NULL REFERENCES students(id),
    badge_key  TEXT NOT NULL,
    earned_at  TEXT,
    PRIMARY KEY(student_id, badge_key)
);
CREATE INDEX IF NOT EXISTS idx_sessions_plan ON sessions(plan_id, day);
"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def db(write=False):
    """One short-lived connection per operation; commit on success, roll back on error."""
    conn = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.close()


def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def db_list_students():
    with db() as c:
        return [(r["id"], r["name"]) for r in
                c.execute("SELECT id, name FROM students ORDER BY updated_at DESC, id DESC")]


def _student_dict(r):
    d = dict(r)
    d["profile"] = json.loads(d["profile"] or "{}")
    d["draft"] = json.loads(d["draft"] or "{}")
    return d


def db_get_student(student_id):
    with db() as c:
        r = c.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    return _student_dict(r) if r else None


def db_find_student_by_key(key):
    with db() as c:
        r = c.execute("SELECT * FROM students WHERE name_key=?", (key,)).fetchone()
    return _student_dict(r) if r else None


def db_save_student(student_id, name, profile, draft, language, theme):
    """Create (student_id None) or update a student. Returns the student id."""
    name = " ".join(str(name).split())
    key, now = norm_name(name), _now()
    with db(True) as c:
        if student_id is None:
            cur = c.execute(
                "INSERT INTO students(name,name_key,profile,draft,language,theme,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (name, key, json.dumps(profile), json.dumps(draft), language, theme, now, now))
            return cur.lastrowid
        c.execute(
            "UPDATE students SET name=?,name_key=?,profile=?,draft=?,language=?,theme=?,updated_at=?"
            " WHERE id=?",
            (name, key, json.dumps(profile), json.dumps(draft), language, theme, now, student_id))
        return student_id


def db_update_prefs(student_id, language, theme):
    with db(True) as c:
        c.execute("UPDATE students SET language=?, theme=?, updated_at=? WHERE id=?",
                  (language, theme, _now(), student_id))


def _plan_dict(r):
    d = dict(r)
    d["subjects"] = json.loads(d["subjects"])
    return d


def db_get_active_plan(student_id):
    with db() as c:
        r = c.execute("SELECT * FROM plans WHERE student_id=? AND status='active'"
                      " ORDER BY id DESC LIMIT 1", (student_id,)).fetchone()
    return _plan_dict(r) if r else None


def _require_plan(c, plan_id, student_id):
    r = c.execute("SELECT * FROM plans WHERE id=? AND student_id=?", (plan_id, student_id)).fetchone()
    if r is None:
        raise PermissionError("plan does not belong to this student")
    return _plan_dict(r)


def db_create_plan(student_id, subjects, daily_hours, exam_days, style, stress, start=None):
    """Archive the student's active plan (kept, never deleted) and store a new one."""
    schedule = generate_schedule(subjects, daily_hours, exam_days, style)
    if not schedule:
        raise ValueError("The schedule is empty - check hours, days and subjects.")
    start = (start or date.today()).isoformat()
    with db(True) as c:
        c.execute("UPDATE plans SET status='archived' WHERE student_id=? AND status='active'",
                  (student_id,))
        cur = c.execute(
            "INSERT INTO plans(student_id,status,start_date,exam_days,daily_hours,study_style,"
            "subjects,stress,current_day,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (student_id, "active", start, int(exam_days), day_capacity(daily_hours), style,
             json.dumps(subjects), stress, 1, _now()))
        pid = cur.lastrowid
        c.executemany(
            "INSERT INTO sessions(id,plan_id,subject,day,slot,duration) VALUES(?,?,?,?,?,?)",
            [(f"P{pid}-{i + 1:04d}", pid, s["subject"], s["day"], s["slot"], s["duration"])
             for i, s in enumerate(schedule)])
    return pid


def _session_dict(r):
    d = dict(r)
    d["completed"] = bool(d["completed"])
    return d


def db_get_sessions(plan_id):
    with db() as c:
        rows = c.execute("SELECT * FROM sessions WHERE plan_id=?"
                         " ORDER BY COALESCE(day,0), slot, id", (plan_id,)).fetchall()
    return [_session_dict(r) for r in rows]


def db_set_current_day(plan_id, student_id, day):
    with db(True) as c:
        plan = _require_plan(c, plan_id, student_id)
        day = max(1, min(int(day), plan["exam_days"]))
        c.execute("UPDATE plans SET current_day=? WHERE id=?", (day, plan_id))


def db_awarded_days(c, student_id, plan_id):
    rows = c.execute("SELECT reward_key FROM rewards WHERE student_id=? AND reward_key LIKE ?",
                     (student_id, f"{plan_id}:d:%")).fetchall()
    return {int(r["reward_key"].split(":")[2]) for r in rows}


def db_reschedule(plan_id, student_id, current_day):
    """Move unfinished past sessions into future days (one atomic transaction).
    Completed sessions are never updated (guarded by `completed=0` in SQL)."""
    with db(True) as c:
        plan = _require_plan(c, plan_id, student_id)
        rows = [_session_dict(r) for r in
                c.execute("SELECT * FROM sessions WHERE plan_id=?", (plan_id,))]
        locked = db_awarded_days(c, student_id, plan_id)
        placed, unplaced, total = plan_reschedule(
            rows, current_day, plan["exam_days"], day_capacity(plan["daily_hours"]), locked)
        old = {r["id"]: r["day"] for r in rows}
        for sid, (d, slot) in placed.items():
            c.execute("UPDATE sessions SET day=?, slot=?, original_day=COALESCE(original_day,?),"
                      " rescheduled=1 WHERE id=? AND plan_id=? AND completed=0",
                      (d, slot, old[sid], sid, plan_id))
        for sid in unplaced:
            c.execute("UPDATE sessions SET day=NULL, original_day=COALESCE(original_day,?),"
                      " rescheduled=1 WHERE id=? AND plan_id=? AND completed=0",
                      (old[sid], sid, plan_id))
        c.execute("UPDATE plans SET current_day=? WHERE id=?",
                  (max(1, min(int(current_day), plan["exam_days"])), plan_id))
    return {"moved": len(placed), "backlog": len(unplaced), "total": total}


# ----------------------------------------------------------- XP and badges
def _grant(c, student_id, key, xp):
    """Insert a reward once. The PRIMARY KEY makes a duplicate impossible."""
    cur = c.execute("INSERT OR IGNORE INTO rewards(student_id,reward_key,xp,created_at)"
                    " VALUES(?,?,?,?)", (student_id, key, xp, _now()))
    return xp if cur.rowcount == 1 else 0


def _xp_total(c, student_id):
    return c.execute("SELECT COALESCE(SUM(xp),0) FROM rewards WHERE student_id=?",
                     (student_id,)).fetchone()[0]


def level_for_xp(xp):
    idx = max(i for i, lv in enumerate(LEVELS) if xp >= lv[1])
    nxt = LEVELS[idx + 1] if idx + 1 < len(LEVELS) else None
    if nxt is None:
        progress, need, nxt_key = 1.0, 0, None
    else:
        span = nxt[1] - LEVELS[idx][1]
        progress = (xp - LEVELS[idx][1]) / span
        need, nxt_key = nxt[1] - xp, nxt[0]
    return {"index": idx, "key": LEVELS[idx][0], "emoji": LEVELS[idx][2],
            "progress": progress, "xp_to_next": need, "next_key": nxt_key}


def db_complete_session(student_id, plan_id, session_id):
    """Mark ONE session complete and award XP / badges - atomically.
    A second call for the same session changes nothing and rewards nothing."""
    res = {"newly_completed": False, "xp_gained": 0, "day_completed": None,
           "plan_completed": False, "new_badges": [], "level_up": False, "subject": ""}
    with db(True) as c:
        _require_plan(c, plan_id, student_id)
        row = c.execute("SELECT * FROM sessions WHERE id=? AND plan_id=?",
                        (session_id, plan_id)).fetchone()
        if row is None or row["completed"]:
            return res
        xp_before = _xp_total(c, student_id)
        c.execute("UPDATE sessions SET completed=1, completed_at=? WHERE id=? AND completed=0",
                  (_now(), session_id))
        res["newly_completed"] = True
        res["subject"] = row["subject"]
        res["xp_gained"] += _grant(c, student_id, f"{plan_id}:s:{session_id}", XP_SESSION)
        if row["day"] is not None:
            pending = c.execute("SELECT COUNT(*) FROM sessions WHERE plan_id=? AND day=?"
                                " AND completed=0", (plan_id, row["day"])).fetchone()[0]
            if pending == 0:
                bonus = _grant(c, student_id, f"{plan_id}:d:{row['day']}", XP_DAY_BONUS)
                if bonus:
                    res["day_completed"] = row["day"]
                    res["xp_gained"] += bonus
        left = c.execute("SELECT COUNT(*) FROM sessions WHERE plan_id=? AND completed=0",
                         (plan_id,)).fetchone()[0]
        res["plan_completed"] = left == 0
        done_total = c.execute(
            "SELECT COUNT(*) FROM sessions s JOIN plans p ON p.id=s.plan_id"
            " WHERE p.student_id=? AND s.completed=1", (student_id,)).fetchone()[0]
        day_rewards = c.execute("SELECT COUNT(*) FROM rewards WHERE student_id=? AND reward_key"
                                " LIKE '%:d:%'", (student_id,)).fetchone()[0]
        earned = []
        if done_total >= 1:
            earned.append("first_session")
        if done_total >= 5:
            earned.append("five_sessions")
        if done_total >= 10:
            earned.append("ten_sessions")
        if day_rewards >= 1:
            earned.append("first_day")
        if left == 0:
            earned.append("plan_complete")
        for b in earned:
            cur = c.execute("INSERT OR IGNORE INTO badges(student_id,badge_key,earned_at)"
                            " VALUES(?,?,?)", (student_id, b, _now()))
            if cur.rowcount == 1:
                res["new_badges"].append(b)
        xp_after = _xp_total(c, student_id)
        res["level_up"] = level_for_xp(xp_after)["index"] > level_for_xp(xp_before)["index"]
    return res


def db_xp_summary(student_id):
    with db() as c:
        total = _xp_total(c, student_id)
        day_xp = c.execute("SELECT COALESCE(SUM(xp),0) FROM rewards WHERE student_id=? AND"
                           " reward_key LIKE '%:d:%'", (student_id,)).fetchone()[0]
    return {"total": total, "days": day_xp, "sessions": total - day_xp}


def db_badges(student_id):
    with db() as c:
        return {r["badge_key"] for r in
                c.execute("SELECT badge_key FROM badges WHERE student_id=?", (student_id,))}


# ------------------------------------------------------------- statistics
def compute_stats(sessions, plan):
    """All dashboard numbers come from this single function, so they always agree."""
    total = len(sessions)
    done = sum(1 for s in sessions if s["completed"])
    hours_total = sum(s["duration"] for s in sessions)
    hours_done = sum(s["duration"] for s in sessions if s["completed"])
    cur = plan["current_day"]
    backlog = sum(1 for s in sessions if s["day"] is None and not s["completed"])
    overdue = sum(1 for s in sessions
                  if s["day"] is not None and s["day"] < cur and not s["completed"])
    by_subject, by_day = {}, {d: [0.0, 0.0] for d in range(1, plan["exam_days"] + 1)}
    for s in sessions:
        e = by_subject.setdefault(s["subject"], [0.0, 0.0])
        e[1] += s["duration"]
        if s["completed"]:
            e[0] += s["duration"]
        if s["day"] in by_day:
            by_day[s["day"]][1] += s["duration"]
            if s["completed"]:
                by_day[s["day"]][0] += s["duration"]
    return {
        "total": total, "done": done, "pending": total - done,
        "pct": (done / total * 100) if total else 0.0,
        "hours_total": hours_total, "hours_done": hours_done,
        "hours_left": hours_total - hours_done,
        "overdue": overdue, "backlog": backlog,
        "by_subject": by_subject, "by_day": by_day,
    }


def day_date(plan, day):
    return date.fromisoformat(plan["start_date"]) + timedelta(days=day - 1)


# ===== LOGIC END =====

# ==================================================
# 1. PAGE CONFIG
# ==================================================
st.set_page_config(
    page_title="Academic & Stress Management",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_resource
def _boot_db():
    init_db()
    return True


_boot_db()

# ==================================================
# 2. SESSION STATE
# ==================================================
defaults = {
    "step": 0,
    "language": "English",
    "theme_mode": "Dark",
    "student_id": None,          # which saved student is active (None = nobody yet)
    "student_name": "",
    "study_level": "University student",
    "daily_hours": 4.0,
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
LEVEL_OPTIONS = ["University student", "High school student", "Preparatory student", "Other"]
STYLE_OPTIONS = ["Short focused sessions", "Long focused sessions", "Mix of both"]
PROFILE_KEYS = ("study_level", "daily_hours", "exam_days", "study_style",
                "stress_score", "sleep_score", "focus_score", "workload")

ACCENT = "#6366f1"
GREEN = "#34d399"


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


# ==================================================
# 3. TRANSLATIONS
# ==================================================
# --- Original strings (substring based, used through tr()) ---
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
    """Translate visible UI strings while keeping internal rule values unchanged."""
    if not isinstance(value, str):
        return value
    if st.session_state.get("language", "English") != "Arabic":
        return value
    result = value
    for en, ar in sorted(TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True):
        result = result.replace(en, ar)
    return result


def html(markup):
    """Render HTML, translating visible content when Arabic is selected.
    Use ONLY for static markup (no user-typed text inside)."""
    cleaned = "\n".join(line.strip() for line in markup.strip().splitlines())
    cleaned = tr(cleaned)
    st.markdown(cleaned, unsafe_allow_html=True)


def html_raw(markup):
    """Render HTML WITHOUT the substring translator. Callers must escape any
    user-typed text with esc() and translate with t() themselves."""
    cleaned = "\n".join(line.strip() for line in markup.strip().splitlines() if line.strip())
    st.markdown(cleaned, unsafe_allow_html=True)


# --- New strings: explicit (English, Arabic) pairs used through t() ---
UI = {
    # navigation
    "nav_dashboard": ("Dashboard", "لوحة المتابعة"),
    "nav_schedule": ("Daily schedule", "الجدول اليومي"),
    "nav_analytics": ("Analytics", "التحليلات"),
    "nav_overview": ("Plan overview", "نظرة عامة"),
    # persistence / profiles
    "saved_title": ("Welcome back?", "أهلًا بعودتك؟"),
    "saved_help": ("Choose your saved profile to continue where you stopped. Progress is stored on this device.",
                   "اختر ملفك المحفوظ لتكمل من حيث توقفت. يتم حفظ التقدم على هذا الجهاز."),
    "saved_placeholder": ("Choose a saved student", "اختر طالبًا محفوظًا"),
    "saved_load": ("Load saved progress", "تحميل التقدم المحفوظ"),
    "signed_in": ("Saved profile loaded: {name}", "تم تحميل الملف المحفوظ: {name}"),
    "name_taken": ("A saved student named “{name}” already exists. Load that profile from the list above, or use a different name.",
                   "يوجد طالب محفوظ باسم “{name}”. حمّل ملفه من القائمة أعلاه أو استخدم اسمًا مختلفًا."),
    "name_long": ("Please use a name of 60 characters or fewer.", "من فضلك استخدم اسمًا لا يزيد عن 60 حرفًا."),
    "err_dup": ("Subject names must be different from each other.", "يجب أن تكون أسماء المواد مختلفة عن بعضها."),
    "err_empty": ("Please enter at least one subject name.", "من فضلك اكتب اسم مادة واحدة على الأقل."),
    "active_plan_note": ("You already have an active plan. Creating a new one archives it. Your XP, badges and completed sessions are kept.",
                         "لديك خطة نشطة بالفعل. إنشاء خطة جديدة سيؤرشف الخطة الحالية، وتبقى نقاط الخبرة والشارات والجلسات المكتملة محفوظة."),
    "confirm_new": ("Archive my current plan and create a new one", "أرشفة خطتي الحالية وإنشاء خطة جديدة"),
    "confirm_needed": ("Please tick the confirmation box to replace your active plan.",
                       "من فضلك فعّل مربع التأكيد لاستبدال خطتك النشطة."),
    "db_error": ("Could not save your data: {err}", "تعذّر حفظ بياناتك: {err}"),
    "saved_note": ("💾 Progress is saved automatically on this device.", "💾 يتم حفظ تقدمك تلقائيًا على هذا الجهاز."),
    "no_plan": ("No active plan found. Please create one first.", "لا توجد خطة نشطة. من فضلك أنشئ خطة أولًا."),
    "start_over_help": ("Start over clears this screen only. Your saved data stays on the device and can be loaded again.",
                        "البدء من جديد يمسح هذه الشاشة فقط. بياناتك المحفوظة تبقى على الجهاز ويمكنك تحميلها مرة أخرى."),
    "new_plan": ("Create a new plan", "إنشاء خطة جديدة"),
    # dashboard
    "completion": ("Overall completion", "نسبة الإنجاز الكلية"),
    "completed": ("Completed sessions", "الجلسات المكتملة"),
    "pending": ("Pending sessions", "الجلسات المتبقية"),
    "hours_done": ("Hours completed", "ساعات منجزة"),
    "hours_left": ("Hours remaining", "ساعات متبقية"),
    "overdue": ("Overdue + backlog", "متأخرة + مؤجلة"),
    "of": ("of", "من"),
    "h": ("h", "س"),
    "xp": ("XP", "نقطة خبرة"),
    "level": ("Level", "المستوى"),
    "xp_to_next": ("{n} XP to reach {level}", "{n} نقطة للوصول إلى {level}"),
    "max_level": ("Top level reached", "وصلت لأعلى مستوى"),
    "lvl_beginner": ("Beginner", "مبتدئ"),
    "lvl_focused": ("Focused Learner", "متعلم مركّز"),
    "lvl_champion": ("Study Champion", "بطل المذاكرة"),
    "lvl_master": ("Study Master", "أستاذ المذاكرة"),
    "buddy_title": ("Your study buddy", "رفيق المذاكرة"),
    "badges": ("Achievement badges", "شارات الإنجاز"),
    "badge_first_session": ("First step", "الخطوة الأولى"),
    "badge_five_sessions": ("Five sessions", "خمس جلسات"),
    "badge_ten_sessions": ("Ten sessions", "عشر جلسات"),
    "badge_first_day": ("Perfect day", "يوم مثالي"),
    "badge_plan_complete": ("Plan complete", "الخطة مكتملة"),
    "badge_d_first_session": ("Complete your first session", "أكمل أول جلسة"),
    "badge_d_five_sessions": ("Complete 5 sessions", "أكمل 5 جلسات"),
    "badge_d_ten_sessions": ("Complete 10 sessions", "أكمل 10 جلسات"),
    "badge_d_first_day": ("Finish every session of one study day", "أنهِ كل جلسات يوم دراسي واحد"),
    "badge_d_plan_complete": ("Complete the entire study plan", "أكمل خطة المذاكرة بالكامل"),
    "badge_locked": ("Locked", "مقفلة"),
    # motivation
    "m_session": ("Great job! You finished a {subject} session (+{xp} XP).",
                  "أحسنت! أنهيت جلسة {subject} (+{xp} نقطة خبرة)."),
    "m_day": ("Full day completed! Day {day} is done: +{xp} XP including the day bonus. Take a well-earned rest.",
              "اكتمل اليوم بالكامل! أنهيت اليوم {day}: +{xp} نقطة خبرة مع مكافأة اليوم. استرح، فقد استحققت ذلك."),
    "m_plan": ("🎉 You completed the entire study plan! Be proud of the consistency you showed.",
               "🎉 أكملت خطة المذاكرة بالكامل! افتخر بالالتزام الذي أظهرته."),
    "m_levelup": ("Level up: you are now a {level}!", "ارتقيت إلى مستوى جديد: أنت الآن {level}!"),
    "m_badge": ("New badge: {names}", "شارة جديدة: {names}"),
    "m_overdue": ("You have {n} unfinished session(s) from earlier days. That is completely fine - use “Reschedule missed sessions” and keep going.",
                  "لديك {n} جلسة غير مكتملة من أيام سابقة. لا مشكلة إطلاقًا، استخدم «إعادة جدولة الجلسات الفائتة» وواصل."),
    "m_idle": ("Ready when you are! Start with just one session today. I'll be right here.",
               "جاهز عندما تكون جاهزًا! ابدأ بجلسة واحدة فقط اليوم، وأنا هنا بجانبك."),
    "m_low": ("Every big journey starts small - {done} of {total} sessions done. One more session today is a great step.",
              "كل رحلة كبيرة تبدأ صغيرة، أنجزت {done} من {total} جلسة. جلسة واحدة إضافية اليوم خطوة رائعة."),
    "m_good": ("Nice momentum! {done} of {total} sessions done. Keep it steady.",
               "زخم جميل! أنجزت {done} من {total} جلسة. حافظ على هذا الإيقاع."),
    "m_close": ("You are close to the finish line - only {left} session(s) left!",
                "اقتربت من خط النهاية، تبقّت {left} جلسة فقط!"),
    "buddy_beginner": ("Just hatched", "فقس للتو"),
    "buddy_focused": ("Growing fast", "ينمو بسرعة"),
    "buddy_champion": ("Wise and steady", "حكيم وثابت"),
    "buddy_master": ("Soaring high", "يحلّق عاليًا"),
    # schedule
    "current_day": ("Current study day", "يوم المذاكرة الحالي"),
    "day": ("Day", "اليوم"),
    "resched_btn": ("Reschedule missed sessions", "إعادة جدولة الجلسات الفائتة"),
    "resched_none": ("Nothing to reschedule - you are on track.", "لا شيء لإعادة جدولته، أنت على المسار الصحيح."),
    "resched_pending": ("{n} unfinished session(s) from earlier days or the backlog can be rescheduled.",
                        "يمكن إعادة جدولة {n} جلسة غير مكتملة من أيام سابقة أو من قائمة المؤجلات."),
    "resched_result": ("Rescheduled {moved} of {total} unfinished sessions. {backlog} remain in the backlog.",
                       "تمت إعادة جدولة {moved} من {total} جلسة غير مكتملة. تبقّى {backlog} في قائمة المؤجلات."),
    "backlog": ("Backlog", "المؤجلات"),
    "backlog_note": ("These sessions did not fit into the remaining days yet. They stay here until space opens up.",
                     "هذه الجلسات لم تجد مكانًا في الأيام المتبقية بعد، وتبقى هنا حتى يتوفر وقت."),
    "from_day": ("from day {d}", "من اليوم {d}"),
    "moved_tag": ("moved", "نُقلت"),
    "no_sessions_day": ("No sessions on this day.", "لا توجد جلسات في هذا اليوم."),
    "lock_note": ("Tick a session when you finish it. Completed sessions are locked so XP can never be counted twice.",
                  "ضع علامة على الجلسة عند إنهائها. الجلسات المكتملة مقفلة حتى لا تُحتسب نقاطها مرتين."),
    "late_warn": ("Day {d} ends after 10 PM. Consider fewer daily hours or an earlier start to protect your sleep.",
                  "اليوم {d} ينتهي بعد العاشرة مساءً. فكّر في تقليل الساعات اليومية أو البدء مبكرًا للحفاظ على نومك."),
    "break_short": ("Short break", "استراحة قصيرة"),
    "break_long": ("Long break / meal", "استراحة طويلة / وجبة"),
    # analytics
    "ch_sessions": ("Completed vs pending sessions", "الجلسات المكتملة مقابل المتبقية"),
    "ch_subject": ("Subject-wise progress (hours)", "التقدم حسب المادة (ساعات)"),
    "ch_daily": ("Daily progress (hours)", "التقدم اليومي (ساعات)"),
    "lbl_done": ("Completed", "مكتملة"),
    "lbl_pending": ("Pending", "متبقية"),
    "lbl_day": ("Day", "اليوم"),
    "lbl_today": ("Current day", "اليوم الحالي"),
    "xp_levels": ("XP and levels", "نقاط الخبرة والمستويات"),
    "xp_sessions": ("XP from sessions", "نقاط من الجلسات"),
    "xp_days": ("Full-day bonuses", "مكافآت الأيام الكاملة"),
    "xp_total": ("Total XP", "إجمالي النقاط"),
    # overview / export
    "scheduled_hours": ("Scheduled hours", "الساعات المجدولة"),
    "dl_schedule": ("Download full schedule", "تحميل الجدول الكامل"),
    "col_day": ("Day", "اليوم"),
    "col_date": ("Date", "التاريخ"),
    "col_start": ("Start", "البداية"),
    "col_end": ("End", "النهاية"),
    "col_subject": ("Subject", "المادة"),
    "col_hours": ("Hours", "الساعات"),
    "col_status": ("Status", "الحالة"),
    "st_done": ("Completed", "مكتملة"),
    "st_pending": ("Pending", "متبقية"),
    "st_backlog": ("Backlog", "مؤجلة"),
    "daily_template_note": ("A typical day, based on each subject's share of your hours. The exact day-by-day plan is in “Daily schedule”.",
                            "يوم نموذجي بحسب نصيب كل مادة من ساعاتك. الخطة التفصيلية لكل يوم في «الجدول اليومي»."),
}

WEEKDAYS_AR = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]


def t(key, **kw):
    en, ar = UI[key]
    text = ar if st.session_state.get("language") == "Arabic" else en
    return text.format(**kw) if kw else text


def level_name(key):
    return t(f"lvl_{key}")


def fmt_date(d):
    if st.session_state.get("language") == "Arabic":
        return f"{WEEKDAYS_AR[d.weekday()]} {d.day}/{d.month}"
    return d.strftime("%a %d %b")


def md_safe(text):
    """Escape characters that Markdown would interpret inside widget labels."""
    for ch in ("\\", "`", "*", "_", "[", "]", "$", "~", "<", ">", "#"):
        text = text.replace(ch, "\\" + ch)
    return text


# --- chart text helpers (Arabic shaping is optional, see imports) ---
def ctext(s):
    if st.session_state.language == "Arabic" and HAS_SHAPING:
        return get_display(arabic_reshaper.reshape(str(s)))
    return str(s)


def tc(key, **kw):
    """Chart label: Arabic only when shaping libraries are installed."""
    if st.session_state.language == "Arabic" and not HAS_SHAPING:
        en = UI[key][0]
        return en.format(**kw) if kw else en
    return ctext(t(key, **kw))


def chart_palette():
    light = st.session_state.theme_mode == "Light"
    return {
        "bg": "#f4f6fb" if light else "#0b0f19",
        "text": "#172033" if light else "#e5e7eb",
        "muted": "#475569" if light else "#94a3b8",
        "grid": "#d8deea" if light else "#1f2937",
        "pending": "#c4ccdc" if light else "#334155",
    }


# ==================================================
# 3b. PERSISTENCE GLUE (session_state <-> SQLite)
# ==================================================
def save_current_student():
    """Write profile + subject draft + prefs of the ACTIVE student to SQLite."""
    ss = st.session_state
    name = " ".join(str(ss.student_name).split())
    if not name:
        return None
    profile = {k: ss[k] for k in PROFILE_KEYS}
    draft = {
        "subject_count": int(ss.subject_count),
        "subjects": [
            {"name": ss.get(f"subject_name_{i}", ""),
             "difficulty": ss.get(f"difficulty_{i}", "Easy"),
             "priority": ss.get(f"priority_{i}", "Normal")}
            for i in range(MAX_SUBJECTS)
        ],
    }
    ss.student_id = db_save_student(ss.student_id, name, profile, draft,
                                    ss.language, ss.theme_mode)
    return ss.student_id


def persist_prefs():
    """Language/theme only - never touches the student's name or profile."""
    if st.session_state.student_id:
        try:
            db_update_prefs(st.session_state.student_id, st.session_state.language,
                            st.session_state.theme_mode)
        except sqlite3.Error:
            pass


def cb_load_student():
    """Button callback: copy a saved student into session_state."""
    ss = st.session_state
    sid = ss.get("load_choice")
    if not sid:
        return
    s = db_get_student(sid)
    if not s:
        return
    ss.student_id = s["id"]
    ss.student_name = s["name"]
    p = s["profile"]
    if p.get("study_level") in LEVEL_OPTIONS:
        ss.study_level = p["study_level"]
    if p.get("study_style") in STYLE_OPTIONS:
        ss.study_style = p["study_style"]
    if p.get("workload") in WORKLOAD_SCORES:
        ss.workload = p["workload"]
    try:
        ss.daily_hours = float(min(12.0, max(1.0, float(p.get("daily_hours", 4)))))
        ss.exam_days = int(min(90, max(1, int(p.get("exam_days", 14)))))
        for k in ("stress_score", "sleep_score", "focus_score"):
            ss[k] = int(min(10, max(0, int(p.get(k, 5)))))
    except (TypeError, ValueError):
        pass
    draft = s["draft"]
    ss.subject_count = int(min(MAX_SUBJECTS, max(1, draft.get("subject_count", 3))))
    subs = draft.get("subjects", [])
    for i in range(MAX_SUBJECTS):
        d = subs[i] if i < len(subs) else {}
        ss[f"subject_name_{i}"] = d.get("name", "")
        ss[f"difficulty_{i}"] = d.get("difficulty") if d.get("difficulty") in DIFFICULTY_WEIGHT else "Easy"
        ss[f"priority_{i}"] = d.get("priority") if d.get("priority") in PRIORITY_WEIGHT else "Normal"
    ss.language = s["language"] if s["language"] in ("English", "Arabic") else "English"
    ss.theme_mode = s["theme"] if s["theme"] in ("Dark", "Light") else "Dark"
    has_plan = db_get_active_plan(s["id"]) is not None
    ss.step = 3 if has_plan else 0
    if not has_plan:
        ss.loaded_notice = s["name"]   # shown on step 1; with a plan we jump to the plan


def cb_complete(session_id, plan_id, student_id, widget_key):
    """Checkbox callback: runs BEFORE the page re-renders, so every number on
    the dashboard is already up to date in the same run."""
    if not st.session_state.get(widget_key):
        return
    try:
        res = db_complete_session(student_id, plan_id, session_id)
    except sqlite3.Error:
        return
    if res["newly_completed"]:
        st.session_state.last_event = res


def cb_set_day(plan_id, student_id, widget_key):
    try:
        db_set_current_day(plan_id, student_id, st.session_state[widget_key])
    except sqlite3.Error:
        pass


# ==================================================
# 4. DESIGN SYSTEM
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
    --good: #34d399;
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
.metric .unit { font-size: 14px; font-weight: 500; color: var(--muted); margin-inline-start: 4px; }

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

/* ---------- Study buddy, XP, badges (new) ---------- */
.buddy {
    display: flex; gap: 20px; align-items: center;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 16px; padding: 22px 24px; height: 100%;
}
.buddy .emoji {
    font-size: 58px; line-height: 1; width: 96px; height: 96px; min-width: 96px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 50%; background: var(--surface-2); border: 1px solid var(--border-strong);
}
.buddy .who { font-size: 13px; font-weight: 600; color: var(--muted); }
.buddy .bubble {
    margin-top: 8px; padding: 12px 14px; border-radius: 12px;
    background: var(--surface-2); border: 1px solid var(--border);
    font-size: 14px; line-height: 1.65; color: var(--text);
}
.buddy .bubble.celebrate { border-color: var(--good); }
.xpcard {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 16px; padding: 22px 24px; height: 100%;
}
.xpcard .lvl { font-size: 20px; font-weight: 700; color: #f8fafc; }
.xpcard .xpnum { font-size: 13px; color: var(--muted); margin-top: 2px; }
.bar.big { height: 10px; margin: 14px 0 8px; }
.ladder { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
.ladder .rung {
    font-size: 12px; padding: 4px 10px; border-radius: 999px;
    border: 1px solid var(--border-strong); color: var(--faint);
}
.ladder .rung.on { border-color: var(--accent); color: var(--text); background: rgba(99,102,241,0.12); }
.chips { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 4px; }
.chip {
    display: flex; align-items: center; gap: 8px;
    background: var(--surface); border: 1px solid var(--border-strong);
    border-radius: 999px; padding: 8px 14px; font-size: 13px; color: var(--text);
}
.chip.off { opacity: 0.45; filter: grayscale(1); }
.brk { color: var(--faint); font-size: 12px; margin: 2px 0 2px 34px; margin-inline-start: 34px; }

/* ---------- Inputs ---------- */
div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="textarea"] {
    background-color: var(--surface-2) !important;
    border-color: var(--border-strong) !important;
    border-radius: 10px !important;
}
div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea { color: #f8fafc !important; }
[data-testid="stWidgetLabel"] p { font-size: 13px; font-weight: 500; color: var(--muted); }

[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: var(--border) !important;
    background: var(--surface-2);
    border-radius: 14px !important;
}
[data-testid="stExpander"] { border-color: var(--border) !important; border-radius: 12px !important; }
button[data-baseweb="tab"] p { font-weight: 600; color: var(--muted); }
button[data-baseweb="tab"][aria-selected="true"] p { color: var(--text); }

/* ---------- Buttons ---------- */
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
@media (max-width: 720px) {
    .buddy { flex-direction: column; text-align: center; }
    .st-key-slide_card { padding: 20px; }
}
</style>
""", unsafe_allow_html=True)

# Language and theme controls. These only change presentation, not the expert-system logic.
toolbar_left, toolbar_right = st.columns([1, 1])
with toolbar_left:
    lang_label = "🌐 العربية" if st.session_state.language == "English" else "🌐 English"
    if st.button(lang_label, key="toggle_language", help="Switch interface language"):
        st.session_state.language = "Arabic" if st.session_state.language == "English" else "English"
        persist_prefs()
        st.rerun()

with toolbar_right:
    theme_label = "☀️ Light theme" if st.session_state.theme_mode == "Dark" else "🌙 Dark theme"
    if st.button(tr(theme_label), key="toggle_theme", help="Switch between dark and light themes"):
        st.session_state.theme_mode = "Light" if st.session_state.theme_mode == "Dark" else "Dark"
        persist_prefs()
        st.rerun()

if st.session_state.theme_mode == "Light":
    st.markdown("""
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
        --good: #059669;
    }
    .stApp { background: var(--bg) !important; color: var(--text) !important; }
    h1, h2, h3, h4, p, label, span { color: var(--text); }
    .app-title, .card-title, .step.current .name, .section-title,
    .metric .value, .xpcard .lvl { color: #172033 !important; }
    .st-key-slide_card, .metric, .tip { background: #ffffff !important; }
    .estimate, .note, [data-testid="stVerticalBlockBorderWrapper"] { background: #edf1f8 !important; }
    div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea { color: #172033 !important; }
    .stButton > button[data-testid="stBaseButton-secondary"],
    .stDownloadButton > button { color: #172033 !important; }
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
# 5. HEADER AND STEPPER
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

    # --- NEW: load a saved student (restores profile, subjects, plan, XP) ---
    try:
        saved_students = db_list_students()
    except sqlite3.Error:
        saved_students = []
    if st.session_state.get("loaded_notice"):
        st.success(t("signed_in", name=st.session_state.pop("loaded_notice")))
    if saved_students:
        with st.container(border=True):
            html_raw(f'<div class="subject-label">{esc(t("saved_title"))}</div>'
                     f'<div class="muted">{esc(t("saved_help"))}</div>')
            lc1, lc2 = st.columns([3, 1])
            with lc1:
                st.selectbox(
                    t("saved_placeholder"), [sid for sid, _ in saved_students],
                    index=None, placeholder=t("saved_placeholder"),
                    format_func=lambda sid: dict(saved_students).get(sid, str(sid)),
                    key="load_choice", label_visibility="collapsed",
                )
            with lc2:
                st.button(t("saved_load"), key="load_btn", on_click=cb_load_student)

    with st.container(key="slide_card"):
        html("""
        <div class="card-eyebrow">Step 1 · Profile</div>
        <div class="card-title">Let’s get to know you</div>
        <p class="muted">Enter your information to personalize your study plan.</p>
        """)

        st.text_input(tr("Student name"), key="student_name", placeholder=tr("Enter your name"))

        col1, col2 = st.columns(2, gap="large")

        with col1:
            st.selectbox(
                tr("Academic level"),
                LEVEL_OPTIONS,
                format_func=tr,
                key="study_level",
            )
            st.slider(tr("Available study hours per day"), 1.0, 12.0, step=0.5, key="daily_hours")

        with col2:
            st.selectbox(
                tr("Preferred study style"),
                STYLE_OPTIONS,
                format_func=tr,
                key="study_style",
            )
            st.slider(tr("Days remaining until exam or deadline"), 1, 90, key="exam_days")

        html("""
        <div class="note"><b>Tip.</b> A balanced and realistic routine is easier to maintain than an overloaded schedule.</div>
        """)

    _, next_col = st.columns([3, 1])
    with next_col:
        if st.button(tr("Continue"), key="profile_next", type="primary"):
            clean_name = " ".join(st.session_state.student_name.split())
            if not clean_name:
                st.error(tr("Please enter your name before continuing."))
            elif len(clean_name) > 60:
                st.error(t("name_long"))
            else:
                try:
                    existing = db_find_student_by_key(norm_name(clean_name))
                    if existing and existing["id"] != st.session_state.student_id:
                        # Same name as ANOTHER saved student: never overwrite it silently.
                        st.error(t("name_taken", name=clean_name))
                    else:
                        if existing is None and st.session_state.student_id is not None:
                            # A different, new name = a different student record.
                            # The previously loaded student's data stays untouched.
                            st.session_state.student_id = None
                        save_current_student()
                        go_next()
                        st.rerun()
                except sqlite3.Error as err:
                    st.error(t("db_error", err=err))

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
            st.select_slider(
                tr("How manageable is your workload?"),
                options=list(WORKLOAD_SCORES.keys()),
                format_func=tr,
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
        if st.button(tr("Back"), key="stress_back"):
            go_back()
            st.rerun()
    with next_col:
        if st.button(tr("Continue"), key="stress_next", type="primary"):
            try:
                save_current_student()
            except sqlite3.Error as err:
                st.error(t("db_error", err=err))
            go_next()
            st.rerun()

# ==================================================
# STEP 3: SUBJECT PLANNING
# ==================================================
elif current_step == 2:

    active_plan = None
    if st.session_state.student_id:
        try:
            active_plan = db_get_active_plan(st.session_state.student_id)
        except sqlite3.Error:
            active_plan = None

    with st.container(key="slide_card"):
        html("""
        <div class="card-eyebrow">Step 3 · Study planning</div>
        <div class="card-title">Organize your subjects</div>
        <p class="muted">Add each subject and set its difficulty and priority.</p>
        """)

        st.number_input(
            tr("How many subjects do you have?"),
            min_value=1,
            max_value=MAX_SUBJECTS,
            step=1,
            key="subject_count",
        )

        raw_subjects = []

        for i in range(int(st.session_state.subject_count)):
            with st.container(border=True):
                html(f'<div class="subject-label">{tr("SUBJECT")} {i + 1}</div>')

                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    subject = st.text_input(
                        tr("Subject name"),
                        key=f"subject_name_{i}",
                        placeholder=f"{tr('Subject name')} {i + 1}",
                        max_chars=40,
                    )
                with c2:
                    difficulty = st.selectbox(
                        tr("Difficulty"), ["Easy", "Medium", "Hard"], format_func=tr, key=f"difficulty_{i}"
                    )
                with c3:
                    priority = st.selectbox(
                        tr("Priority"),
                        ["Normal", "Important", "Very important"],
                        format_func=tr,
                        key=f"priority_{i}",
                    )
            raw_subjects.append((subject, difficulty, priority))

        subjects_data, subjects_error = build_subjects(raw_subjects)
        st.session_state.subjects_data = subjects_data

        html("""
        <div class="note"><b>How it works.</b> Harder and more important subjects receive a larger share of your available study hours.</div>
        """)

        # NEW: starting a new plan archives the active one - ask first, never delete.
        confirm_new = True
        if active_plan:
            st.info(t("active_plan_note"))
            confirm_new = st.checkbox(t("confirm_new"), key="confirm_new_plan")

    back_col, next_col = st.columns(2)
    with back_col:
        if st.button(tr("Back"), key="subjects_back"):
            try:
                save_current_student()
            except sqlite3.Error:
                pass
            go_back()
            st.rerun()
    with next_col:
        if st.button(tr("Generate plan"), key="subjects_next", type="primary"):
            if subjects_error == "empty":
                st.error(t("err_empty"))
            elif subjects_error == "duplicate":
                st.error(t("err_dup"))
            elif not confirm_new:
                st.error(t("confirm_needed"))
            else:
                try:
                    sid = save_current_student()
                    if sid is None:
                        st.error(tr("Please enter your name before continuing."))
                    else:
                        db_create_plan(
                            sid, subjects_data, st.session_state.daily_hours,
                            st.session_state.exam_days, st.session_state.study_style,
                            compute_stress(),
                        )
                        go_next()
                        st.rerun()
                except (sqlite3.Error, ValueError) as err:
                    st.error(t("db_error", err=err))

# ==================================================
# STEP 4: RESULTS
# ==================================================
elif current_step == 3:

    # ------------------------------------------------------------------
    # Small rendering helpers for the new analytics UI
    # ------------------------------------------------------------------
    def metric_card(label, value, unit="", color=None):
        style = f' style="color:{color}"' if color else ""
        unit_html = f'<span class="unit">{esc(unit)}</span>' if unit else ""
        return (f'<div class="metric"><div class="label">{esc(label)}</div>'
                f'<div class="value"{style}>{esc(str(value))}{unit_html}</div></div>')

    def progress_bar(fraction, color=ACCENT, big=False):
        pct = max(0.0, min(1.0, fraction)) * 100
        cls = "bar big" if big else "bar"
        return f'<div class="{cls}"><div style="width:{pct:.1f}%;background:{color}"></div></div>'

    def motivation(stats, lvl, event):
        """Pick ONE message that reflects the student's real progress."""
        if event:
            if event["plan_completed"]:
                kind, text = "celebrate", t("m_plan")
            elif event["day_completed"]:
                kind, text = "celebrate", t("m_day", day=event["day_completed"], xp=event["xp_gained"])
            else:
                kind, text = "celebrate", t("m_session", subject=event["subject"], xp=event["xp_gained"])
            if event["level_up"]:
                text += " " + t("m_levelup", level=level_name(lvl["key"]))
            if event["new_badges"]:
                names = ", ".join(t(f"badge_{b}") for b in event["new_badges"])
                text += " 🏅 " + t("m_badge", names=names)
            return kind, text
        if stats["total"] and stats["pending"] == 0:
            return "celebrate", t("m_plan")
        late = stats["overdue"] + stats["backlog"]
        if late > 0:
            return "info", t("m_overdue", n=late)
        if stats["done"] == 0:
            return "info", t("m_idle")
        if stats["pct"] < 30:
            return "info", t("m_low", done=stats["done"], total=stats["total"])
        if stats["pct"] >= 75:
            return "info", t("m_close", left=stats["pending"])
        return "info", t("m_good", done=stats["done"], total=stats["total"])

    def schedule_dataframe(sessions, plan):
        """Full day-by-day schedule as a table (also used for the CSV export)."""
        rows, by_day = [], {}
        for s in sessions:
            by_day.setdefault(s["day"], []).append(s)
        for d in range(1, plan["exam_days"] + 1):
            items, _ = day_timetable(by_day.get(d, []))
            for it in items:
                if it["kind"] != "session":
                    continue
                s = it["session"]
                rows.append({
                    t("col_day"): d, t("col_date"): day_date(plan, d).isoformat(),
                    t("col_start"): format_time(it["start"]), t("col_end"): format_time(it["end"]),
                    t("col_subject"): s["subject"], t("col_hours"): s["duration"],
                    t("col_status"): t("st_done") if s["completed"] else t("st_pending"),
                })
        for s in by_day.get(None, []):
            rows.append({
                t("col_day"): "-", t("col_date"): "", t("col_start"): "", t("col_end"): "",
                t("col_subject"): s["subject"], t("col_hours"): s["duration"],
                t("col_status"): t("st_backlog"),
            })
        return pd.DataFrame(rows)

    def new_fig(figsize):
        p = chart_palette()
        fig, ax = plt.subplots(figsize=figsize)
        fig.patch.set_facecolor(p["bg"])
        ax.set_facecolor(p["bg"])
        for spine in ("top", "right", "left"):
            ax.spines[spine].set_visible(False)
        ax.spines["bottom"].set_color(p["grid"])
        ax.tick_params(colors=p["muted"], labelsize=9, length=0)
        return fig, ax, p

    # ------------------------------------------------------------------
    # Load everything from SQLite (source of truth) for this run
    # ------------------------------------------------------------------
    sid = st.session_state.student_id
    plan = None
    try:
        plan = db_get_active_plan(sid) if sid else None
    except sqlite3.Error as err:
        st.error(t("db_error", err=err))

    if not plan:
        st.warning(t("no_plan") if sid else tr("Please enter your subjects first."))
        if st.button(tr("Back to planning"), key="results_missing_back"):
            st.session_state.step = 2
            st.rerun()
        st.stop()

    sessions = db_get_sessions(plan["id"])
    stats = compute_stats(sessions, plan)
    xp = db_xp_summary(sid)
    lvl = level_for_xp(xp["total"])
    earned_badges = db_badges(sid)
    event = st.session_state.pop("last_event", None)   # shown once, right after a tick
    msg_kind, msg_text = motivation(stats, lvl, event)
    if event:
        st.toast(msg_text, icon="🎉")

    subjects_data = [dict(s) for s in plan["subjects"]]
    name = st.session_state.student_name
    daily_hours = day_capacity(plan["daily_hours"])
    exam_days = plan["exam_days"]
    stress_score = compute_stress()
    level, color = stress_level(stress_score)

    total_weight = sum(s["Weight"] for s in subjects_data)
    total_hours = daily_hours * exam_days
    scheduled = {k: v[1] for k, v in stats["by_subject"].items()}

    for s in subjects_data:
        s["Daily Hours"] = daily_hours * s["Weight"] / total_weight
        s["Total Planned Hours"] = total_hours * s["Weight"] / total_weight
        s["Scheduled Hours"] = scheduled.get(s["Subject"], 0.0)

    html_raw(f"""
    <div class="card-eyebrow">{esc(tr("Your plan"))}</div>
    <div class="app-title" style="margin-top:6px">{esc(tr("Study plan for"))} {esc(name)}</div>
    <p class="muted">{esc(tr(st.session_state.study_level))} · {esc(tr(st.session_state.study_style))}</p>
    """)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        html(f'<div class="metric"><div class="label">Daily study</div>'
             f'<div class="value">{fmt_h(daily_hours)}<span class="unit">hrs</span></div></div>')
    with m2:
        html(f'<div class="metric"><div class="label">Planning window</div>'
             f'<div class="value">{exam_days}<span class="unit">days</span></div></div>')
    with m3:
        html(f'<div class="metric"><div class="label">Total hours</div>'
             f'<div class="value">{fmt_h(total_hours)}<span class="unit">hrs</span></div></div>')
    with m4:
        html(f'<div class="metric"><div class="label">Stress estimate</div>'
             f'<div class="value" style="color:{color}">{stress_score}'
             f'<span class="unit">/ 10 · {level}</span></div></div>')

    st.caption(t("saved_note"))

    tab_dash, tab_sched, tab_stats, tab_over = st.tabs(
        [t("nav_dashboard"), t("nav_schedule"), t("nav_analytics"), t("nav_overview")])

    # ==============================================================
    # TAB 1 - DASHBOARD: buddy, XP, level, badges, key metrics
    # ==============================================================
    with tab_dash:
        left, right = st.columns([3, 2], gap="large")
        with left:
            bubble_cls = "bubble celebrate" if msg_kind == "celebrate" else "bubble"
            html_raw(f"""
            <div class="buddy">
            <div class="emoji">{lvl["emoji"]}</div>
            <div>
            <div class="who">{esc(t("buddy_title"))} · {esc(level_name(lvl["key"]))} · {xp["total"]} {esc(t("xp"))}</div>
            <div class="who" style="font-weight:500">{esc(t("buddy_" + lvl["key"]))}</div>
            <div class="{bubble_cls}">{esc(msg_text)}</div>
            </div>
            </div>
            """)
        with right:
            if lvl["next_key"]:
                nxt_text = t("xp_to_next", n=lvl["xp_to_next"], level=level_name(lvl["next_key"]))
            else:
                nxt_text = t("max_level")
            rungs = "".join(
                f'<span class="rung {"on" if i <= lvl["index"] else ""}">{LEVELS[i][2]} {esc(level_name(LEVELS[i][0]))} · {LEVELS[i][1]}</span>'
                for i in range(len(LEVELS)))
            html_raw(f"""
            <div class="xpcard">
            <div class="who">{esc(t("level"))}</div>
            <div class="lvl">{lvl["emoji"]} {esc(level_name(lvl["key"]))}</div>
            <div class="xpnum">{xp["total"]} {esc(t("xp"))}</div>
            {progress_bar(lvl["progress"], ACCENT, big=True)}
            <div class="xpnum">{esc(nxt_text)}</div>
            <div class="ladder">{rungs}</div>
            </div>
            """)

        html_raw('<div style="height:18px"></div>')
        a, b, c = st.columns(3)
        with a:
            html_raw(metric_card(t("completion"), f"{stats['pct']:.0f}", "%", GREEN if stats["pct"] >= 75 else None)
                     + progress_bar(stats["pct"] / 100, GREEN))
        with b:
            html_raw(metric_card(t("completed"), stats["done"], f"{t('of')} {stats['total']}"))
        with c:
            html_raw(metric_card(t("pending"), stats["pending"]))
        html_raw('<div style="height:12px"></div>')
        d1, d2, d3 = st.columns(3)
        with d1:
            html_raw(metric_card(t("hours_done"), fmt_h(stats["hours_done"]), t("h")))
        with d2:
            html_raw(metric_card(t("hours_left"), fmt_h(stats["hours_left"]), t("h")))
        with d3:
            late = stats["overdue"] + stats["backlog"]
            html_raw(metric_card(t("overdue"), late, color="#f87171" if late else None))

        html_raw(f'<div class="section-title">{esc(t("badges"))}</div>')
        chips = []
        for b in BADGE_KEYS:
            on = b in earned_badges
            tip = esc(t(f"badge_d_{b}"))
            chips.append(
                f'<div class="chip {"" if on else "off"}" title="{tip}">'
                f'<span>{BADGE_EMOJI[b] if on else "🔒"}</span>'
                f'<span><b>{esc(t("badge_" + b))}</b><br><span class="muted" style="font-size:12px">{tip}</span></span></div>')
        html_raw(f'<div class="chips">{"".join(chips)}</div>')

    # ==============================================================
    # TAB 2 - DAILY SCHEDULE: tick sessions, pick today, reschedule
    # ==============================================================
    with tab_sched:
        if "resched_msg" in st.session_state:
            r = st.session_state.pop("resched_msg")
            if r["total"] == 0:
                st.info(t("resched_none"))
            else:
                (st.success if r["backlog"] == 0 else st.warning)(
                    t("resched_result", moved=r["moved"], total=r["total"], backlog=r["backlog"]))

        cur_key = f"cur_day_{plan['id']}"
        st.selectbox(
            t("current_day"), list(range(1, exam_days + 1)),
            index=max(0, min(plan["current_day"], exam_days) - 1),
            format_func=lambda d: f"{t('day')} {d} · {fmt_date(day_date(plan, d))}",
            key=cur_key, on_change=cb_set_day, args=(plan["id"], sid, cur_key),
        )
        cur_day = plan["current_day"]

        unfinished = stats["overdue"] + stats["backlog"]
        if unfinished:
            st.warning(t("resched_pending", n=unfinished))
        if st.button(t("resched_btn"), key=f"resched_{plan['id']}", type="primary",
                     disabled=unfinished == 0):
            try:
                st.session_state.resched_msg = db_reschedule(plan["id"], sid, cur_day)
            except sqlite3.Error as err:
                st.error(t("db_error", err=err))
            else:
                st.rerun()
        st.caption(t("lock_note"))

        def session_checkbox(s, label):
            wkey = f"sess_{s['id']}"
            st.checkbox(
                label, value=bool(s["completed"]), disabled=bool(s["completed"]), key=wkey,
                on_change=cb_complete, args=(s["id"], plan["id"], sid, wkey),
            )

        by_day = {}
        for s in sessions:
            by_day.setdefault(s["day"], []).append(s)

        # ---- Backlog (visible, never silently dropped) ----
        backlog_rows = by_day.get(None, [])
        if backlog_rows:
            with st.expander(f"📥 {t('backlog')} ({len(backlog_rows)})", expanded=True):
                st.caption(t("backlog_note"))
                for s in backlog_rows:
                    origin = f" · {t('from_day', d=s['original_day'])}" if s["original_day"] else ""
                    session_checkbox(
                        s, f"{md_safe(s['subject'])} · {fmt_h(s['duration'])} {t('h')}{origin}")

        # ---- One expander per day ----
        late_days = []
        for d in range(1, exam_days + 1):
            rows = by_day.get(d, [])
            done_n = sum(1 for s in rows if s["completed"])
            if rows and done_n == len(rows):
                mark = "✅"
            elif d == cur_day:
                mark = "▶️"
            elif d < cur_day and rows:
                mark = "⚠️"
            else:
                mark = "▫️"
            label = (f"{mark} {t('day')} {d} · {fmt_date(day_date(plan, d))}"
                     f" · {done_n}/{len(rows)}")
            items, end_h = day_timetable(rows)
            if end_h > LATE_HOUR and rows:
                late_days.append(d)
            with st.expander(label, expanded=(d == cur_day)):
                if not rows:
                    st.caption(t("no_sessions_day"))
                for it in items:
                    span = f"{format_time(it['start'])} - {format_time(it['end'])}"
                    if it["kind"] == "session":
                        s = it["session"]
                        tag = f" · 🔁 {t('moved_tag')}" if s["rescheduled"] else ""
                        session_checkbox(
                            s, f"{span} · {md_safe(s['subject'])} · {fmt_h(s['duration'])} {t('h')}{tag}")
                    else:
                        brk = t("break_long") if it["kind"] == "long" else t("break_short")
                        html_raw(f'<div class="brk">☕ {esc(brk)} · {esc(span)}</div>')
        if late_days:
            st.warning(t("late_warn", d=late_days[0]))

    # ==============================================================
    # TAB 3 - ANALYTICS
    # ==============================================================
    with tab_stats:
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            html_raw(metric_card(t("completion"), f"{stats['pct']:.0f}", "%"))
        with k2:
            html_raw(metric_card(t("hours_done"), fmt_h(stats["hours_done"]), t("h")))
        with k3:
            html_raw(metric_card(t("hours_left"), fmt_h(stats["hours_left"]), t("h")))
        with k4:
            html_raw(metric_card(t("xp_total"), xp["total"], t("xp")))

        c_left, c_right = st.columns(2, gap="large")

        # --- Completed vs pending (donut) ---
        with c_left:
            html_raw(f'<div class="section-title">{esc(t("ch_sessions"))}</div>')
            fig, ax, p = new_fig((4.6, 3.6))
            if stats["total"]:
                ax.pie([stats["done"], stats["pending"]], colors=[GREEN, p["pending"]],
                       startangle=90, counterclock=False,
                       wedgeprops={"width": 0.38, "edgecolor": p["bg"]})
                ax.text(0, 0, f"{stats['pct']:.0f}%", ha="center", va="center",
                        fontsize=20, fontweight="bold", color=p["text"])
                ax.legend(
                    [f"{tc('lbl_done')}: {stats['done']}", f"{tc('lbl_pending')}: {stats['pending']}"],
                    loc="lower center", bbox_to_anchor=(0.5, -0.12), ncol=2, frameon=False,
                    labelcolor=p["text"], fontsize=9)
            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

        # --- Subject-wise progress ---
        with c_right:
            html_raw(f'<div class="section-title">{esc(t("ch_subject"))}</div>')
            subj = sorted(stats["by_subject"].items(), key=lambda kv: kv[1][1])
            fig, ax, p = new_fig((5.4, max(2.6, 0.5 * len(subj) + 1.2)))
            labels = [ctext(k) for k, _ in subj]
            done_h = [v[0] for _, v in subj]
            left_h = [v[1] - v[0] for _, v in subj]
            ax.barh(labels, done_h, color=GREEN, height=0.55, label=tc("lbl_done"))
            ax.barh(labels, left_h, left=done_h, color=p["pending"], height=0.55, label=tc("lbl_pending"))
            for i, (_, v) in enumerate(subj):
                ax.text(v[1] + max(0.1, 0.01 * max(x[1][1] for x in subj)), i,
                        f"{v[0]:g}/{v[1]:g}", va="center", color=p["text"], fontsize=9)
            ax.tick_params(axis="y", colors=p["text"], labelsize=9)
            ax.set_xlim(0, max(v[1] for _, v in subj) * 1.2)
            ax.legend(frameon=False, labelcolor=p["text"], fontsize=8, loc="lower right")
            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

        # --- Daily progress ---
        html_raw(f'<div class="section-title">{esc(t("ch_daily"))}</div>')
        days = list(range(1, exam_days + 1))
        d_done = [stats["by_day"][d][0] for d in days]
        d_left = [stats["by_day"][d][1] - stats["by_day"][d][0] for d in days]
        fig, ax, p = new_fig((10, 3.2))
        ax.bar(days, d_done, color=GREEN, width=0.7, label=tc("lbl_done"))
        ax.bar(days, d_left, bottom=d_done, color=p["pending"], width=0.7, label=tc("lbl_pending"))
        ax.axvline(plan["current_day"], color=ACCENT, linewidth=1.5, linestyle="--", label=tc("lbl_today"))
        step_x = max(1, math.ceil(exam_days / 20))
        ax.set_xticks(days[::step_x])
        ax.set_xlabel(tc("lbl_day"), color=p["muted"], fontsize=9)
        ax.grid(axis="y", color=p["grid"], linewidth=0.8)
        ax.set_axisbelow(True)
        ax.legend(frameon=False, labelcolor=p["text"], fontsize=8, ncol=3, loc="upper right")
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

        # --- XP and levels ---
        html_raw(f'<div class="section-title">{esc(t("xp_levels"))}</div>')
        x1, x2, x3 = st.columns(3)
        with x1:
            html_raw(metric_card(t("xp_sessions"), xp["sessions"], t("xp")))
        with x2:
            html_raw(metric_card(t("xp_days"), xp["days"], t("xp")))
        with x3:
            html_raw(metric_card(t("level"), f'{lvl["emoji"]} {level_name(lvl["key"])}'))
        html_raw(progress_bar(lvl["progress"], ACCENT, big=True))

    # ==============================================================
    # TAB 4 - PLAN OVERVIEW (all original result sections preserved)
    # ==============================================================
    with tab_over:
        # ---- Allocation table ----
        html('<div class="section-title">Study hours allocation</div>')

        df = pd.DataFrame(subjects_data)
        display_df = df[["Subject", "Difficulty", "Priority", "Daily Hours",
                         "Total Planned Hours", "Scheduled Hours"]].copy()
        display_df["Daily Hours"] = display_df["Daily Hours"].round(2)
        display_df["Total Planned Hours"] = display_df["Total Planned Hours"].round(2)
        display_df["Scheduled Hours"] = display_df["Scheduled Hours"].round(2)

        if st.session_state.language == "Arabic":
            display_df["Difficulty"] = display_df["Difficulty"].map({
                "Easy": "سهلة", "Medium": "متوسطة", "Hard": "صعبة"
            })
            display_df["Priority"] = display_df["Priority"].map({
                "Normal": "عادية", "Important": "مهمة", "Very important": "مهمة جدًا"
            })
            display_df = display_df.rename(columns={
                "Subject": "المادة", "Difficulty": "الصعوبة", "Priority": "الأولوية",
                "Daily Hours": "ساعات يوميًا", "Total Planned Hours": "إجمالي الساعات",
                "Scheduled Hours": t("scheduled_hours"),
            })
        st.dataframe(display_df, hide_index=True)

        # ---- Chart ----
        html('<div class="section-title">Daily study distribution</div>')

        chart_df = df[["Subject", "Daily Hours"]].copy().sort_values("Daily Hours", ascending=True)
        chart_df["Subject"] = chart_df["Subject"].map(ctext)

        fig, ax = plt.subplots(figsize=(10, max(2.4, 0.55 * len(chart_df) + 1)))
        fig.patch.set_facecolor("#f4f6fb" if st.session_state.theme_mode == "Light" else "#0b0f19")
        ax.set_facecolor("#f4f6fb" if st.session_state.theme_mode == "Light" else "#0b0f19")

        bars = ax.barh(chart_df["Subject"], chart_df["Daily Hours"], color=ACCENT, height=0.55)

        # Arabic axis text only when the optional shaping libraries are installed
        hours_label = ("Hours per day" if (st.session_state.language == "Arabic" and not HAS_SHAPING)
                       else ctext(tr("Hours per day")))
        ax.set_xlabel(hours_label, color=("#475569" if st.session_state.theme_mode == "Light" else "#94a3b8"), fontsize=10)
        ax.tick_params(axis="x", colors=("#475569" if st.session_state.theme_mode == "Light" else "#94a3b8"), labelsize=9)
        ax.tick_params(axis="y", colors=("#172033" if st.session_state.theme_mode == "Light" else "#e5e7eb"), labelsize=10, length=0)
        for spine in ("top", "right", "left"):
            ax.spines[spine].set_visible(False)
        ax.spines["bottom"].set_color("#d8deea" if st.session_state.theme_mode == "Light" else "#1f2937")
        ax.grid(axis="x", color="#d8deea" if st.session_state.theme_mode == "Light" else "#1f2937", linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_xlim(0, chart_df["Daily Hours"].max() * 1.18)

        for bar in bars:
            ax.text(
                bar.get_width() + chart_df["Daily Hours"].max() * 0.015,
                bar.get_y() + bar.get_height() / 2,
                f"{bar.get_width():.1f} h",
                va="center",
                color=("#172033" if st.session_state.theme_mode == "Light" else "#e5e7eb"),
                fontsize=10,
            )

        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

        # ---- Timetable (typical day, original logic) ----
        html('<div class="section-title">Suggested daily timetable</div>')
        st.caption(t("daily_template_note"))

        ordered = sorted(subjects_data, key=lambda x: x["Weight"], reverse=True)

        timetable = []
        current_time = 9.0

        for i, s in enumerate(ordered):
            duration = s["Daily Hours"]
            end_time = current_time + duration

            timetable.append({
                "Time": f"{format_time(current_time)} - {format_time(end_time)}",
                "Activity": f"{tr('Study: ')}{s['Subject']}",
                "Duration": f"{duration:.1f} {tr('hours')}",
            })
            current_time = end_time

            if i < len(ordered) - 1:
                timetable.append({
                    "Time": f"{format_time(current_time)} - {format_time(current_time + 0.25)}",
                    "Activity": tr("Short break"),
                    "Duration": f"15 {tr('minutes')}",
                })
                current_time += 0.25

                if (i + 1) % 2 == 0 and i < len(ordered) - 2:
                    timetable.append({
                        "Time": f"{format_time(current_time)} - {format_time(current_time + 0.5)}",
                        "Activity": tr("Long break / meal"),
                        "Duration": f"30 {tr('minutes')}",
                    })
                    current_time += 0.5

        timetable_df = pd.DataFrame(timetable)
        if st.session_state.language == "Arabic":
            # الأول نترجم محتوى عمود Activity وهو لسه اسمه "Activity"
            timetable_df["Activity"] = timetable_df["Activity"].map(
                lambda x: x.replace("Study: ", "مذاكرة: ").replace("Short break", "استراحة قصيرة").replace("Long break / meal", "استراحة طويلة / وجبة")
            )
            # وبعد كده نغير أسماء الأعمدة
            timetable_df = timetable_df.rename(columns={
                "Time": "الوقت", "Activity": "النشاط", "Duration": "المدة"
            })
        st.dataframe(timetable_df, hide_index=True)

        if current_time > 22:
            st.warning(
                tr("This timetable runs late into the evening. Consider reducing your daily hours or starting earlier to protect your sleep.")
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

        st.caption(tr("This tool offers study-planning suggestions, not medical advice or a clinical stress diagnosis."))

        # ---- Downloads ----
        html('<div class="section-title">Export</div>')

        d1, d2, d3 = st.columns(3)
        with d1:
            st.download_button(
                tr("Download study plan"),
                data=display_df.to_csv(index=False).encode("utf-8-sig"),
                file_name="study_plan.csv",
                mime="text/csv",
            )
        with d2:
            st.download_button(
                tr("Download timetable"),
                data=timetable_df.to_csv(index=False).encode("utf-8-sig"),
                file_name="daily_timetable.csv",
                mime="text/csv",
            )
        with d3:
            st.download_button(
                t("dl_schedule"),
                data=schedule_dataframe(sessions, plan).to_csv(index=False).encode("utf-8-sig"),
                file_name="full_schedule.csv",
                mime="text/csv",
            )

    st.markdown("---")

    back_col, restart_col = st.columns(2)
    with back_col:
        if st.button(tr("Back to planning"), key="results_back"):
            go_back()
            st.rerun()
    with restart_col:
        if st.button(tr("Start over"), key="restart", type="primary"):
            # Clears the screen/session only. Saved data in SQLite is NOT deleted.
            st.session_state.clear()
            st.rerun()
    st.caption(t("start_over_help"))

# ==================================================
# FOOTER
# ==================================================
st.markdown("---")
html('<div class="footer">ACADEMIC &amp; STRESS MANAGEMENT EXPERT SYSTEM</div>')
