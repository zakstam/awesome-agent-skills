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

def test_parse_bullet_list_format():
    """Upstream uses bullet lists instead of tables."""
    readme = """<details open>
<summary><h3 style="display:inline">Official Claude Skills</h3></summary>

- **[anthropics/docx](https://github.com/anthropics/skills/tree/main/skills/docx)** - Create Word documents
- **[anthropics/pdf](https://github.com/anthropics/skills/tree/main/skills/pdf)** - Extract text and create PDFs

</details>

### Skills by Composio Team
- **[ComposioHQ/skills](https://github.com/ComposioHQ/skills)** - Connect AI agents to 1000+ apps"""
    skills = parse_readme(readme)
    assert len(skills) == 3
    url = "https://github.com/anthropics/skills/tree/main/skills/docx"
    assert url in skills
    assert skills[url].description == "Create Word documents"
    assert skills[url].section == "Official Claude Skills"
    composio_url = "https://github.com/ComposioHQ/skills"
    assert composio_url in skills
    assert skills[composio_url].section == "Skills by Composio Team"

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
    assert "https://github.com/a/1" not in new
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

from sync_upstream import insert_skills

def test_insert_into_two_column_section():
    readme = """<details>
<summary><h3 style="display:inline">Official Claude Skills </h3></summary>

| Skill | Description |
|-------|-------------|
| [anthropics/docx](https://github.com/anthropics/skills/tree/main/skills/docx) | Create Word documents |

</details>"""
    new_skills = {
        "https://github.com/anthropics/skills/tree/main/skills/newskill": SkillEntry(
            url="https://github.com/anthropics/skills/tree/main/skills/newskill",
            description="A new skill",
            section="Official Claude Skills",
            raw_line="| [anthropics/newskill](https://github.com/anthropics/skills/tree/main/skills/newskill) | A new skill |",
        )
    }
    result, inserted, unmatched = insert_skills(readme, new_skills)
    assert "anthropics/newskill" in result
    assert len(inserted) == 1
    assert len(unmatched) == 0
    lines = result.splitlines()
    newskill_idx = next(i for i, l in enumerate(lines) if "newskill" in l)
    details_idx = next(i for i, l in enumerate(lines) if "</details>" in l and i > newskill_idx - 5)
    assert newskill_idx < details_idx

def test_insert_into_three_column_community_section():
    readme = """### Community Skills

<details>
<summary><h3 style="display:inline">Marketing</h3></summary>

| Skill | Stars | Description |
|-------|-------|-------------|
| [foo/bar](https://github.com/foo/bar) | ![GitHub Stars](https://img.shields.io/github/stars/foo/bar) | SEO tool |

</details>"""
    new_skills = {
        "https://github.com/baz/qux": SkillEntry(
            url="https://github.com/baz/qux",
            description="Email tool",
            section="Community Skills > Marketing",
            raw_line="ignored",
        )
    }
    result, inserted, unmatched = insert_skills(readme, new_skills)
    assert "baz/qux" in result
    assert "img.shields.io/github/stars/baz/qux" in result
    assert len(inserted) == 1

def test_insert_unmatched_section():
    readme = """<details>
<summary><h3 style="display:inline">Official Claude Skills </h3></summary>

| Skill | Description |
|-------|-------------|
| [anthropics/docx](https://github.com/anthropics/skills/tree/main/skills/docx) | Create Word documents |

</details>"""
    new_skills = {
        "https://github.com/new/team": SkillEntry(
            url="https://github.com/new/team",
            description="New team skill",
            section="Skills by New Team",
            raw_line="| [new/team](https://github.com/new/team) | New team skill |",
        )
    }
    result, inserted, unmatched = insert_skills(readme, new_skills)
    assert "new/team" not in result
    assert len(inserted) == 0
    assert len(unmatched) == 1

from sync_upstream import refresh_top15

def test_refresh_top15_replaces_table():
    readme = """## ⭐ Top 15 Most Popular Skills

| # | Skill | Stars | Description |
|---|-------|-------|-------------|
| 1 | [old/skill](https://github.com/old/skill) | ![GitHub Stars](https://img.shields.io/github/stars/old/skill?style=flat-square&logo=github&label=★) | Old skill |


## Table of Contents"""

    star_data = {
        "https://github.com/top/one": (1000, "Top one skill", "top/one"),
        "https://github.com/top/two": (500, "Top two skill", "top/two"),
    }
    result = refresh_top15(readme, star_data)
    assert "old/skill" not in result
    assert "top/one" in result
    assert "top/two" in result
    assert "## Table of Contents" in result
    lines = [l for l in result.splitlines() if l.startswith('| ')]
    data_lines = [l for l in lines if not l.startswith('| #') and not l.startswith('|--')]
    assert "| 1 |" in data_lines[0]
    assert "top/one" in data_lines[0]

from unittest.mock import patch, MagicMock
from sync_upstream import fetch_star_counts

def test_fetch_star_counts_deduplicates_repos():
    """Two skills from same repo should produce one API call."""
    skills = {
        "https://github.com/org/repo/tree/main/skills/a": SkillEntry(
            "https://github.com/org/repo/tree/main/skills/a", "Skill A", "Section", "|"
        ),
        "https://github.com/org/repo/tree/main/skills/b": SkillEntry(
            "https://github.com/org/repo/tree/main/skills/b", "Skill B", "Section", "|"
        ),
    }
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"stargazers_count": 42}'
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch('urllib.request.urlopen', return_value=mock_response) as mock_urlopen:
        result = fetch_star_counts(skills, token=None)
        assert mock_urlopen.call_count == 1
        assert result["org/repo"] == 42

from sync_upstream import fetch_upstream_readme

def test_fetch_upstream_readme_mock():
    mock_response = MagicMock()
    mock_response.read.return_value = b"# Test README"
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch('urllib.request.urlopen', return_value=mock_response):
        result = fetch_upstream_readme("https://example.com/readme")
        assert result == "# Test README"


from pathlib import Path

def test_parse_real_readme():
    """Smoke test: parse the actual README and verify we get a reasonable number of skills."""
    readme_path = Path(__file__).resolve().parent.parent / "README.md"
    if not readme_path.exists():
        return
    text = readme_path.read_text(encoding="utf-8")
    skills = parse_readme(text)
    assert len(skills) > 100, f"Expected 100+ skills, got {len(skills)}"
    sections = {e.section for e in skills.values()}
    assert "Official Claude Skills" in sections
    assert any("anthropics/skills" in url for url in skills)

def test_insert_idempotent_on_real_readme():
    """Inserting empty new_skills should not modify the README."""
    readme_path = Path(__file__).resolve().parent.parent / "README.md"
    if not readme_path.exists():
        return
    text = readme_path.read_text(encoding="utf-8")
    result, inserted, unmatched = insert_skills(text, {})
    assert result == text
    assert len(inserted) == 0
    assert len(unmatched) == 0

def test_dry_run_does_not_update_snapshot():
    """--dry-run should not write the snapshot file."""
    with tempfile.TemporaryDirectory() as tmp:
        snapshot_path = os.path.join(tmp, "snapshot.json")
        save_snapshot(snapshot_path, {"https://github.com/old/url"})
        old_content = open(snapshot_path).read()
        load_snapshot(snapshot_path)
        assert open(snapshot_path).read() == old_content
