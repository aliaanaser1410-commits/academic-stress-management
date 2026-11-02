
"""
Expert System for Smart Student Assistant.

Uses IF-THEN rules to assess student conditions,
generate recommendations, and explain each decision.
"""

RULES = [
    {
        "id": "R01",
        "condition": lambda p: float(p.get("stress", 0)) >= 8,
        "level": "High",
        "title": "High stress detected",
        "message": "Your stress level is high. Reduce today's study load and add short breaks.",
        "action": "Reduce daily study hours and schedule relaxation breaks."
    },
    {
        "id": "R02",
        "condition": lambda p: float(p.get("stress", 0)) >= 5
        and float(p.get("stress", 0)) < 8,
        "level": "Medium",
        "title": "Moderate stress detected",
        "message": "You have some stress. Use shorter focused sessions and regular breaks.",
        "action": "Use 30–60 minute sessions with regular breaks."
    },
    {
        "id": "R03",
        "condition": lambda p: float(p.get("sleep", 8)) < 5,
        "level": "High",
        "title": "Insufficient sleep",
        "message": "Your sleep duration is low. Prioritize rest before increasing study time.",
        "action": "Protect your sleep schedule and avoid late-night study."
    },
    {
        "id": "R04",
        "condition": lambda p: float(p.get("sleep", 8)) >= 5
        and float(p.get("sleep", 8)) < 7,
        "level": "Medium",
        "title": "Sleep needs improvement",
        "message": "Your sleep may need improvement to support concentration.",
        "action": "Try to maintain a consistent sleep routine."
    },
    {
        "id": "R05",
        "condition": lambda p: float(p.get("focus", 5)) <= 3,
        "level": "High",
        "title": "Low concentration",
        "message": "Your concentration is low. Start with small tasks and remove distractions.",
        "action": "Begin with 30-minute focused study sessions."
    },
    {
        "id": "R06",
        "condition": lambda p: float(p.get("workload", 5)) >= 8,
        "level": "High",
        "title": "Heavy academic workload",
        "message": "Your workload is high. Prioritize urgent and difficult subjects.",
        "action": "Divide large tasks into smaller achievable steps."
    },
    {
        "id": "R07",
        "condition": lambda p: int(p.get("days_left", 30)) <= 3,
        "level": "High",
        "title": "Exam is approaching",
        "message": "Your nearest exam is very close. Focus on revision and important topics.",
        "action": "Prioritize exam preparation and active recall."
    },
    {
        "id": "R08",
        "condition": lambda p: float(p.get("study_hours", 4)) > 8,
        "level": "Medium",
        "title": "Long daily study target",
        "message": "Your daily study target is high. Make sure it is realistic and includes breaks.",
        "action": "Consider shorter sessions and a balanced workload."
    },
    {
        "id": "R09",
        "condition": lambda p: float(p.get("focus", 5)) >= 7
        and float(p.get("stress", 0)) < 5,
        "level": "Positive",
        "title": "Good study readiness",
        "message": "Your focus is good and stress is relatively low. Maintain your routine.",
        "action": "Keep your current productive study habits."
    }
]


def evaluate_student(profile):
    """
    Forward-chaining style evaluation:
    checks every rule against the student's profile
    and returns all activated rules.
    """
    activated_rules = []

    for rule in RULES:
        try:
            if rule["condition"](profile):
                activated_rules.append({
                    "id": rule["id"],
                    "level": rule["level"],
                    "title": rule["title"],
                    "message": rule["message"],
                    "action": rule["action"]
                })
        except (TypeError, ValueError, AttributeError):
            continue

    return activated_rules


def generate_recommendations(profile):
    """Return recommendations and an explanation for each activated rule."""
    results = evaluate_student(profile)

    recommendations = [
        {
            "rule_id": item["id"],
            "title": item["title"],
            "recommendation": item["action"],
            "explanation": item["message"],
            "level": item["level"]
        }
        for item in results
    ]

    if not recommendations:
        recommendations.append({
            "rule_id": "R00",
            "title": "Balanced starting point",
            "recommendation": "Follow a balanced study plan and review your progress regularly.",
            "explanation": "No high-priority risk rules were activated by the available answers.",
            "level": "Positive"
        })

    return recommendations


def get_study_adjustments(profile):
    """
    Calculate suggested planner adjustments.
    These are suggestions, not medical assessments.
    """
    rules = evaluate_student(profile)

    high_risk = any(rule["level"] == "High" for rule in rules)

    try:
        hours = float(profile.get("study_hours", 4))
    except (TypeError, ValueError):
        hours = 4.0

    if high_risk:
        hours = min(hours, 4.0)

    return {
        "recommended_daily_hours": max(1.0, hours),
        "short_sessions": high_risk,
        "extra_breaks": high_risk or any(
            rule["id"] in ("R01", "R02", "R03", "R04")
            for rule in rules
        ),
        "activated_rule_ids": [rule["id"] for rule in rules]
    }
