import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime
import re

URL = "https://southshoreadultsoccer.com/schedule-union-point-weymouth/"
YOUR_TEAM_KEYWORD = "gray"
YEAR = 2026  # <-- FIXED YEAR


def fetch_html(url):
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.text


def parse_schedule(html):
    soup = BeautifulSoup(html, "html.parser")

    # Extract all text lines, cleaned
    lines = [l.strip() for l in soup.get_text("\n").split("\n")]
    lines = [l for l in lines if l]  # remove empty lines

    games = []
    i = 0

    date_pattern = re.compile(r"^\d{1,2}/\d{1,2}$")  # e.g., 5/29

    while i < len(lines):
        line = lines[i]

        # Detect a date row
        if date_pattern.match(line):
            current_date = line

            # Next 3 rows are the block
            matchups = lines[i+1].split("|")
            fields   = lines[i+2].split("|")
            times    = lines[i+3].split("|")
            refs     = lines[i+4].split("|")

            # Clean whitespace
            matchups = [m.strip() for m in matchups]
            fields   = [f.strip() for f in fields]
            times    = [t.strip() for t in times]
            refs     = [r.strip() for r in refs]

            # Column 0 is the date/day-of-week → skip it
            for col in range(1, len(matchups)):
                matchup = matchups[col]
                field   = fields[col] if col < len(fields) else None
                time    = times[col] if col < len(times) else None

                # Skip empty matchup columns
                if "vs" not in matchup.lower():
                    continue

                # Parse teams
                home, away = [t.strip() for t in matchup.split("vs")]

                # Build datetime
                if time:
                    # Always PM unless explicitly AM
                    if "am" in time.lower():
                        dt = datetime.strptime(f"{YEAR} {current_date} {time}", "%Y %m/%d %I:%M %p")
                    else:
                        dt = datetime.strptime(f"{YEAR} {current_date} {time} PM", "%Y %m/%d %I:%M %p")
                else:
                    # No time → default to 00:00
                    dt = datetime.strptime(f"{YEAR} {current_date} 00:00", "%Y %m/%d %H:%M")

                games.append({
                    "date": current_date,
                    "time": time,
                    "datetime": dt,
                    "field": field,
                    "home": home,
                    "away": away
                })

            # Move to next block (skip 5 rows)
            i += 5
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
        event.name = f"{g['home']} vs {g['away']}"
        event.begin = g["datetime"]
        event.location = g["field"] or "TBD"
        event.description = f"Field: {g['field']}\nMatchup: {g['home']} vs {g['away']}"
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
