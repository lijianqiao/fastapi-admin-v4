"""Static checks over the Alembic migration chain (no database required)."""

import re
from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"
REVISION = re.compile(r'^revision[^=]*= "([0-9a-f]+)"', re.MULTILINE)
DOWN_REVISION = re.compile(r"^down_revision[^=]*= (.+)$", re.MULTILINE)


def _sources() -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in sorted(VERSIONS.glob("*.py"))}


def test_every_downgrade_requires_explicit_opt_in() -> None:
    unguarded = []
    for name, source in _sources().items():
        downgrade_body = source.split("def downgrade() -> None:", 1)[1]
        if "_require_destructive_downgrade()" not in downgrade_body:
            unguarded.append(name)

    assert unguarded == []


def test_revisions_form_a_single_linear_chain() -> None:
    parents: dict[str, str | None] = {}
    for name, source in _sources().items():
        revision = REVISION.search(source)
        down_revision = DOWN_REVISION.search(source)
        assert revision is not None and down_revision is not None, name
        value = down_revision.group(1).strip()
        parents[revision.group(1)] = None if value == "None" else value.strip("\"'")

    referenced = [parent for parent in parents.values() if parent is not None]
    assert [rev for rev, parent in parents.items() if parent is None] != [], "缺少根版本"
    assert len([rev for rev, parent in parents.items() if parent is None]) == 1
    assert len(referenced) == len(set(referenced)), "存在分叉"
    assert set(referenced) <= set(parents), "down_revision 指向不存在的版本"
    assert len(set(parents) - set(referenced)) == 1, "存在多个 head"
