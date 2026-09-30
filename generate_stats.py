"""Generates stats.svg and languages.svg from your real GitHub data.
Lives in the storage repo; writes stats.svg + languages.svg next to your other SVGs.
Uses only the Python standard library."""
import html
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

USER = os.environ.get("GH_USER", "kushwaha-aryan")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT_DIR", ".")
F = "font-family=\"'Segoe UI',Ubuntu,'Helvetica Neue',Arial,sans-serif\""


def _request(url, data=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-stats"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def rest(path):
    return _request("https://api.github.com" + path)


def graphql(query):
    body = json.dumps({"query": query}).encode()
    res = _request("https://api.github.com/graphql", data=body)
    if "errors" in res:
        raise RuntimeError(res["errors"])
    return res["data"]


def fetch():
    user = rest(f"/users/{USER}")
    repos, page = [], 1
    while True:
        chunk = rest(f"/users/{USER}/repos?per_page=100&type=owner&page={page}")
        repos += chunk
        if len(chunk) < 100:
            break
        page += 1
    own = [r for r in repos if not r["fork"]]
    stars = sum(r["stargazers_count"] for r in own)
    langs = {}
    for r in own:
        try:
            for name, size in rest(f"/repos/{r['full_name']}/languages").items():
                langs[name] = langs.get(name, 0) + size
        except Exception as e:  # one bad repo should not break everything
            print("skip languages for", r["full_name"], e, file=sys.stderr)
    commits = None
    try:
        d = graphql('{ user(login: "%s") { contributionsCollection { totalCommitContributions } } }' % USER)
        commits = d["user"]["contributionsCollection"]["totalCommitContributions"]
    except Exception as e:
        print("commit count unavailable:", e, file=sys.stderr)
    return {
        "repos": user["public_repos"],
        "followers": user["followers"],
        "following": user["following"],
        "stars": stars,
        "commits": commits,
        "langs": langs,
    }


DEFS = '''<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1b1f3b"/><stop offset="1" stop-color="#2d1b4e"/></linearGradient>
<linearGradient id="acc" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#7f7fff"/><stop offset="1" stop-color="#e879f9"/></linearGradient>'''


def frame(title, body, extra_defs="", note=""):
    return f'''<svg width="420" height="290" viewBox="0 0 420 290" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{title}">
<defs>{DEFS}{extra_defs}</defs>
<rect width="420" height="290" rx="24" fill="url(#bg)"/>
<rect x="1" y="1" width="418" height="288" rx="23" fill="none" stroke="url(#acc)" stroke-opacity="0.55" stroke-width="1.5"/>
<text x="28" y="45" font-size="20" font-weight="700" fill="url(#acc)" {F}>{title}</text>
<rect x="28" y="54" width="48" height="3" rx="1.5" fill="url(#acc)"/>
{body}
<text x="28" y="274" font-size="10.5" fill="#9aa0d6" {F}>{html.escape(note)}</text>
</svg>'''


def fmt(n):
    return "-" if n is None else f"{n:,}"


def stats_svg(s):
    items = [
        ("Commits (last year)", fmt(s["commits"])),
        ("Stars earned", fmt(s["stars"])),
        ("Public repos", fmt(s["repos"])),
        ("Followers", fmt(s["followers"])),
    ]
    rows = ""
    for i, (label, value) in enumerate(items):
        y = 95 + i * 44
        rows += f'''<rect x="28" y="{y-24}" width="364" height="36" rx="12" fill="#ffffff" fill-opacity="0.06"/>
<circle cx="50" cy="{y-6}" r="5" fill="url(#acc)"/>
<text x="68" y="{y}" font-size="14" fill="#c9cdf5" {F}>{label}</text>
<text x="372" y="{y}" font-size="16" font-weight="700" fill="#ffffff" text-anchor="end" {F}>{value}</text>'''
    today = datetime.now(timezone.utc).strftime("%d %b %Y")
    return frame("GitHub Stats", rows, note=f"Auto-updated {today}")


PALETTE = [("#60a5fa", "#6366f1"), ("#fbbf24", "#f97316"), ("#a78bfa", "#e879f9"),
           ("#34d399", "#06b6d4"), ("#fb7185", "#f97316")]


def languages_svg(s):
    langs = sorted(s["langs"].items(), key=lambda kv: kv[1], reverse=True)[:5]
    total = sum(v for _, v in langs) or 1
    rows, grads = "", ""
    for i, (name, size) in enumerate(langs):
        c1, c2 = PALETTE[i % len(PALETTE)]
        y = 88 + i * 34
        pct = size / total * 100
        grads += f'<linearGradient id="g{i}" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient>'
        rows += f'''<text x="28" y="{y}" font-size="13.5" fill="#e5e7ff" {F}>{html.escape(name)}</text>
<text x="392" y="{y}" font-size="12.5" fill="#c9cdf5" text-anchor="end" {F}>{pct:.1f}%</text>
<rect x="28" y="{y+7}" width="364" height="9" rx="4.5" fill="#ffffff" fill-opacity="0.08"/>
<rect x="28" y="{y+7}" width="{max(6, 364*pct/100):.1f}" height="9" rx="4.5" fill="url(#g{i})"/>'''
    return frame("Top Languages", rows, extra_defs=grads, note="Share of code by size across public repos")


def main():
    data = fetch()
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "stats.svg"), "w", encoding="utf8").write(stats_svg(data))
    open(os.path.join(OUT, "languages.svg"), "w", encoding="utf8").write(languages_svg(data))
    print("done", {k: v for k, v in data.items() if k != "langs"}, list(data["langs"])[:5])


if __name__ == "__main__":
    main()
