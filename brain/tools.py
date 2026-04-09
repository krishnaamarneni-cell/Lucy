from datetime import datetime
import pytz

def get_datetime():
    now = datetime.now(pytz.timezone("America/New_York"))
    return now.strftime("%-I:%M %p on %A, %B %-d, %Y")
