import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta, timezone
import re

URL = "https://southshoreadultsoccer.com/schedule-union-point-weymouth/"
YOUR_TEAM_KEYWORD = "gray"
YEAR = 2026

# EDT for the entire season (May–Aug)
ET = timezone(timedelta(hours=-4))

WEEKDAYS = {
    "monday","tuesday","wednesday","thursday",
    "friday","saturday","sunday"
}

def fetch_html(url):
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.text

def parse_schedule(html):
    soup = BeautifulSoup(html, "html.parser")
    lines = [l.strip() for l in soup.get_text("\n").split("\n")]
    lines = [l for l in lines if l]

    games = []
    i = 0

    date_pattern = re.compile(r"^\d{1,2}/\d{1,2}$")
    time_pattern = re.compile(r"^\d{1,2}:\d{2}$")

    while i < len(lines):
        line = lines[i]

        if date_pattern.match(line):
            current_date = line
            i += 1

            # Matchups
            matchups = []
            while i < len(lines) and "vs" in lines[i].lower():
                matchups.append(lines[i])
                i += 1

            num_games = len(matchups)
            if num_games == 0:
                continue

            # Skip weekday
            while i < len(lines) and lines[i].lower() in WEEKDAYS:
                i += 1

            # Fields
            fields = []
            while i < len(lines) and lines[i].lower().startswith("field"):
                fields.append(lines[i])
                i += 1

            # Times
            times = []
            while i < len(lines) and time_pattern.match(lines[i]):
                times.append(lines[i])
                i += 1

            # Refs
            refs = []
            while i < len(lines) and lines[i].lower().startswith("ref"):
                refs.append(lines[i])
                i += 1

            # Build games
            for idx in range(num_games):
                matchup = matchups[idx]
                field = fields[idx] if idx < len(fields) else None
                time = times[idx] if idx < len(times) else None
                ref = refs[idx] if idx < len(refs) else None

                home, away = [t.strip() for t in matchup.split("vs", 1)]

                if time:
                    dt = datetime.strptime(
                        f"{YEAR} {current_date} {time} PM",
                        "%Y %m/%d %I:%M %p"
                    )
                else:
                    dt = datetime.strptime(
                        f"{YEAR} {current_date} 00:00",
                        "%Y %m/%d %H:%M"
                    )

                # Attach EDT timezone
                dt = dt.replace(tzinfo=ET)

                games.append({
                    "date": current_date,
                    "time": time,
                    "datetime": dt,
                    "field": field,
                    "ref": ref,
                    "home": home,
                    "away": away
                })

            continue

        i += 1

    return games

def filter_for_team(games, keyword):
    keyword = keyword.lower()
    return [
        g for g in games
        if keyword in g["home"].lower() or keyword in g["away"].lower()
    ]

def create_ics(games, filename):
    cal = Calendar()

    for g in games:
        event = Event()

        title = f"{g['home'].title()} vs {g['away'].title()}"
        event.name = f"Adult Soccer Game: {title}"

        # Use timezone-aware datetimes
        event.begin = g["datetime"]
        event.end = g["datetime"] + timedelta(minutes=90)

        event.location = g["field"].title() if g["field"] else "TBD"

        ref_clean = g["ref"].replace("ref –", "").strip().title() if g["ref"] else "TBD"
        field_clean = g["field"].title() if g["field"] else "TBD"

        event.description = (
            f"Field: {field_clean}\n"
            f"Referee: {ref_clean}"
        )

        cal.events.add(event)

    with open(filename, "w") as f:
        f.writelines(cal)

def main():
    html = fetch_html(URL)
    games = parse_schedule(html)
    my_games = filter_for_team(games, YOUR_TEAM_KEYWORD)
    create_ics(my_games, "gray_team_schedule.ics")
    print(f"Found {len(my_games)} Gray games.")

if __name__ == "__main__":
    main()
