"""Render the profile's activity card (dark + light SVG) from the GitHub contribution calendar.

Uses the GraphQL API when GITHUB_TOKEN is set (GitHub Actions), otherwise the public calendar page.
Stdlib only.  Usage: python activity.py --user abhisn15 --out dist
"""
import argparse, datetime as dt, html, json, math, os, re, urllib.request

TOKENS = {
    "dark": dict(bg="#0D1117", dots="#2A3140", surface="#161B22", border="#30363D", text="#E6EDF3",
                 muted="#8B949E", a1="#99F4FF", a2="#7C9CFF", a3="#C792FF", orb1="#1F6FEB", orb2="#8957E5", orb_op="0.18"),
    "light": dict(bg="#FFFFFF", dots="#E4E8EE", surface="#F6F8FA", border="#D0D7DE", text="#1F2328",
                  muted="#59636E", a1="#0E7C86", a2="#3B5BDB", a3="#8250DF", orb1="#1F6FEB", orb2="#8957E5", orb_op="0.08"),
}


def fetch_graphql(user, token):
    q = """query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{
      totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
    req = urllib.request.Request("https://api.github.com/graphql",
                                 data=json.dumps({"query": q, "variables": {"u": user}}).encode(),
                                 headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                                          "User-Agent": "profile-activity"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]


def fetch_public(user):
    req = urllib.request.Request(f"https://github.com/users/{user}/contributions",
                                 headers={"User-Agent": "Mozilla/5.0 profile-activity"})
    page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    cells = {}
    for tag in re.findall(r"<td[^>]*data-date=[^>]*>", page):
        d = re.search(r'data-date="(\d{4}-\d{2}-\d{2})"', tag)
        i = re.search(r'id="([^"]+)"', tag)
        if d and i:
            cells[d.group(1)] = i.group(1)
    tips = {}
    for for_id, text in re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page):
        m = re.match(r"\s*(\d[\d,]*) contribution", text)
        tips[for_id] = int(m.group(1).replace(",", "")) if m else 0
    return sorted((d, tips.get(i, 0)) for d, i in cells.items())


def stats(days):
    days = sorted(days)
    total = sum(c for _, c in days)
    longest = run = 0
    for _, c in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    current = 0
    rev = list(reversed(days))
    if rev and rev[0][1] == 0:  # today may still be empty: start from yesterday
        rev = rev[1:]
    for _, c in rev:
        if c == 0:
            break
        current += 1
    wd = [0] * 7
    for d, c in days:
        wd[dt.date.fromisoformat(d).weekday()] += c
    busiest = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][wd.index(max(wd))]
    weeks, cur = [], []  # weeks end on Saturday, like the GitHub calendar
    for d, c in days:
        cur.append((d, c))
        if dt.date.fromisoformat(d).weekday() == 5:
            weeks.append(cur)
            cur = []
    if cur:
        weeks.append(cur)
    weeks = weeks[-53:]
    return dict(total=total, longest=longest, current=current, busiest=busiest,
                weeks=[(w[0][0], sum(c for _, c in w)) for w in weeks])


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def render(s, t, today):
    W, H = 840, 300
    x0, x1, base, top = 44, 796, 246, 132
    n = len(s["weeks"])
    step = (x1 - x0) / n
    bw = max(4.0, step * 0.68)
    mx = max([c for _, c in s["weeks"]] + [1])
    peak_i = max(range(n), key=lambda i: s["weeks"][i][1])
    bars, months, last_m = [], [], None
    for i, (start, c) in enumerate(s["weeks"]):
        x = x0 + i * step + (step - bw) / 2
        if c == 0:
            bars.append(f'<rect x="{x:.1f}" y="{base - 3}" width="{bw:.1f}" height="3" rx="1.5" fill="{t["border"]}"/>')
        else:
            h = max(6.0, (base - top) * math.sqrt(c / mx))
            bars.append(f'<rect class="bar" style="animation-delay:{i * 22}ms" x="{x:.1f}" y="{base - h:.1f}" '
                        f'width="{bw:.1f}" height="{h:.1f}" rx="{min(3, bw / 2):.1f}" fill="url(#bar)"/>')
        m = start[:7]
        if m != last_m:
            if last_m is not None:
                label = dt.date.fromisoformat(start).strftime("%b").upper()
                months.append(f'<text x="{x:.1f}" y="{base + 20}" class="mono axis">{label}</text>')
            last_m = m
    px = x0 + peak_i * step + step / 2
    ph = max(6.0, (base - top) * math.sqrt(s["weeks"][peak_i][1] / mx))
    peak_label = plural(s["weeks"][peak_i][1], "contribution")
    anchor = "end" if px > 700 else ("start" if px < 140 else "middle")
    stats_block = ""
    for k, (label, value) in enumerate((("CURRENT STREAK", plural(s["current"], "day")),
                                        ("LONGEST STREAK", plural(s["longest"], "day")),
                                        ("MOST ACTIVE", s["busiest"]))):
        sx = 420 + k * 130
        if k:
            stats_block += f'<line x1="{sx - 16}" y1="46" x2="{sx - 16}" y2="88" stroke="{t["border"]}"/>'
        stats_block += (f'<text x="{sx}" y="58" class="mono label">{label}</text>'
                        f'<text x="{sx}" y="82" class="sans stat">{html.escape(value)}</text>')
    total = f"{s['total']:,}"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
  <title id="t">GitHub activity, last 12 months</title>
  <desc id="d">{total} contributions. Current streak {plural(s["current"], "day")}, longest streak {plural(s["longest"], "day")}, most active on {s["busiest"]}.</desc>
  <defs>
    <linearGradient id="num" x1="0" y1="0" x2="260" y2="0" gradientUnits="userSpaceOnUse" spreadMethod="reflect">
      <stop offset="0" stop-color="{t['a1']}"/><stop offset="0.5" stop-color="{t['a2']}"/><stop offset="1" stop-color="{t['a3']}"/>
      <animateTransform attributeName="gradientTransform" type="translate" values="0 0;260 0;0 0" dur="8s" repeatCount="indefinite"/>
    </linearGradient>
    <linearGradient id="bar" x1="{x0}" y1="0" x2="{x1}" y2="0" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{t['a1']}"/><stop offset="0.5" stop-color="{t['a2']}"/><stop offset="1" stop-color="{t['a3']}"/>
    </linearGradient>
    <linearGradient id="scan" x1="0" x2="1"><stop offset="0" stop-color="{t['a1']}" stop-opacity="0"/><stop offset="0.5" stop-color="{t['a1']}" stop-opacity="0.22"/><stop offset="1" stop-color="{t['a1']}" stop-opacity="0"/></linearGradient>
    <pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1.1" fill="{t['dots']}"/></pattern>
    <filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="40"/></filter>
    <clipPath id="frame"><rect width="{W}" height="{H}" rx="18"/></clipPath>
    <clipPath id="chart"><rect x="{x0 - 6}" y="{top - 30}" width="{x1 - x0 + 12}" height="{base - top + 34}"/></clipPath>
  </defs>
  <style>
    .sans {{ font-family: 'Segoe UI', Inter, system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif; }}
    .mono {{ font-family: ui-monospace, 'Cascadia Code', 'SF Mono', Consolas, 'Liberation Mono', monospace; }}
    .tag {{ font-size: 12px; fill: {t['muted']}; letter-spacing: 2px; }}
    .num {{ font-weight: 800; font-size: 46px; letter-spacing: -1px; }}
    .unit {{ font-size: 16px; fill: {t['muted']}; }}
    .label {{ font-size: 10.5px; fill: {t['muted']}; letter-spacing: 1.5px; }}
    .stat {{ font-size: 17px; font-weight: 700; fill: {t['text']}; }}
    .axis {{ font-size: 10.5px; fill: {t['muted']}; letter-spacing: 1px; }}
    .peak {{ font-size: 11px; fill: {t['text']}; }}
    .foot {{ font-size: 10.5px; fill: {t['muted']}; }}
    .bar {{ transform-box: fill-box; transform-origin: 50% 100%; animation: grow .9s cubic-bezier(.2,.8,.2,1) both; }}
    .scan {{ animation: scan 7s ease-in-out infinite; }}
    .orbA {{ animation: driftA 14s ease-in-out infinite; }}
    .orbB {{ animation: driftB 18s ease-in-out infinite; }}
    .ping {{ transform-box: fill-box; transform-origin: center; animation: ping 2.4s ease-out infinite; }}
    @keyframes grow {{ from {{ transform: scaleY(0); }} to {{ transform: scaleY(1); }} }}
    @keyframes scan {{ 0% {{ transform: translateX(-80px); opacity: 0; }} 10% {{ opacity: 1; }} 90% {{ opacity: 1; }} 100% {{ transform: translateX({x1 - x0 + 80}px); opacity: 0; }} }}
    @keyframes driftA {{ 0%,100% {{ transform: translate(0,0); }} 50% {{ transform: translate(60px,24px); }} }}
    @keyframes driftB {{ 0%,100% {{ transform: translate(0,0); }} 50% {{ transform: translate(-70px,-18px); }} }}
    @keyframes ping {{ 0% {{ transform: scale(1); opacity: .9; }} 100% {{ transform: scale(3.2); opacity: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{ .bar,.scan,.orbA,.orbB,.ping {{ animation: none; }} .scan {{ display: none; }} }}
  </style>
  <g clip-path="url(#frame)">
    <rect width="{W}" height="{H}" fill="{t['bg']}"/>
    <rect width="{W}" height="{H}" fill="url(#dots)"/>
    <circle class="orbA" cx="150" cy="30" r="120" fill="{t['orb1']}" opacity="{t['orb_op']}" filter="url(#blur)"/>
    <circle class="orbB" cx="720" cy="280" r="130" fill="{t['orb2']}" opacity="{t['orb_op']}" filter="url(#blur)"/>

    <rect x="{x0 - 4}" y="34" width="6" height="64" rx="3" fill="{t['a1']}"/>
    <text x="{x0 + 14}" y="48" class="mono tag">ACTIVITY · LAST 12 MONTHS</text>
    <text x="{x0 + 12}" y="96" class="sans"><tspan class="num" fill="url(#num)">{total}</tspan><tspan class="unit" dx="12">contributions</tspan></text>
    {stats_block}

    <line x1="{x0}" y1="{base + 0.5}" x2="{x1}" y2="{base + 0.5}" stroke="{t['border']}"/>
    <g clip-path="url(#chart)">
      {''.join(bars)}
      <rect class="scan" x="{x0 - 40}" y="{top - 10}" width="80" height="{base - top + 10}" fill="url(#scan)"/>
    </g>
    <circle class="ping" cx="{px:.1f}" cy="{base - ph - 10:.1f}" r="3" fill="{t['a1']}"/>
    <circle cx="{px:.1f}" cy="{base - ph - 10:.1f}" r="3" fill="{t['a1']}"/>
    <text x="{px:.1f}" y="{base - ph - 20:.1f}" text-anchor="{anchor}" class="mono peak">peak week · {peak_label}</text>
    {''.join(months)}
    <text x="{x1}" y="{H - 16}" text-anchor="end" class="mono foot">updated {today}</text>
    <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="18" fill="none" stroke="{t['border']}"/>
  </g>
</svg>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--out", default="dist")
    a = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    days = fetch_graphql(a.user, token) if token else fetch_public(a.user)
    if not days:
        raise SystemExit("no contribution data")
    s = stats(days)
    os.makedirs(a.out, exist_ok=True)
    today = dt.date.today().isoformat()
    for name, t in TOKENS.items():
        with open(os.path.join(a.out, f"activity-{name}.svg"), "w", encoding="utf-8", newline="\n") as f:
            f.write(render(s, t, today))
    print(json.dumps({k: v for k, v in s.items() if k != "weeks"}), len(s["weeks"]), "weeks")


if __name__ == "__main__":
    main()
