import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime
import re

URL = "https://southshoreadultsoccer.com/schedule-union-point-weymouth/"
YOUR_TEAM_KEYWORD = "gray"
YEAR = 2026  # season year


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

    date_pattern = re.compile(r"^\d{1,2}/\d{1,2}$")      # e.g., 5/29
    time_pattern = re.compile(r"^\d{1,2}:\d{2}$")        # e.g., 8:15

    while i < len(lines):
        line = lines[i]

        # Detect a date row
        if date_pattern.match(line):
            current_date = line
            i += 1

            # 1) Collect matchups (lines with "vs")
            matchups = []
            while i < len(lines) and " vs " in lines[i].lower():
                matchups.append(lines[i])
                i += 1

            if not matchups:
                continue

            num_games = len(matchups)

            # 2) Collect fields (lines starting with "field")
            fields = []
            while i < len(lines) and lines[i].lower().startswith("field"):
                fields.append(lines[i])
                i += 1

            # 3) Collect times (lines matching time pattern)
            times = []
            while i < len(lines) and time_pattern.match(lines[i]):
                times.append(lines[i])
                i += 1

            # 4) Collect refs (lines starting with "ref")
            refs = []
            while i < len(lines) and lines[i].lower().startswith("ref"):
                refs.append(lines[i])
                i += 1

            # Build games per column
            for idx in range(num_games):
                matchup = matchups[idx]
                field = fields[idx] if idx < len(fields) else None
                time = times[idx] if idx < len(times) else None

                # Parse teams
                if "vs" not in matchup.lower():
                    continue
                home, away = [t.strip() for t in matchup.split("vs", 1)]

                # Build datetime
                if time:
                    # Assume PM unless explicitly AM
                    if "am" in time.lower():
                        dt = datetime.strptime(
                            f"{YEAR} {current_date} {time}",
                            "%Y %m/%d %I:%M %p"
                        )
                    else:
                        dt = datetime.strptime(
                            f"{YEAR} {current_date} {time} PM",
                            "%Y %m/%d %I:%M %p"
                        )
                else:
                    # No time → default to midnight
                    dt = datetime.strptime(
                        f"{YEAR} {current_date} 00:00",
                        "%Y %m/%d %H:%M"
                    )

                games.append({
                    "date": current_date,
                    "time": time,
                    "datetime": dt,
                    "field": field,
                    "home": home,
                    "away": away
                })

            # continue scanning from current i
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
        event.description = (
            f"Field: {g['field']}\n"
            f"Matchup: {g['home']} vs {g['away']}"
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
