from apscheduler.schedulers.background import BackgroundScheduler
from notifications import send_mac_notification, send_email_reminder
from models import get_pending_reminders

scheduler = BackgroundScheduler()


def check_reminders():
    """Check for goals due right now and send notifications."""
    goals = get_pending_reminders()
    for goal in goals:
        # Always send macOS notification
        send_mac_notification(
            "MyTracker Reminder",
            f"Time for: {goal['title']}"
        )
        # Send email if configured
        if goal.get("reminder_email"):
            send_email_reminder(
                goal["reminder_email"],
                f"MyTracker Reminder: {goal['title']}",
                f"""
                <h2>Reminder: {goal['title']}</h2>
                <p>{goal['description']}</p>
                <p><strong>Due:</strong> {goal['due_date']} at {goal['due_time']}</p>
                <p>— MyTracker</p>
                """
            )


def start_scheduler():
    """Start the background scheduler that checks every minute."""
    scheduler.add_job(check_reminders, "interval", minutes=1, id="reminder_check", replace_existing=True)
    scheduler.start()


def stop_scheduler():
    scheduler.shutdown(wait=False)
