"""Render the profile's activity card, "A year in orbit" (dark + light SVG), from the GitHub contribution calendar.

Every day of the last year is a dot on a slowly turning spiral: oldest at the centre, today on the rim,
busier days bigger and brighter. No numbers on purpose.

Uses the GraphQL API when GITHUB_TOKEN is set (GitHub Actions), otherwise the public calendar page.
Stdlib only.  Usage: python activity.py --user abhisn15 --out dist
"""
import argparse, datetime as dt, json, math, os, re, urllib.request

TOKENS = {
    "dark": dict(bg="#0D1117", dots="#2A3140", border="#30363D", quiet="#3A4250", text="#E6EDF3",
                 muted="#8B949E", a1="#99F4FF", a2="#7C9CFF", a3="#C792FF", orb1="#1F6FEB", orb2="#8957E5", orb_op="0.18"),
    "light": dict(bg="#FFFFFF", dots="#E4E8EE", border="#D0D7DE", quiet="#C9D1D9", text="#1F2328",
                  muted="#59636E", a1="#0E7C86", a2="#3B5BDB", a3="#8250DF", orb1="#1F6FEB", orb2="#8957E5", orb_op="0.08"),
}


def fetch_graphql(user, token):
    q = """query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{
      weeks{contributionDays{date contributionCount}}}}}}"""
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


def rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def mix(a, b, f):
    return "#" + "".join(f"{round(x + (y - x) * f):02X}" for x, y in zip(rgb(a), rgb(b)))


def ramp(t, f):
    """cyan -> indigo -> violet along the year"""
    return mix(t["a1"], t["a2"], f * 2) if f < 0.5 else mix(t["a2"], t["a3"], (f - 0.5) * 2)


def levels(counts):
    nz = sorted(c for c in counts if c > 0)
    if not nz:
        return [0] * len(counts)
    q = [nz[int(len(nz) * p)] for p in (0.25, 0.5, 0.8)]
    return [0 if c == 0 else 1 + sum(c > x for x in q) for c in counts]


def render(days, t, today):
    W, H = 840, 340
    cx, cy = 612, 170
    r0, r1, turns = 16, 152, 4.25
    days = sorted(days)[-365:]
    n = len(days)
    lv = levels([c for _, c in days])
    pts, dots, glows = [], [], []
    for i, ((_, c), L) in enumerate(zip(days, lv)):
        f = i / max(1, n - 1)
        th = -math.pi / 2 + f * turns * 2 * math.pi
        r = r0 + (r1 - r0) * f
        x, y = cx + r * math.cos(th), cy + r * math.sin(th)
        pts.append(f"{x:.1f},{y:.1f}")
        delay = f"{(i * 37) % 4000}ms"
        if L == 0:
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.1" fill="{t["quiet"]}"/>')
            continue
        col = ramp(t, f)
        rad = (1.8, 2.6, 3.5, 4.8)[L - 1]
        cls = ' class="tw"' if L >= 3 else ""
        style = f' style="animation-delay:{delay}"' if L >= 3 else ""
        if L == 4:
            glows.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{col}" opacity="0.35"/>')
        dots.append(f'<circle{cls}{style} cx="{x:.1f}" cy="{y:.1f}" r="{rad}" fill="{col}"/>')
    lx, ly = pts[-1].split(",")
    legend = "".join(
        f'<circle cx="{58 + k * 16}" cy="252" r="{r}" fill="{ramp(t, 0.15 + k * 0.23) if k else t["quiet"]}"/>'
        for k, r in enumerate((1.1, 1.8, 2.6, 3.5, 4.8)))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
  <title id="t">A year in orbit</title>
  <desc id="d">GitHub activity for the last year drawn as a turning spiral: one dot per day, oldest at the centre and today on the rim; busier days are bigger and brighter.</desc>
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="300" y2="0" gradientUnits="userSpaceOnUse" spreadMethod="reflect">
      <stop offset="0" stop-color="{t['a1']}"/><stop offset="0.5" stop-color="{t['a2']}"/><stop offset="1" stop-color="{t['a3']}"/>
      <animateTransform attributeName="gradientTransform" type="translate" values="0 0;300 0;0 0" dur="8s" repeatCount="indefinite"/>
    </linearGradient>
    <radialGradient id="core"><stop offset="0" stop-color="{t['a1']}" stop-opacity="0.45"/><stop offset="1" stop-color="{t['a1']}" stop-opacity="0"/></radialGradient>
    <pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1.1" fill="{t['dots']}"/></pattern>
    <filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="40"/></filter>
    <filter id="soft" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="4"/></filter>
    <clipPath id="frame"><rect width="{W}" height="{H}" rx="18"/></clipPath>
  </defs>
  <style>
    .sans {{ font-family: 'Segoe UI', Inter, system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif; }}
    .mono {{ font-family: ui-monospace, 'Cascadia Code', 'SF Mono', Consolas, 'Liberation Mono', monospace; }}
    .tag {{ font-size: 12px; fill: {t['muted']}; letter-spacing: 2px; }}
    .h {{ font-weight: 800; font-size: 40px; letter-spacing: -0.8px; }}
    .p {{ font-size: 15px; fill: {t['muted']}; }}
    .small {{ font-size: 10.5px; fill: {t['muted']}; letter-spacing: 1px; }}
    .galaxy {{ transform-origin: {cx}px {cy}px; animation: spin 140s linear infinite; }}
    .trail {{ stroke-dasharray: 2600; animation: draw 3.2s cubic-bezier(.3,.7,.2,1) backwards; }}
    .appear {{ animation: fade 1.2s ease-out .6s backwards; }}
    .tw {{ animation: twinkle 4s ease-in-out infinite; }}
    .ping {{ transform-box: fill-box; transform-origin: center; animation: ping 2.4s ease-out infinite; }}
    .orbA {{ animation: driftA 14s ease-in-out infinite; }}
    .orbB {{ animation: driftB 18s ease-in-out infinite; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    @keyframes draw {{ from {{ stroke-dashoffset: 2600; }} to {{ stroke-dashoffset: 0; }} }}
    @keyframes fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    @keyframes twinkle {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: .45; }} }}
    @keyframes ping {{ 0% {{ transform: scale(1); opacity: .9; }} 100% {{ transform: scale(3.4); opacity: 0; }} }}
    @keyframes driftA {{ 0%,100% {{ transform: translate(0,0); }} 50% {{ transform: translate(60px,24px); }} }}
    @keyframes driftB {{ 0%,100% {{ transform: translate(0,0); }} 50% {{ transform: translate(-70px,-18px); }} }}
    @media (prefers-reduced-motion: reduce) {{
      .galaxy,.tw,.ping,.orbA,.orbB {{ animation: none; }}
      .trail {{ animation: none; stroke-dashoffset: 0; }}
      .appear {{ animation: none; opacity: 1; }}
    }}
  </style>
  <g clip-path="url(#frame)">
    <rect width="{W}" height="{H}" fill="{t['bg']}"/>
    <rect width="{W}" height="{H}" fill="url(#dots)"/>
    <circle class="orbA" cx="160" cy="40" r="120" fill="{t['orb1']}" opacity="{t['orb_op']}" filter="url(#blur)"/>
    <circle class="orbB" cx="640" cy="300" r="140" fill="{t['orb2']}" opacity="{t['orb_op']}" filter="url(#blur)"/>

    <rect x="40" y="58" width="6" height="64" rx="3" fill="{t['a1']}"/>
    <text x="58" y="72" class="mono tag">ACTIVITY · ONE DOT PER DAY</text>
    <text x="56" y="118" class="sans h" fill="url(#g)">A year in orbit</text>
    <text x="58" y="160" class="sans p">The last twelve months, spiralling out</text>
    <text x="58" y="182" class="sans p">from the centre to today. Brighter means busier.</text>
    {legend}
    <text x="54" y="276" class="mono small">QUIET</text>
    <text x="130" y="276" text-anchor="end" class="mono small">BUSY</text>

    <circle cx="{cx}" cy="{cy}" r="34" fill="url(#core)"/>
    <g class="galaxy">
      <polyline class="trail" points="{' '.join(pts)}" fill="none" stroke="{t['border']}" stroke-width="1" opacity="0.7"/>
      <g class="appear">
        <g filter="url(#soft)">{''.join(glows)}</g>
        {''.join(dots)}
        <circle class="ping" cx="{lx}" cy="{ly}" r="4" fill="none" stroke="{t['a3']}" stroke-width="1.5"/>
      </g>
    </g>
    <text x="{W - 24}" y="{H - 18}" text-anchor="end" class="mono small">updated {today}</text>
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
    os.makedirs(a.out, exist_ok=True)
    today = dt.date.today().isoformat()
    for name, t in TOKENS.items():
        with open(os.path.join(a.out, f"activity-{name}.svg"), "w", encoding="utf-8", newline="\n") as f:
            f.write(render(days, t, today))
    print(len(days), "days rendered")


if __name__ == "__main__":
    main()
