from flask import Flask, render_template, request, jsonify, Response, session, redirect, url_for
from functools import wraps
from models import (
    init_db, create_user, authenticate_user, get_user,
    add_goal, update_goal, toggle_complete, update_progress,
    reorder_goals, delete_goal, get_all_goals, get_goals_by_date,
    get_goal, search_goals, get_overdue_goals, get_pending_reminders,
    add_subtask, toggle_subtask, delete_subtask,
    save_note, get_note, get_all_notes,
    get_completion_stats, get_agent_insights,
)
from calendar_sync import add_to_calendar, remove_from_calendar
from notifications import send_mac_notification
from scheduler import start_scheduler, stop_scheduler
from datetime import datetime
import csv
import io
import os
import atexit

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(32).hex())

init_db()
start_scheduler()
atexit.register(stop_scheduler)


# ── Auth helpers ──

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


# ── Auth pages ──

@app.route("/login")
def login_page():
    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/signup")
def signup_page():
    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("signup.html")


@app.route("/api/auth/signup", methods=["POST"])
def api_signup():
    d = request.json
    username = d.get("username", "").strip()
    password = d.get("password", "")
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    user_id = create_user(username, password)
    if user_id is None:
        return jsonify({"error": "Username already taken"}), 409
    session["user_id"] = user_id
    session["username"] = username
    return jsonify({"id": user_id, "username": username}), 201


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    d = request.json
    username = d.get("username", "").strip()
    password = d.get("password", "")
    user = authenticate_user(username, password)
    if not user:
        return jsonify({"error": "Invalid username or password"}), 401
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return jsonify({"id": user["id"], "username": user["username"]})


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"status": "logged out"})


@app.route("/api/auth/me", methods=["GET"])
def api_me():
    if "user_id" not in session:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"id": session["user_id"], "username": session.get("username", "")})


# ── Main app ──

@app.route("/")
@login_required
def index():
    today = datetime.now().strftime("%Y-%m-%d")
    return render_template("index.html", today=today, username=session.get("username", ""))


# ── Goals API ──

@app.route("/api/goals", methods=["GET"])
@login_required
def api_get_goals():
    uid = session["user_id"]
    date = request.args.get("date")
    q = request.args.get("q")
    if q:
        return jsonify(search_goals(uid, q))
    if date:
        return jsonify(get_goals_by_date(uid, date))
    return jsonify(get_all_goals(uid))


@app.route("/api/goals", methods=["POST"])
@login_required
def api_add_goal():
    uid = session["user_id"]
    d = request.json
    goal_id = add_goal(
        user_id=uid,
        title=d["title"],
        description=d.get("description", ""),
        category=d.get("category", "General"),
        priority=d.get("priority", "medium"),
        due_date=d.get("due_date", ""),
        due_time=d.get("due_time", ""),
        reminder_enabled=d.get("reminder_enabled", True),
        reminder_email=d.get("reminder_email", ""),
        progress_target=d.get("progress_target", 100),
        recurring=d.get("recurring", "none"),
    )
    if d.get("due_date"):
        add_to_calendar(d["title"], d.get("description", ""), d["due_date"], d.get("due_time", "09:00"))
    for sub in d.get("subtasks", []):
        add_subtask(goal_id, sub)
    return jsonify({"id": goal_id}), 201


@app.route("/api/goals/<int:gid>", methods=["PUT"])
@login_required
def api_update_goal(gid):
    uid = session["user_id"]
    d = request.json
    old = get_goal(uid, gid)
    update_goal(uid, gid,
        title=d["title"], description=d.get("description", ""),
        category=d.get("category", "General"), priority=d.get("priority", "medium"),
        due_date=d.get("due_date", ""), due_time=d.get("due_time", ""),
        reminder_enabled=d.get("reminder_enabled", True),
        reminder_email=d.get("reminder_email", ""),
        progress_target=d.get("progress_target", 100),
        recurring=d.get("recurring", "none"),
    )
    if old:
        remove_from_calendar(old["title"])
    if d.get("due_date"):
        add_to_calendar(d["title"], d.get("description", ""), d["due_date"], d.get("due_time", "09:00"))
    return jsonify({"status": "updated"})


@app.route("/api/goals/<int:gid>/toggle", methods=["POST"])
@login_required
def api_toggle_goal(gid):
    uid = session["user_id"]
    toggle_complete(uid, gid)
    goal = get_goal(uid, gid)
    return jsonify({"completed": goal["completed"] if goal else 0})


@app.route("/api/goals/<int:gid>/progress", methods=["POST"])
@login_required
def api_update_progress(gid):
    uid = session["user_id"]
    progress = request.json.get("progress", 0)
    update_progress(uid, gid, progress)
    return jsonify({"status": "updated"})


@app.route("/api/goals/<int:gid>", methods=["DELETE"])
@login_required
def api_delete_goal(gid):
    uid = session["user_id"]
    goal = get_goal(uid, gid)
    if goal:
        remove_from_calendar(goal["title"])
    delete_goal(uid, gid)
    return jsonify({"status": "deleted"})


@app.route("/api/goals/reorder", methods=["POST"])
@login_required
def api_reorder():
    uid = session["user_id"]
    ids = request.json.get("ids", [])
    reorder_goals(uid, ids)
    return jsonify({"status": "reordered"})


@app.route("/api/goals/overdue", methods=["GET"])
@login_required
def api_overdue():
    return jsonify(get_overdue_goals(session["user_id"]))


# ── Subtasks ──

@app.route("/api/subtasks", methods=["POST"])
@login_required
def api_add_subtask():
    d = request.json
    sid = add_subtask(d["goal_id"], d["title"])
    return jsonify({"id": sid}), 201


@app.route("/api/subtasks/<int:sid>/toggle", methods=["POST"])
@login_required
def api_toggle_subtask(sid):
    toggle_subtask(session["user_id"], sid)
    return jsonify({"status": "toggled"})


@app.route("/api/subtasks/<int:sid>", methods=["DELETE"])
@login_required
def api_del_subtask(sid):
    delete_subtask(session["user_id"], sid)
    return jsonify({"status": "deleted"})


# ── Notes ──

@app.route("/api/notes", methods=["GET"])
@login_required
def api_get_notes():
    uid = session["user_id"]
    date = request.args.get("date")
    if date:
        note = get_note(uid, date)
        return jsonify(note or {"date": date, "content": "", "mood": 3})
    return jsonify(get_all_notes(uid))


@app.route("/api/notes", methods=["POST"])
@login_required
def api_save_note():
    uid = session["user_id"]
    d = request.json
    save_note(uid, d["date"], d["content"], d.get("mood", 3))
    return jsonify({"status": "saved"})


# ── Stats ──

@app.route("/api/stats", methods=["GET"])
@login_required
def api_stats():
    return jsonify(get_completion_stats(session["user_id"]))


# ── AI Agent ──

@app.route("/api/agent", methods=["GET"])
@login_required
def api_agent():
    return jsonify(get_agent_insights(session["user_id"]))


# ── Export ──

@app.route("/api/export/csv", methods=["GET"])
@login_required
def api_export_csv():
    goals = get_all_goals(session["user_id"])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Title", "Description", "Category", "Priority", "Due Date", "Due Time",
                      "Progress", "Completed", "Created At"])
    for g in goals:
        writer.writerow([g["title"], g["description"], g["category"], g["priority"],
                          g["due_date"], g["due_time"], f"{g['progress']}/{g['progress_target']}",
                          "Yes" if g["completed"] else "No", g["created_at"]])
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=mytracker_export.csv"})


# ── Notifications ──

@app.route("/api/test-notification", methods=["POST"])
@login_required
def api_test_notification():
    success = send_mac_notification("MyTracker", "Notifications are working!")
    return jsonify({"success": success})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
