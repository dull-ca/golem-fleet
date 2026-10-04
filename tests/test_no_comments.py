import ast
import io
import tokenize
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
DOCSTRING_OWNERS = (
    ast.Module,
    ast.ClassDef,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
)
VIOLATION_REMEDY = (
    "golem-fleet documents itself through names and structure, so delete "
    "each comment and docstring listed below, or rename what it was explaining:"
)


def source_files() -> list[Path]:
    return sorted(
        path
        for directory in ("golem_fleet", "tests")
        for path in (REPOSITORY_ROOT / directory).rglob("*.py")
        if "__pycache__" not in path.parts
    )


def comment_lines(source: str) -> list[int]:
    readline = io.StringIO(source).readline
    return [
        token.start[0]
        for token in tokenize.generate_tokens(readline)
        if token.type == tokenize.COMMENT
    ]


def docstring_lines(source: str) -> list[int]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, DOCSTRING_OWNERS):
            continue
        body = getattr(node, "body", [])
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            found.append(first.lineno)
    return found


def violations_in(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    relative = path.relative_to(REPOSITORY_ROOT)
    found = (
        ("comment", comment_lines(source)),
        ("docstring", docstring_lines(source)),
    )
    return [
        f"{relative}:{line} carries a {kind}" for kind, lines in found for line in lines
    ]


def test_no_source_file_carries_a_comment_or_a_docstring() -> None:
    violations = [
        violation for path in source_files() for violation in violations_in(path)
    ]

    assert not violations, "\n".join([VIOLATION_REMEDY, *violations])
