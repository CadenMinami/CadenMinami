"""Tests for the README activity feed (no network: events are hand-written dicts)."""
import pytest

from scripts.update_activity import END, START, format_events, replace_block

USER = "CadenMinami"


def _ev(kind: str, repo: str, payload: dict | None = None, when: str = "2026-11-15T10:00:00Z") -> dict:
    return {"type": kind, "repo": {"name": f"{USER}/{repo}"}, "payload": payload or {}, "created_at": when}


def test_formats_the_main_event_types() -> None:
    events = [
        _ev("PushEvent", "LaMetro"),
        _ev("PullRequestEvent", "aria-design", {"action": "opened", "number": 4,
            "pull_request": {"title": "Add dark mode", "html_url": "https://github.com/x/pull/4", "merged": False}}),
        _ev("ReleaseEvent", "clash-simulator", {"action": "published",
            "release": {"tag_name": "v1.0", "html_url": "https://github.com/x/releases/v1.0"}}),
        _ev("CreateEvent", "new-thing", {"ref_type": "repository"}),
    ]
    lines = format_events(events, USER)
    assert "Pushed to [LaMetro](https://github.com/CadenMinami/LaMetro)" in lines[0]
    assert "Opened PR [#4 Add dark mode](https://github.com/x/pull/4)" in lines[1]
    assert "Released [v1.0]" in lines[2]
    assert "Created repo [new-thing]" in lines[3]


def test_skips_the_profile_repo_and_noise_events() -> None:
    events = [_ev("PushEvent", USER), _ev("WatchEvent", "LaMetro"), _ev("PushEvent", "LaMetro")]
    lines = format_events(events, USER)
    assert len(lines) == 1 and "LaMetro" in lines[0]


def _pr(repo: str, number: int, action: str = "opened") -> dict:
    # The real Events API (since 2025) sends only a stub: no title, no web URL, no merged flag.
    return _ev("PullRequestEvent", repo, {"action": action, "number": number,
        "pull_request": {"url": f"https://api.github.com/repos/{USER}/{repo}/pulls/{number}", "number": number}})


def test_pr_link_is_built_from_repo_and_number_when_payload_is_trimmed() -> None:
    line = format_events([_pr("BruinBet", 8)], USER)[0]
    assert "Opened PR [#8](https://github.com/CadenMinami/BruinBet/pull/8)" in line
    assert "]()" not in line  # never an empty link


def test_closed_pr_without_merge_info_is_skipped() -> None:
    assert format_events([_pr("BruinBet", 3, action="closed")], USER) == []


def test_collapses_a_run_of_prs_in_one_repo() -> None:
    lines = format_events([_pr("BruinBet", 8), _pr("BruinBet", 7), _pr("BruinBet", 6)], USER)
    assert lines == ["- 🔃 Opened 3 PRs in [BruinBet](https://github.com/CadenMinami/BruinBet) · Nov 15"]


def test_collapses_back_to_back_pushes_to_the_same_repo() -> None:
    events = [_ev("PushEvent", "LaMetro"), _ev("PushEvent", "LaMetro"), _ev("PushEvent", "BruinBet")]
    assert len(format_events(events, USER)) == 2


def test_respects_limit() -> None:
    events = [_ev("CreateEvent", f"r{i}", {"ref_type": "repository"}) for i in range(10)]
    assert len(format_events(events, USER, limit=5)) == 5


def test_merged_pr_says_merged() -> None:
    ev = _ev("PullRequestEvent", "LaMetro", {"action": "closed", "number": 9,
        "pull_request": {"title": "Fix", "html_url": "u", "merged": True}})
    assert format_events([ev], USER)[0].startswith("- 🔀 Merged PR")


def test_replace_block_only_touches_text_between_markers() -> None:
    readme = f"top\n{START}\nold\n{END}\nbottom\n"
    out = replace_block(readme, ["- a", "- b"])
    assert out == f"top\n{START}\n- a\n- b\n{END}\nbottom\n"


def test_replace_block_empty_feed_shows_friendly_note() -> None:
    out = replace_block(f"{START}\n{END}", [])
    assert "private" in out  # explains why public activity can be quiet


def test_replace_block_without_markers_fails_loudly() -> None:
    with pytest.raises(ValueError):
        replace_block("no markers here", ["- a"])
