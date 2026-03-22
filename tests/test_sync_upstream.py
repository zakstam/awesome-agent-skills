import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from sync_upstream import extract_section_name

def test_extract_section_from_summary_h3():
    line = '<summary><h3 style="display:inline">Official Claude Skills </h3></summary>'
    assert extract_section_name(line) == "Official Claude Skills"

def test_extract_section_from_summary_h3_no_style():
    line = '<summary><h3>Skills by Stripe Team</h3></summary>'
    assert extract_section_name(line) == "Skills by Stripe Team"

def test_extract_section_from_h3_heading():
    line = '### Community Skills'
    assert extract_section_name(line) == "Community Skills"

def test_extract_section_from_h2_heading():
    line = '## ⭐ Top 15 Most Popular Skills'
    assert extract_section_name(line) == "Top 15 Most Popular Skills"

def test_extract_section_from_h2_plain():
    line = '## Skills Paths for Other AI Coding Assistants'
    assert extract_section_name(line) == "Skills Paths for Other AI Coding Assistants"

def test_no_section_in_regular_line():
    line = '| [foo](https://github.com/foo/bar) | description |'
    assert extract_section_name(line) is None


from sync_upstream import SkillEntry, parse_readme

def test_parse_two_column_table():
    readme = """<details>
<summary><h3 style="display:inline">Official Claude Skills </h3></summary>

| Skill | Description |
|-------|-------------|
| [anthropics/docx](https://github.com/anthropics/skills/tree/main/skills/docx) | Create Word documents |

</details>"""
    skills = parse_readme(readme)
    url = "https://github.com/anthropics/skills/tree/main/skills/docx"
    assert url in skills
    assert skills[url].description == "Create Word documents"
    assert skills[url].section == "Official Claude Skills"

def test_parse_three_column_table():
    readme = """### Community Skills

<details>
<summary><h3 style="display:inline">Marketing</h3></summary>

| Skill | Stars | Description |
|-------|-------|-------------|
| [foo/bar](https://github.com/foo/bar) | ![GitHub Stars](https://img.shields.io/github/stars/foo/bar) | SEO tool |

</details>"""
    skills = parse_readme(readme)
    url = "https://github.com/foo/bar"
    assert url in skills
    assert skills[url].description == "SEO tool"
    assert skills[url].section == "Community Skills > Marketing"

def test_skip_top15_table():
    readme = """## ⭐ Top 15 Most Popular Skills

| # | Skill | Stars | Description |
|---|-------|-------|-------------|
| 1 | [foo/bar](https://github.com/foo/bar) | ![stars] | Top skill |

## Next Section"""
    skills = parse_readme(readme)
    assert len(skills) == 0

def test_skip_compatibility_table():
    readme = """## Skills Paths for Other AI Coding Assistants

| Tool | Project Path | Global Path | Official Docs |
|------|-------------|-------------|---------------|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` | [Docs](https://docs.anthropic.com) |"""
    skills = parse_readme(readme)
    assert len(skills) == 0


from sync_upstream import diff_skills

def test_diff_finds_new_skills():
    upstream = {
        "https://github.com/a/1": SkillEntry("https://github.com/a/1", "Skill A", "Section A", "| raw |"),
        "https://github.com/b/2": SkillEntry("https://github.com/b/2", "Skill B", "Section B", "| raw |"),
    }
    local = {
        "https://github.com/a/1": SkillEntry("https://github.com/a/1", "Skill A", "Section A", "| raw |"),
    }
    snapshot_urls = set()
    new, removed = diff_skills(upstream, local, snapshot_urls)
    assert "https://github.com/b/2" in new
    assert len(removed) == 0

def test_diff_finds_removed_skills():
    upstream = {
        "https://github.com/a/1": SkillEntry("https://github.com/a/1", "Skill A", "Section A", "| raw |"),
    }
    local = {
        "https://github.com/a/1": SkillEntry("https://github.com/a/1", "Skill A", "Section A", "| raw |"),
    }
    snapshot_urls = {"https://github.com/a/1", "https://github.com/c/3"}
    new, removed = diff_skills(upstream, local, snapshot_urls)
    assert len(new) == 0
    assert "https://github.com/c/3" in removed

def test_diff_no_snapshot_skips_removals():
    upstream = {"https://github.com/a/1": SkillEntry("https://github.com/a/1", "A", "S", "|")}
    local = {"https://github.com/a/1": SkillEntry("https://github.com/a/1", "A", "S", "|")}
    new, removed = diff_skills(upstream, local, snapshot_urls=None)
    assert len(new) == 0
    assert len(removed) == 0


import tempfile
from sync_upstream import load_snapshot, save_snapshot

def test_load_snapshot_missing_file():
    result = load_snapshot("/nonexistent/path.json")
    assert result is None

def test_save_and_load_snapshot():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "snapshot.json")
        urls = {"https://github.com/a/1", "https://github.com/b/2"}
        save_snapshot(path, urls)
        loaded = load_snapshot(path)
        assert loaded == urls
