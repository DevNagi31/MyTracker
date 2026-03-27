from flask import Flask, render_template, request, jsonify, Response
from models import (
    init_db, add_goal, update_goal, toggle_complete, update_progress,
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
import atexit

app = Flask(__name__)
init_db()
start_scheduler()
atexit.register(stop_scheduler)


@app.route("/")
def index():
    today = datetime.now().strftime("%Y-%m-%d")
    return render_template("index.html", today=today)


# ── Goals API ──

@app.route("/api/goals", methods=["GET"])
def api_get_goals():
    date = request.args.get("date")
    q = request.args.get("q")
    if q:
        return jsonify(search_goals(q))
    if date:
        return jsonify(get_goals_by_date(date))
    return jsonify(get_all_goals())


@app.route("/api/goals", methods=["POST"])
def api_add_goal():
    d = request.json
    goal_id = add_goal(
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
    # Add subtasks if provided
    for sub in d.get("subtasks", []):
        add_subtask(goal_id, sub)
    return jsonify({"id": goal_id}), 201


@app.route("/api/goals/<int:gid>", methods=["PUT"])
def api_update_goal(gid):
    d = request.json
    old = get_goal(gid)
    update_goal(gid,
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
def api_toggle_goal(gid):
    toggle_complete(gid)
    goal = get_goal(gid)
    return jsonify({"completed": goal["completed"] if goal else 0})


@app.route("/api/goals/<int:gid>/progress", methods=["POST"])
def api_update_progress(gid):
    progress = request.json.get("progress", 0)
    update_progress(gid, progress)
    return jsonify({"status": "updated"})


@app.route("/api/goals/<int:gid>", methods=["DELETE"])
def api_delete_goal(gid):
    goal = get_goal(gid)
    if goal:
        remove_from_calendar(goal["title"])
    delete_goal(gid)
    return jsonify({"status": "deleted"})


@app.route("/api/goals/reorder", methods=["POST"])
def api_reorder():
    ids = request.json.get("ids", [])
    reorder_goals(ids)
    return jsonify({"status": "reordered"})


@app.route("/api/goals/overdue", methods=["GET"])
def api_overdue():
    return jsonify(get_overdue_goals())


# ── Subtasks ──

@app.route("/api/subtasks", methods=["POST"])
def api_add_subtask():
    d = request.json
    sid = add_subtask(d["goal_id"], d["title"])
    return jsonify({"id": sid}), 201


@app.route("/api/subtasks/<int:sid>/toggle", methods=["POST"])
def api_toggle_subtask(sid):
    toggle_subtask(sid)
    return jsonify({"status": "toggled"})


@app.route("/api/subtasks/<int:sid>", methods=["DELETE"])
def api_del_subtask(sid):
    delete_subtask(sid)
    return jsonify({"status": "deleted"})


# ── Notes ──

@app.route("/api/notes", methods=["GET"])
def api_get_notes():
    date = request.args.get("date")
    if date:
        note = get_note(date)
        return jsonify(note or {"date": date, "content": "", "mood": 3})
    return jsonify(get_all_notes())


@app.route("/api/notes", methods=["POST"])
def api_save_note():
    d = request.json
    save_note(d["date"], d["content"], d.get("mood", 3))
    return jsonify({"status": "saved"})


# ── Stats ──

@app.route("/api/stats", methods=["GET"])
def api_stats():
    return jsonify(get_completion_stats())


# ── AI Agent ──

@app.route("/api/agent", methods=["GET"])
def api_agent():
    return jsonify(get_agent_insights())


# ── Export ──

@app.route("/api/export/csv", methods=["GET"])
def api_export_csv():
    goals = get_all_goals()
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
def api_test_notification():
    success = send_mac_notification("MyTracker", "Notifications are working!")
    return jsonify({"success": success})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
