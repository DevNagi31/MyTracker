import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "tracker.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            category TEXT DEFAULT 'General',
            priority TEXT DEFAULT 'medium',
            due_date TEXT,
            due_time TEXT,
            reminder_enabled INTEGER DEFAULT 1,
            reminder_email TEXT DEFAULT '',
            completed INTEGER DEFAULT 0,
            progress INTEGER DEFAULT 0,
            progress_target INTEGER DEFAULT 100,
            recurring TEXT DEFAULT 'none',
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS subtasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS daily_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,
            content TEXT DEFAULT '',
            mood INTEGER DEFAULT 3,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS completion_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id INTEGER,
            date TEXT NOT NULL,
            completed_at TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    conn.commit()
    conn.close()


# ── Goals ──

def add_goal(title, description, category, priority, due_date, due_time,
             reminder_enabled, reminder_email, progress_target, recurring):
    conn = get_db()
    max_order = conn.execute("SELECT COALESCE(MAX(sort_order),0) FROM goals").fetchone()[0]
    conn.execute(
        """INSERT INTO goals (title, description, category, priority, due_date, due_time,
           reminder_enabled, reminder_email, progress_target, recurring, sort_order)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, description, category, priority, due_date, due_time,
         int(reminder_enabled), reminder_email, progress_target, recurring, max_order + 1),
    )
    conn.commit()
    goal_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return goal_id


def update_goal(goal_id, **kwargs):
    conn = get_db()
    fields = []
    values = []
    for key, val in kwargs.items():
        if key == "reminder_enabled":
            val = int(val)
        fields.append(f"{key}=?")
        values.append(val)
    values.append(goal_id)
    conn.execute(f"UPDATE goals SET {','.join(fields)} WHERE id=?", values)
    conn.commit()
    conn.close()


def toggle_complete(goal_id):
    conn = get_db()
    goal = conn.execute("SELECT completed FROM goals WHERE id=?", (goal_id,)).fetchone()
    if goal:
        new_status = 0 if goal["completed"] else 1
        completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if new_status else None
        conn.execute("UPDATE goals SET completed=?, completed_at=?, progress=? WHERE id=?",
                      (new_status, completed_at, 100 if new_status else 0, goal_id))
        if new_status:
            today = datetime.now().strftime("%Y-%m-%d")
            conn.execute("INSERT INTO completion_log (goal_id, date) VALUES (?, ?)", (goal_id, today))
        conn.commit()
    conn.close()


def update_progress(goal_id, progress):
    conn = get_db()
    goal = conn.execute("SELECT progress_target FROM goals WHERE id=?", (goal_id,)).fetchone()
    if goal:
        completed = 1 if progress >= goal["progress_target"] else 0
        completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if completed else None
        conn.execute("UPDATE goals SET progress=?, completed=?, completed_at=? WHERE id=?",
                      (progress, completed, completed_at, goal_id))
        if completed:
            today = datetime.now().strftime("%Y-%m-%d")
            conn.execute("INSERT INTO completion_log (goal_id, date) VALUES (?, ?)", (goal_id, today))
        conn.commit()
    conn.close()


def reorder_goals(goal_ids):
    conn = get_db()
    for i, gid in enumerate(goal_ids):
        conn.execute("UPDATE goals SET sort_order=? WHERE id=?", (i, gid))
    conn.commit()
    conn.close()


def delete_goal(goal_id):
    conn = get_db()
    conn.execute("DELETE FROM goals WHERE id=?", (goal_id,))
    conn.commit()
    conn.close()


def get_all_goals():
    conn = get_db()
    goals = conn.execute("SELECT * FROM goals ORDER BY sort_order ASC, due_date ASC, due_time ASC").fetchall()
    result = []
    for g in goals:
        gd = dict(g)
        subs = conn.execute("SELECT * FROM subtasks WHERE goal_id=? ORDER BY sort_order", (g["id"],)).fetchall()
        gd["subtasks"] = [dict(s) for s in subs]
        result.append(gd)
    conn.close()
    return result


def get_goals_by_date(date_str):
    conn = get_db()
    goals = conn.execute(
        "SELECT * FROM goals WHERE due_date=? ORDER BY sort_order ASC, due_time ASC", (date_str,)
    ).fetchall()
    result = []
    for g in goals:
        gd = dict(g)
        subs = conn.execute("SELECT * FROM subtasks WHERE goal_id=? ORDER BY sort_order", (g["id"],)).fetchall()
        gd["subtasks"] = [dict(s) for s in subs]
        result.append(gd)
    conn.close()
    return result


def get_goal(goal_id):
    conn = get_db()
    goal = conn.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
    if goal:
        gd = dict(goal)
        subs = conn.execute("SELECT * FROM subtasks WHERE goal_id=? ORDER BY sort_order", (goal_id,)).fetchall()
        gd["subtasks"] = [dict(s) for s in subs]
        conn.close()
        return gd
    conn.close()
    return None


def search_goals(query):
    conn = get_db()
    goals = conn.execute(
        "SELECT * FROM goals WHERE title LIKE ? OR description LIKE ? ORDER BY sort_order",
        (f"%{query}%", f"%{query}%")
    ).fetchall()
    conn.close()
    return [dict(g) for g in goals]


def get_overdue_goals():
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")
    conn = get_db()
    goals = conn.execute(
        """SELECT * FROM goals WHERE completed=0 AND
           ((due_date < ?) OR (due_date = ? AND due_time < ? AND due_time != ''))
           ORDER BY due_date ASC""",
        (today, today, current_time)
    ).fetchall()
    conn.close()
    return [dict(g) for g in goals]


def get_pending_reminders():
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")
    conn = get_db()
    goals = conn.execute(
        """SELECT * FROM goals WHERE due_date=? AND due_time=? AND completed=0 AND reminder_enabled=1""",
        (current_date, current_time),
    ).fetchall()
    conn.close()
    return [dict(g) for g in goals]


# ── Subtasks ──

def add_subtask(goal_id, title):
    conn = get_db()
    max_order = conn.execute("SELECT COALESCE(MAX(sort_order),0) FROM subtasks WHERE goal_id=?", (goal_id,)).fetchone()[0]
    conn.execute("INSERT INTO subtasks (goal_id, title, sort_order) VALUES (?, ?, ?)",
                 (goal_id, title, max_order + 1))
    conn.commit()
    sub_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return sub_id


def toggle_subtask(subtask_id):
    conn = get_db()
    sub = conn.execute("SELECT completed FROM subtasks WHERE id=?", (subtask_id,)).fetchone()
    if sub:
        conn.execute("UPDATE subtasks SET completed=? WHERE id=?", (0 if sub["completed"] else 1, subtask_id))
        conn.commit()
    conn.close()


def delete_subtask(subtask_id):
    conn = get_db()
    conn.execute("DELETE FROM subtasks WHERE id=?", (subtask_id,))
    conn.commit()
    conn.close()


# ── Daily Notes ──

def save_note(date, content, mood):
    conn = get_db()
    conn.execute(
        """INSERT INTO daily_notes (date, content, mood) VALUES (?, ?, ?)
           ON CONFLICT(date) DO UPDATE SET content=excluded.content, mood=excluded.mood""",
        (date, content, mood)
    )
    conn.commit()
    conn.close()


def get_note(date):
    conn = get_db()
    note = conn.execute("SELECT * FROM daily_notes WHERE date=?", (date,)).fetchone()
    conn.close()
    return dict(note) if note else None


def get_all_notes():
    conn = get_db()
    notes = conn.execute("SELECT * FROM daily_notes ORDER BY date DESC").fetchall()
    conn.close()
    return [dict(n) for n in notes]


# ── Stats ──

def get_completion_stats():
    conn = get_db()
    today = datetime.now()

    # Daily completions for last 90 days
    ninety_ago = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    daily = conn.execute(
        "SELECT date, COUNT(*) as count FROM completion_log WHERE date >= ? GROUP BY date ORDER BY date",
        (ninety_ago,)
    ).fetchall()

    # Total stats
    total = conn.execute("SELECT COUNT(*) as c FROM goals").fetchone()["c"]
    done = conn.execute("SELECT COUNT(*) as c FROM goals WHERE completed=1").fetchone()["c"]

    # Category breakdown
    cats = conn.execute(
        "SELECT category, COUNT(*) as total, SUM(completed) as done FROM goals GROUP BY category"
    ).fetchall()

    # Streak calculation
    streak = 0
    d = today
    while True:
        ds = d.strftime("%Y-%m-%d")
        day_goals = conn.execute("SELECT COUNT(*) as c FROM goals WHERE due_date=?", (ds,)).fetchone()["c"]
        day_done = conn.execute(
            "SELECT COUNT(*) as c FROM completion_log WHERE date=?", (ds,)
        ).fetchone()["c"]
        if day_goals > 0 and day_done > 0:
            streak += 1
            d -= timedelta(days=1)
        else:
            break

    # Heatmap data (last 365 days)
    year_ago = (today - timedelta(days=365)).strftime("%Y-%m-%d")
    heatmap = conn.execute(
        "SELECT date, COUNT(*) as count FROM completion_log WHERE date >= ? GROUP BY date",
        (year_ago,)
    ).fetchall()

    # Weekly completion rates for atomic habits graph
    weeks = []
    for w in range(12, -1, -1):
        week_start = today - timedelta(days=today.weekday() + 7 * w)
        week_end = week_start + timedelta(days=6)
        ws = week_start.strftime("%Y-%m-%d")
        we = week_end.strftime("%Y-%m-%d")
        wl = week_start.strftime("%b %d")
        total_w = conn.execute(
            "SELECT COUNT(*) as c FROM goals WHERE due_date BETWEEN ? AND ?", (ws, we)
        ).fetchone()["c"]
        done_w = conn.execute(
            "SELECT COUNT(*) as c FROM completion_log WHERE date BETWEEN ? AND ?", (ws, we)
        ).fetchone()["c"]
        rate = round((done_w / total_w * 100) if total_w > 0 else 0)
        weeks.append({"label": wl, "rate": rate, "done": done_w, "total": total_w})

    conn.close()
    return {
        "total": total,
        "done": done,
        "streak": streak,
        "daily": [dict(d) for d in daily],
        "categories": [dict(c) for c in cats],
        "heatmap": [dict(h) for h in heatmap],
        "weeks": weeks,
    }


# ── AI Agent ──

def get_agent_insights():
    conn = get_db()
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    current_time = today.strftime("%H:%M")

    insights = []

    # Overdue goals
    overdue = conn.execute(
        "SELECT COUNT(*) as c FROM goals WHERE completed=0 AND due_date < ?", (today_str,)
    ).fetchone()["c"]
    if overdue > 0:
        insights.append({
            "type": "warning",
            "icon": "alert-triangle",
            "message": f"You have {overdue} overdue goal{'s' if overdue > 1 else ''}. Let's tackle them today."
        })

    # Today's progress
    today_total = conn.execute("SELECT COUNT(*) as c FROM goals WHERE due_date=?", (today_str,)).fetchone()["c"]
    today_done = conn.execute(
        "SELECT COUNT(*) as c FROM goals WHERE due_date=? AND completed=1", (today_str,)
    ).fetchone()["c"]
    if today_total > 0:
        pct = round(today_done / today_total * 100)
        if pct == 100:
            insights.append({
                "type": "success",
                "icon": "trophy",
                "message": "You crushed all of today's goals! Your consistency is building something powerful."
            })
        elif pct >= 50:
            insights.append({
                "type": "info",
                "icon": "trending-up",
                "message": f"You're {pct}% through today's goals. Keep the momentum going — you're past the halfway mark."
            })
        else:
            remaining = today_total - today_done
            insights.append({
                "type": "info",
                "icon": "target",
                "message": f"You have {remaining} goal{'s' if remaining > 1 else ''} left today. Small steps compound into big results."
            })

    # Streak motivation
    # Calculate streak
    streak = 0
    d = today
    while True:
        ds = d.strftime("%Y-%m-%d")
        dg = conn.execute("SELECT COUNT(*) as c FROM goals WHERE due_date=?", (ds,)).fetchone()["c"]
        dd = conn.execute("SELECT COUNT(*) as c FROM completion_log WHERE date=?", (ds,)).fetchone()["c"]
        if dg > 0 and dd > 0:
            streak += 1
            d -= timedelta(days=1)
        else:
            break

    if streak >= 7:
        insights.append({
            "type": "success",
            "icon": "flame",
            "message": f"Incredible {streak}-day streak! You're proving that consistency beats intensity."
        })
    elif streak >= 3:
        insights.append({
            "type": "info",
            "icon": "zap",
            "message": f"{streak}-day streak going! Remember: every action is a vote for the person you want to become."
        })
    elif streak == 0:
        insights.append({
            "type": "info",
            "icon": "rotate-ccw",
            "message": "Today is a fresh start. The best time to begin was yesterday. The second best time is now."
        })

    # Upcoming goals reminder
    tomorrow = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    upcoming = conn.execute(
        "SELECT title, due_time FROM goals WHERE due_date=? AND completed=0 ORDER BY due_time LIMIT 3",
        (tomorrow,)
    ).fetchall()
    if upcoming:
        names = ", ".join([u["title"] for u in upcoming])
        insights.append({
            "type": "info",
            "icon": "calendar-clock",
            "message": f"Tomorrow's lineup: {names}. Prepare tonight to win tomorrow."
        })

    # Category balance
    cats = conn.execute(
        "SELECT category, COUNT(*) as c FROM goals WHERE completed=0 GROUP BY category ORDER BY c DESC"
    ).fetchall()
    if len(cats) >= 2:
        top = cats[0]
        if top["c"] > 5:
            insights.append({
                "type": "info",
                "icon": "scale",
                "message": f"You have {top['c']} goals in {top['category']}. Consider balancing across other areas of your life."
            })

    # Atomic habits quote
    quotes = [
        "You do not rise to the level of your goals. You fall to the level of your systems.",
        "Every action you take is a vote for the type of person you wish to become.",
        "The task of breaking a bad habit is like uprooting a powerful oak within us.",
        "Success is the product of daily habits, not once-in-a-lifetime transformations.",
        "Be the designer of your world and not merely the consumer of it.",
        "Habits are the compound interest of self-improvement.",
        "Small habits don't add up. They compound.",
        "Getting 1% better every day counts for a lot in the long-run.",
        "You should be far more concerned with your current trajectory than with your current results.",
        "Time magnifies the margin between success and failure."
    ]
    import random
    insights.append({
        "type": "quote",
        "icon": "book-open",
        "message": f"\"{random.choice(quotes)}\" — Atomic Habits"
    })

    conn.close()
    return insights
