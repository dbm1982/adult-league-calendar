import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime
import json

URL = "https://southshoreadultsoccer.com/schedule-union-point-weymouth/"
YOUR_TEAM_KEYWORD = "gray"   # case-insensitive match


def fetch_html(url):
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.text


def parse_schedule(html):
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    games = []
    teams = set()

    for table in tables:
        rows = table.find_all("tr")
        for row in rows[1:]:
            cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cols) < 5:
                continue

            date_str, time_str, field, home, away = cols[:5]
            teams.add(home)
            teams.add(away)

            try:
                dt = datetime.strptime(f"{date_str} {time_str}", "%m/%d/%Y %I:%M %p")
            except ValueError:
                continue

            games.append({
                "date": date_str,
                "time": time_str,
                "datetime": dt,
                "field": field,
                "home": home,
                "away": away
            })

    return games, sorted(list(teams))


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
        event.location = g["field"]
        event.description = (
            f"South Shore Adult Soccer League\n"
            f"Field: {g['field']}\n"
            f"Matchup: {g['home']} vs {g['away']}"
        )
        cal.events.add(event)

    with open(filename, "w") as f:
        f.writelines(cal)


def main():
    html = fetch_html(URL)
    games, teams = parse_schedule(html)

    with open("teams.json", "w") as f:
        json.dump(teams, f, indent=2)

    my_games = filter_for_team(games, YOUR_TEAM_KEYWORD)
    create_ics(my_games, filename="gray_team_schedule.ics")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
