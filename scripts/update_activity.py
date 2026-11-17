"""Refresh the "Recent activity" section of README.md from my public GitHub events.

Runs daily in GitHub Actions (.github/workflows/activity.yml). It only rewrites
the lines between the two marker comments, so the rest of the README is never
touched. Run it locally with:

    GITHUB_TOKEN=$(gh auth token) python -m scripts.update_activity
"""
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any
import urllib.request

START = "<!-- ACTIVITY:START -->"
END = "<!-- ACTIVITY:END -->"
EMPTY_NOTE = "- 🔒 Quiet on public repos lately: most of my current work is private client work."

Event = dict[str, Any]


def fetch_events(user: str, token: str | None) -> list[Event]:
    """Fetch the user's most recent public events (newest first)."""
    req = urllib.request.Request(
        f"https://api.github.com/users/{user}/events/public?per_page=100",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "profile-activity-updater"},
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data: list[Event] = json.load(resp)
    return data


def format_events(events: list[Event], user: str, limit: int = 5) -> list[str]:
    """Turn raw events into README bullet lines, newest first.

    Skips the profile repo itself (otherwise this bot's own daily commits
    would fill the feed) and event types that aren't real work, like stars.
    A run of the same action in the same repo (three PRs opened in a row,
    five pushes in a row) collapses into one line, so one busy afternoon
    can't take over the whole list.
    """
    groups: list[tuple[Event, int, tuple[str, str]]] = []
    for ev in events:
        full_name: str = ev["repo"]["name"]
        if full_name.lower() == f"{user}/{user}".lower():
            continue
        kind = _kind(ev)
        if kind is None:
            continue
        key = (kind, full_name)
        if groups and groups[-1][2] == key:
            first, count, _ = groups[-1]
            groups[-1] = (first, count + 1, key)
        else:
            groups.append((ev, 1, key))
    return [_format_one(ev, kind, count) for ev, count, (kind, _) in groups[:limit]]


def _kind(ev: Event) -> str | None:
    """Classify an event into one of the kinds we show, or None to skip it."""
    payload: dict[str, Any] = ev.get("payload") or {}
    t = ev["type"]
    if t == "PushEvent":
        return "push"
    if t == "PullRequestEvent":
        if payload.get("action") == "opened":
            return "pr-opened"
        # Since 2025 the Events API usually omits the merged flag. Without it we
        # can't tell a merge from an abandoned PR, so those are left out.
        if payload.get("action") == "closed" and (payload.get("pull_request") or {}).get("merged"):
            return "pr-merged"
        return None
    if t == "ReleaseEvent" and payload.get("action") == "published":
        return "release"
    if t == "CreateEvent" and payload.get("ref_type") == "repository":
        return "repo"
    return None


def _format_one(ev: Event, kind: str, count: int) -> str:
    """Format the newest event of a group; `count` is how many were collapsed into it."""
    full_name: str = ev["repo"]["name"]
    repo = f"[{full_name.split('/')[-1]}](https://github.com/{full_name})"
    when = _short_date(ev.get("created_at", ""))
    payload: dict[str, Any] = ev.get("payload") or {}

    if kind == "push":
        return f"- ⬆️ Pushed to {repo} · {when}"
    if kind in ("pr-opened", "pr-merged"):
        verb, icon = ("Opened", "🔃") if kind == "pr-opened" else ("Merged", "🔀")
        if count > 1:
            return f"- {icon} {verb} {count} PRs in {repo} · {when}"
        pr = payload.get("pull_request") or {}
        number = payload.get("number") or pr.get("number")
        # The web URL and title are often missing now, so build the link ourselves.
        url = pr.get("html_url") or f"https://github.com/{full_name}/pull/{number}"
        label = f"#{number} {pr['title']}" if pr.get("title") else f"#{number}"
        return f"- {icon} {verb} PR [{label}]({url}) in {repo} · {when}"
    if kind == "release":
        rel = payload.get("release") or {}
        return f"- 🚀 Released [{rel.get('tag_name', '')}]({rel.get('html_url', '')}) of {repo} · {when}"
    return f"- ✨ Created repo {repo} · {when}"


def _short_date(iso: str) -> str:
    """'2026-11-15T10:00:00Z' -> 'Nov 15'. Falls back to '' if unparseable."""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%b %-d")
    except ValueError:
        return ""


def replace_block(readme: str, lines: list[str]) -> str:
    """Replace everything between the START and END markers with `lines`."""
    start, end = readme.find(START), readme.find(END)
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"README is missing the {START} / {END} markers")
    body = "\n".join(lines or [EMPTY_NOTE])
    return readme[: start + len(START)] + "\n" + body + "\n" + readme[end:]


def main() -> None:
    user = os.environ.get("GITHUB_USER", "CadenMinami")
    readme_path = Path(os.environ.get("README_PATH", "README.md"))
    events = fetch_events(user, os.environ.get("GITHUB_TOKEN"))
    old = readme_path.read_text(encoding="utf-8")
    new = replace_block(old, format_events(events, user))
    if new != old:
        readme_path.write_text(new, encoding="utf-8")
        print("README activity updated")
    else:
        print("no change")


if __name__ == "__main__":
    main()
