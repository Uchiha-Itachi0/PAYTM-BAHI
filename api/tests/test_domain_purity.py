"""bahi/domain imports nothing but the standard library.

This is how "no model ever produces a number" is proved rather than promised.
Every figure the product shows is computed in bahi/domain. If that package cannot
import a database driver, an HTTP client or an AI SDK, then no figure can come
from one. The test reads the source, so it fails before anything runs.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

DOMAIN = Path(__file__).resolve().parents[1] / "bahi" / "domain"
ALLOWED = set(sys.stdlib_module_names) | {"__future__"}


def imported(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def test_there_is_a_domain_to_check() -> None:
    assert len(list(DOMAIN.glob("*.py"))) > 1


def test_domain_imports_only_the_standard_library() -> None:
    bad = [
        f"{path.name} imports {name}"
        for path in sorted(DOMAIN.glob("*.py"))
        for name in sorted(imported(path))
        if name.split(".")[0] not in ALLOWED and not name.startswith("bahi.domain")
    ]
    assert bad == []
