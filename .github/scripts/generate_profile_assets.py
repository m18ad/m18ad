#!/usr/bin/env python3
"""Builds assets/stats.svg and assets/activity.svg from the GitHub GraphQL API.

Runs inside GitHub Actions with the built-in GITHUB_TOKEN. No third-party
services are involved. If the API call fails, the existing files are kept.
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

USER = os.environ.get("USERNAME") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "m18ad"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "assets")

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(privacy: PUBLIC, ownerAffiliations: OWNER, isFork: false, first: 100) {
      totalCount
      nodes { stargazerCount }
    }
  }
}
"""

MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace"
# Black, white and ash palette
CYAN, BLUE, PURPLE = "#f2f2f2", "#9a9a9a", "#bdbdbd"
LEVELS = ["#151515", "#2f2f2f", "#575757", "#8f8f8f", "#f2f2f2"]


def fetch():
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": "profile-assets"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data or not data.get("data", {}).get("user"):
        raise RuntimeError(str(data.get("errors") or "no user"))
    return data["data"]["user"]


def level(count, peak):
    if count <= 0:
        return 0
    q = count / max(peak, 1)
    return 1 if q <= 0.25 else 2 if q <= 0.5 else 3 if q <= 0.75 else 4


def streaks(days):
    """days: list of (date, count) sorted ascending. Returns current, longest."""
    longest = run = 0
    for d, c in days:
        run = run + 1 if c > 0 else 0
        if run > longest:
            longest = run
    # current streak: today may still be empty, so allow it to be skipped
    cur = 0
    seq = list(days)
    if seq and seq[-1][1] == 0:
        seq = seq[:-1]
    for d, c in reversed(seq):
        if c > 0:
            cur += 1
        else:
            break
    return cur, longest


def fmt_day(s):
    d = dt.date.fromisoformat(s)
    return d.strftime("%b ") + str(d.day)


def stats_svg(total, cur, longest, start, end, repos, stars):
    frac = min(cur / longest, 1) if longest else 0
    circ = 2 * 3.14159 * 34
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 150" width="1000" height="150" role="img" aria-label="GitHub statistics for {escape(USER)}">
<defs>
<linearGradient id="ln" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{CYAN}" stop-opacity="0"/><stop offset="0.5" stop-color="{CYAN}" stop-opacity="0.8"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></linearGradient>
<linearGradient id="ring" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{CYAN}"/><stop offset="1" stop-color="{PURPLE}"/></linearGradient>
<style>.m{{font-family:{MONO}}}.n{{font-family:{MONO};font-weight:700;fill:#f0f0f0}}.l{{font-family:{MONO};font-size:12px;fill:{CYAN};letter-spacing:1px}}.s{{font-family:{MONO};font-size:10px;fill:#6e6e6e}}</style>
</defs>
<rect x="2" y="2" width="996" height="146" rx="16" fill="#0b0b0b" stroke="#262626"/>
<line x1="333" y1="26" x2="333" y2="124" stroke="url(#ln)"/><line x1="667" y1="26" x2="667" y2="124" stroke="url(#ln)"/>
<text x="167" y="76" text-anchor="middle" class="n" font-size="40">{total}</text>
<text x="167" y="100" text-anchor="middle" class="l">TOTAL CONTRIBUTIONS</text>
<text x="167" y="120" text-anchor="middle" class="s">{escape(start)} - {escape(end)}</text>
<circle cx="500" cy="62" r="34" fill="none" stroke="#262626" stroke-width="5"/>
<circle cx="500" cy="62" r="34" fill="none" stroke="url(#ring)" stroke-width="5" stroke-linecap="round" stroke-dasharray="{circ * frac:.1f} {circ:.1f}" transform="rotate(-90 500 62)"><animate attributeName="stroke-dasharray" from="0 {circ:.1f}" to="{circ * frac:.1f} {circ:.1f}" dur="1.4s" fill="freeze"/></circle>
<text x="500" y="71" text-anchor="middle" class="n" font-size="26">{cur}</text>
<text x="500" y="116" text-anchor="middle" class="l">CURRENT STREAK</text>
<text x="500" y="135" text-anchor="middle" class="s">longest: {longest} days</text>
<text x="833" y="76" text-anchor="middle" class="n" font-size="40">{repos}</text>
<text x="833" y="100" text-anchor="middle" class="l">PUBLIC REPOSITORIES</text>
<text x="833" y="120" text-anchor="middle" class="s">{stars} stars earned</text>
</svg>'''


def activity_svg(weeks, total):
    peak = max((c for w in weeks for _, c in w), default=0)
    cell, gap, left, top = 13, 3, 40, 52
    width = left + len(weeks) * (cell + gap) + 24
    height = top + 7 * (cell + gap) + 64
    parts, last_month = [], None
    for wi, w in enumerate(weeks):
        x = left + wi * (cell + gap)
        month = dt.date.fromisoformat(w[0][0]).month
        if month != last_month:
            if last_month is None or wi >= 2:
                parts.append(f'<text x="{x}" y="{top - 10}" class="s">{dt.date(2000, month, 1).strftime("%b").upper()}</text>')
            last_month = month
        for di, (d, c) in enumerate(w):
            y = top + di * (cell + gap)
            lv = level(c, peak)
            parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{LEVELS[lv]}"><title>{c} contributions on {d}</title></rect>')
    for di, name in ((1, "MON"), (3, "WED"), (5, "FRI")):
        parts.append(f'<text x="6" y="{top + di * (cell + gap) + 10}" class="s">{name}</text>')
    base = top + 7 * (cell + gap) + 14
    prog_w = width - left - 24
    today = dt.date.today()
    done = min(today.timetuple().tm_yday / 366, 1)
    legend_x = width - 24 - 5 * 16 - 70
    legend = "".join(f'<rect x="{legend_x + 40 + i * 16}" y="{base + 28}" width="12" height="12" rx="3" fill="{c}"/>' for i, c in enumerate(LEVELS))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="GitHub contribution activity for {escape(USER)}: {total} contributions in the last year">
<defs>
<linearGradient id="bar" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{CYAN}"/><stop offset="1" stop-color="{PURPLE}"/></linearGradient>
<style>.s{{font-family:{MONO};font-size:10px;fill:#6e6e6e;letter-spacing:1px}}.l{{font-family:{MONO};font-size:11px;fill:{CYAN};letter-spacing:2px}}</style>
</defs>
<rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="16" fill="#0b0b0b" stroke="#262626"/>
<text x="{left}" y="26" class="l">CONTRIBUTION.ACTIVITY</text>
<text x="{width - 24}" y="26" text-anchor="end" class="s">{total} IN THE LAST YEAR</text>
{"".join(parts)}
<rect x="{left}" y="{base}" width="{prog_w}" height="4" rx="2" fill="#262626"/>
<rect x="{left}" y="{base}" width="{prog_w * done:.0f}" height="4" rx="2" fill="url(#bar)"><animate attributeName="width" from="0" to="{prog_w * done:.0f}" dur="1.6s" fill="freeze"/></rect>
<text x="{left}" y="{base + 38}" class="s">{today.year} PROGRESS {int(done * 100)}%</text>
<text x="{legend_x}" y="{base + 38}" class="s">LESS</text>{legend}<text x="{legend_x + 40 + 5 * 16 + 4}" y="{base + 38}" class="s">MORE</text>
</svg>'''


def main():
    if not TOKEN:
        print("No GITHUB_TOKEN, keeping existing assets")
        return 0
    try:
        user = fetch()
    except Exception as exc:  # keep whatever is already committed
        print("GitHub API failed, keeping existing assets:", exc)
        return 0
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = [[(d["date"], d["contributionCount"]) for d in w["contributionDays"]] for w in cal["weeks"]]
    weeks = [w for w in weeks if w]
    days = [x for w in weeks for x in w]
    cur, longest = streaks(days)
    total = cal["totalContributions"]
    repos = user["repositories"]["totalCount"]
    stars = sum(n["stargazerCount"] for n in user["repositories"]["nodes"])
    start, end = fmt_day(days[0][0]), fmt_day(days[-1][0])
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "stats.svg"), "w") as f:
        f.write(stats_svg(total, cur, longest, start, end, repos, stars))
    with open(os.path.join(OUT, "activity.svg"), "w") as f:
        f.write(activity_svg(weeks, total))
    print(f"ok: {total} contributions, streak {cur}/{longest}, {repos} repos, {stars} stars")
    return 0


if __name__ == "__main__":
    sys.exit(main())
