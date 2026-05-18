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
    current_date = None

    date_pattern = re.compile(r"^\d{1,2}/\d{1,2}$")  # e.g., 5/29

    i = 0
    while i < len(lines):
        line = lines[i]

        # Detect date header
        if date_pattern.match(line):
            current_date = line
            i += 1
            continue

        # Detect matchup line: "gray vs purple"
        if " vs " in line.lower():
            matchup = line
            field = None
            time = None

            # Next lines contain field, time, ref
            j = i + 1
            while j < len(lines):
                nxt = lines[j].lower()

                if nxt.startswith("field"):
                    field = lines[j]
                elif re.match(r"^\d{1,2}:\d{2}$", nxt):  # time like 8:15
                    time = lines[j]
                elif nxt.startswith("ref"):
                    pass  # ignore referee
                elif " vs " in nxt or date_pattern.match(nxt):
                    break  # next game or next date
                j += 1

            # Build datetime with correct year
            if time:
                dt = datetime.strptime(f"{YEAR} {current_date} {time}", "%Y %m/%d %H:%M")
            else:
                dt = datetime.strptime(f"{YEAR} {current_date} 00:00", "%Y %m/%d %H:%M")

            home, away = [t.strip() for t in matchup.split("vs")]

            games.append({
                "date": current_date,
                "time": time,
                "datetime": dt,
                "field": field,
                "home": home,
                "away": away
            })

            i = j
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
