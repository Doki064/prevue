"""Parse-only import extraction for multi-call file co-location (D-06, ENGN-06).

Security: ast.parse only — never eval/exec/compile-and-run. Regex is read-only.
No subprocess. All per-file scans degrade gracefully (never raise).
"""

from __future__ import annotations

import ast
import os
import re

_PY_EXTENSIONS = frozenset({".py", ".pyi"})
_JS_EXTENSIONS = frozenset({".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"})


def _ext(path: str) -> str:
    return os.path.splitext(path)[1].lower()


def _added_lines(patch: str) -> list[str]:
    """Return added-line source from a unified diff (no +++ / hunk headers)."""
    lines: list[str] = []
    for line in patch.splitlines():
        if line.startswith("+++"):
            continue
        if line.startswith("+"):
            lines.append(line[1:])
    return lines


_PY_IMPORT_RE = re.compile(
    r"^\s*(?:import|from)\s+([\w.]+)",
    re.MULTILINE,
)


def _extract_python_imports(patch: str) -> list[str]:
    """Extract module names from added lines; ast.parse first, regex fallback."""
    added = _added_lines(patch)
    if not added:
        return []

    source = "\n".join(added)

    try:
        tree = ast.parse(source, mode="exec")
        modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                prefix = "." * (node.level or 0)
                if node.module:
                    modules.append(prefix + node.module)
                elif node.level and node.level > 0:
                    for alias in node.names:
                        modules.append(prefix + alias.name)
        return modules
    except SyntaxError:
        pass
    except Exception:  # noqa: BLE001
        pass

    # Drop comment lines so prose like `# import foo` does not pollute the graph.
    non_comment = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    return _PY_IMPORT_RE.findall(non_comment)


_JS_FROM_RE = re.compile(
    r"""(?:import|export)\s+(?:[\w*{},\s]+\s+from\s+)?['"]([^'"]+)['"]""",
    re.MULTILINE,
)
_JS_REQUIRE_RE = re.compile(
    r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""",
    re.MULTILINE,
)
_JS_DYNAMIC_RE = re.compile(
    r"""import\s*\(\s*['"]([^'"]+)['"]\s*\)""",
    re.MULTILINE,
)


def _extract_js_imports(patch: str) -> list[str]:
    """Extract ES module / CommonJS specifiers from added JS/TS lines."""
    added = _added_lines(patch)
    if not added:
        return []

    source = "\n".join(added)
    specifiers: list[str] = []
    specifiers.extend(_JS_FROM_RE.findall(source))
    specifiers.extend(_JS_REQUIRE_RE.findall(source))
    specifiers.extend(_JS_DYNAMIC_RE.findall(source))
    return specifiers


def extract_imports(path: str, patch: str | None) -> list[str]:
    """Return raw import/specifier strings from added lines; empty on unknown language."""
    if not patch:
        return []

    ext = _ext(path)

    try:
        if ext in _PY_EXTENSIONS:
            return _extract_python_imports(patch)
        if ext in _JS_EXTENSIONS:
            return _extract_js_imports(patch)
        return []
    except Exception:  # noqa: BLE001
        return []


_JS_EXTENSIONS_FOR_RESOLVE = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")


def _resolve_python_specifier(
    specifier: str,
    importer_path: str,
) -> list[str]:
    """Candidate local paths for a Python module or relative specifier."""
    candidates: list[str] = []
    importer_dir = os.path.dirname(importer_path)

    if specifier.startswith("."):
        level = len(specifier) - len(specifier.lstrip("."))
        module_part = specifier.lstrip(".")

        base = importer_dir
        for _ in range(level - 1):
            base = os.path.dirname(base) or "."

        if module_part:
            rel_path = module_part.replace(".", "/")
            candidates.append(os.path.normpath(os.path.join(base, rel_path + ".py")))
            candidates.append(os.path.normpath(os.path.join(base, rel_path, "__init__.py")))
    else:
        # Absolute/package imports (e.g. "os", "pydantic") are not local edges.
        # Resolving them to local paths would false-link unrelated files that
        # happen to share a name (e.g. a local os.py).
        return []

    return candidates


def _resolve_js_specifier(
    specifier: str,
    importer_path: str,
) -> list[str]:
    """Candidate local paths for a relative JS/TS specifier."""
    if not (specifier.startswith("./") or specifier.startswith("../")):
        return []

    importer_dir = os.path.dirname(importer_path)
    base = os.path.normpath(os.path.join(importer_dir, specifier))

    candidates: list[str] = []
    if os.path.splitext(base)[1].lower() in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
        candidates.append(base)
    else:
        for ext in _JS_EXTENSIONS_FOR_RESOLVE:
            candidates.append(base + ext)
        for ext in _JS_EXTENSIONS_FOR_RESOLVE:
            candidates.append(os.path.join(base, "index" + ext))

    return candidates


def referenced_paths(path: str, patch: str | None) -> set[str]:
    """Resolve import specifiers to plausible local paths; excludes *path* itself.

    Callers must intersect the result with their known changed-file set.
    """
    if not patch:
        return set()

    try:
        specifiers = extract_imports(path, patch)
        if not specifiers:
            return set()

        ext = _ext(path)
        result: set[str] = set()

        for spec in specifiers:
            try:
                if ext in _PY_EXTENSIONS:
                    candidates = _resolve_python_specifier(spec, path)
                elif ext in _JS_EXTENSIONS:
                    candidates = _resolve_js_specifier(spec, path)
                else:
                    candidates = []

                for candidate in candidates:
                    # Normalize to POSIX before checking traversal — diff paths are always '/'.
                    normalized = candidate.replace("\\", "/")
                    parts = normalized.split("/")
                    if not normalized.startswith("/") and ".." not in parts:
                        result.add(candidate)
            except Exception:  # noqa: BLE001
                pass

        self_norm = path.replace("\\", "/")
        result = {c for c in result if c.replace("\\", "/") != self_norm}

        return result

    except Exception:  # noqa: BLE001
        return set()
