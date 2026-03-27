import subprocess
import platform


def add_to_calendar(title, description, due_date, due_time):
    if platform.system() != "Darwin" or not due_date:
        return False
    time_part = due_time if due_time else "09:00"
    hour, minute = time_part.split(":")
    year, month, day = due_date.split("-")
    end_hour = str(min(int(hour) + 1, 23)).zfill(2)
    script = f'''
    tell application "Calendar"
        tell calendar "MyTracker"
            set startDate to current date
            set year of startDate to {int(year)}
            set month of startDate to {int(month)}
            set day of startDate to {int(day)}
            set hours of startDate to {int(hour)}
            set minutes of startDate to {int(minute)}
            set seconds of startDate to 0
            set endDate to current date
            set year of endDate to {int(year)}
            set month of endDate to {int(month)}
            set day of endDate to {int(day)}
            set hours of endDate to {int(end_hour)}
            set minutes of endDate to {int(minute)}
            set seconds of endDate to 0
            make new event with properties {{summary:"{title}", description:"{description}", start date:startDate, end date:endDate}}
        end tell
    end tell
    '''
    try:
        ensure_calendar()
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        return True
    except Exception:
        return False


def ensure_calendar():
    script = '''
    tell application "Calendar"
        set calNames to name of every calendar
        if calNames does not contain "MyTracker" then
            make new calendar with properties {name:"MyTracker"}
        end if
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
    except Exception:
        pass


def remove_from_calendar(title):
    if platform.system() != "Darwin":
        return
    script = f'''
    tell application "Calendar"
        tell calendar "MyTracker"
            set matchingEvents to (every event whose summary is "{title}")
            repeat with e in matchingEvents
                delete e
            end repeat
        end tell
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
    except Exception:
        pass
