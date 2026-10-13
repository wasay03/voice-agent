"""Guards for the layering rules in docs (section 2.1 of the implementation plan)."""

import ast
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
SQL = APP.parent / "sql"
TABLES = {p.stem.split("_", 1)[1] for p in (SQL / "models").glob("*.sql")}


def _sources(package: str) -> list[Path]:
    return [p for p in (APP / package).rglob("*.py") if p.name != "__init__.py"]


def _string_literals(path: Path) -> list[str]:
    """String constants that are not docstrings."""
    tree = ast.parse(path.read_text())
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings
    ]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_repositories_only_call_routines() -> None:
    table_ref = re.compile(rf"\b(FROM|JOIN|INTO|UPDATE)\s+({'|'.join(TABLES)})\b", re.IGNORECASE)
    dml = re.compile(r"\b(INSERT|DELETE)\b|\bUPDATE\s+\w+\s+SET\b", re.IGNORECASE)
    for path in _sources("db/repositories"):
        for text in _string_literals(path):  # SQL lives in strings; comments and docstrings may mention DML
            assert not table_ref.search(text), f"{path.name} references a table directly: {text!r}"
            assert not dml.search(text), f"{path.name} contains DML; use a stored procedure: {text!r}"


def test_services_never_touch_the_driver_or_client() -> None:
    for path in _sources("services"):
        forbidden = {
            m for m in _imports(path) if m.startswith(("asyncpg", "app.db.client", "app.db.repositories"))
        }
        assert not forbidden, f"{path.name} imports {forbidden}; go through the unit of work"


def test_domain_and_utils_have_no_io_or_upward_imports() -> None:
    for package in ("domain", "utils"):
        for path in _sources(package):
            bad = {
                m
                for m in _imports(path)
                if m.startswith(
                    ("asyncpg", "fastapi", "httpx", "app.db", "app.services", "app.api", "app.agent")
                )
                or m.startswith("app.telephony")
            }
            assert not bad, f"{path.name} imports {bad}"


def test_every_routine_lives_in_its_own_file() -> None:
    for folder, keyword in (("functions", "FUNCTION"), ("procedures", "PROCEDURE")):
        for path in (SQL / folder).glob("*.sql"):
            names = re.findall(rf"CREATE OR REPLACE {keyword}\s+(\w+)", path.read_text())
            assert names == [path.stem], f"{path.name} must define exactly {path.stem}"
