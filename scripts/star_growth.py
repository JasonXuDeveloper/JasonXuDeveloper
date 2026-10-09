#!/usr/bin/env python3
"""Render compact project star-growth art for the profile README.

Bootstrap uses the star dates of *current* stargazers, so older points are a
reconstruction rather than exact historical net counts. Later points are daily
snapshots of each repository's public stargazers_count.
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "star-growth.json"
OUTPUT = ROOT / "assets"
REPOS = {"JEngine": "JasonXuDeveloper/JEngine", "Nino": "JasonXuDeveloper/Nino"}


def months_between(first: str, last: str):
    year, month = map(int, first.split("-"))
    end_year, end_month = map(int, last.split("-"))
    while (year, month) <= (end_year, end_month):
        yield f"{year:04d}-{month:02d}"
        month += 1
        if month == 13:
            year, month = year + 1, 1


def public_star_count(repo: str) -> int:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-star-growth"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"https://api.github.com/repos/{repo}", headers=headers)
    with urlopen(request, timeout=20) as response:
        return int(json.load(response)["stargazers_count"])


def save(data: dict):
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(data, indent=2) + "\n")


def bootstrap(files: list[str]):
    today = datetime.now(timezone.utc).date().isoformat()
    end_month = today[:7]
    data = {"backfilled_at": today, "repos": {}, "samples": []}
    snapshot = {"date": today}
    for item in files:
        name, path = item.split("=", 1)
        if name not in REPOS:
            raise ValueError(f"Unknown repository: {name}")
        dates = [line.strip() for line in Path(path).read_text().splitlines() if line.strip()]
        if not dates:
            raise ValueError(f"No star dates for {name}")
        by_month = Counter(starred_at[:7] for starred_at in dates)
        total = 0
        monthly = []
        for month in months_between(min(by_month), end_month):
            total += by_month[month]
            monthly.append([month, total])
        current = public_star_count(REPOS[name])
        if total != current:
            raise ValueError(f"{name}: {total} dated stars, but public count is {current}")
        data["repos"][name] = {"monthly": monthly}
        snapshot[name] = current
    if set(data["repos"]) != set(REPOS):
        raise ValueError("Bootstrap requires both JEngine and Nino")
    data["samples"].append(snapshot)
    save(data)
    render(data)


def refresh():
    data = json.loads(DATA.read_text())
    today = datetime.now(timezone.utc).date().isoformat()
    snapshot = {"date": today, **{name: public_star_count(repo) for name, repo in REPOS.items()}}
    if data["samples"] and data["samples"][-1]["date"] == today:
        data["samples"][-1] = snapshot
    else:
        data["samples"].append(snapshot)
    save(data)
    render(data)


def month_end(month: str) -> date:
    year, number = map(int, month.split("-"))
    return date(year, number, calendar.monthrange(year, number)[1])


def coordinates(data: dict, name: str, start: date, end: date, top: int, bottom: int):
    backfilled_on = date.fromisoformat(data["backfilled_at"])
    history = [
        (backfilled_on if month == data["backfilled_at"][:7] else month_end(month), count)
        for month, count in data["repos"][name]["monthly"]
    ]
    history.extend((date.fromisoformat(sample["date"]), sample[name]) for sample in data["samples"])
    history.sort(key=lambda entry: entry[0])
    maximum = max(1, *(count for _, count in history))
    duration = max(1, (end - start).days)
    points = []
    for day, count in history:
        x = 210 + (day - start).days / duration * 630
        y = bottom - count / maximum * (bottom - top)
        points.append((round(x, 2), round(y, 2)))
    return points, history[-1][1]


def path(points):
    return " ".join(f"{'M' if index == 0 else 'L'}{x},{y}" for index, (x, y) in enumerate(points))


def svg(data: dict, theme: str) -> str:
    dark = theme == "dark"
    fg = "#e6edf3" if dark else "#24292f"
    muted = "#8b949e" if dark else "#57606a"
    grid = "#30363d" if dark else "#d0d7de"
    colors = {"JEngine": "#bc8cff" if dark else "#8250df", "Nino": "#56d4dd" if dark else "#0969da"}
    first_month = min(info["monthly"][0][0] for info in data["repos"].values())
    start = date.fromisoformat(first_month + "-01")
    end = max(date.fromisoformat(data["samples"][-1]["date"]), date.fromisoformat(data["backfilled_at"]))
    duration = max(1, (end - start).days)

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 246" role="img" aria-labelledby="title desc">',
        '<title id="title">JEngine and Nino star growth</title>',
        '<desc id="desc">Reconstructed monthly history from current stargazers, followed by daily star-count snapshots.</desc>',
        '<style>@keyframes appear{from{opacity:.25}to{opacity:1}}',
        '.trace{animation:appear 1.2s ease-out both}',
        '@media(prefers-reduced-motion:reduce){.trace{animation:none}}</style>',
        f'<text x="24" y="24" fill="{muted}" font-family="system-ui,sans-serif" font-size="11" letter-spacing="2">PROJECT GROWTH</text>',
    ]
    for name, top, bottom, label_y in (("JEngine", 48, 104, 74), ("Nino", 143, 199, 169)):
        points, count = coordinates(data, name, start, end, top, bottom)
        line = path(points)
        area = f"{line} L{points[-1][0]},{bottom} L{points[0][0]},{bottom} Z"
        color = colors[name]
        parts.extend(
            [
                f'<line x1="210" y1="{bottom}" x2="840" y2="{bottom}" stroke="{grid}" stroke-width="1"/>',
                f'<path d="{area}" fill="{color}" fill-opacity=".10"/>',
                f'<path class="trace" d="{line}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>',
                f'<circle cx="{points[-1][0]}" cy="{points[-1][1]}" r="4.5" fill="{color}"/>',
                f'<text x="24" y="{label_y}" fill="{fg}" font-family="system-ui,sans-serif" font-size="20" font-weight="650">{escape(name)}</text>',
                f'<text x="24" y="{label_y + 23}" fill="{color}" font-family="system-ui,sans-serif" font-size="14" font-weight="600">{count:,} ★</text>',
            ]
        )
    for year in range(start.year, end.year + 1, 2):
        day = date(year, 1, 1)
        if day < start:
            continue
        x = 210 + (day - start).days / duration * 630
        parts.append(f'<text x="{x:.2f}" y="231" text-anchor="middle" fill="{muted}" font-family="system-ui,sans-serif" font-size="11">{year}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def render(data: dict):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for theme in ("light", "dark"):
        (OUTPUT / f"star-growth-{theme}.svg").write_text(svg(data, theme))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", nargs=2, metavar="NAME=PATH")
    parser.add_argument("--refresh", action="store_true")
    options = parser.parse_args()
    if options.bootstrap:
        bootstrap(options.bootstrap)
    elif options.refresh:
        refresh()
    else:
        parser.error("Choose --bootstrap or --refresh")
