"""RED scaffold — import scan unit tests (D-06, Plan 09-03).

These tests import symbols from prevue.importscan, which does not exist yet.
They MUST FAIL with ImportError/ModuleNotFoundError until Plan 09-03 implements the module.

NO pytest.importorskip or @pytest.mark.skip — RED state is intentional.
"""

from __future__ import annotations

try:
    from prevue.importscan import extract_imports, referenced_paths
except ImportError as _import_err:
    _MISSING = _import_err
    extract_imports = None  # type: ignore[assignment]
    referenced_paths = None  # type: ignore[assignment]
else:
    _MISSING = None

import pytest


def _require_module() -> None:
    if _MISSING is not None:
        pytest.fail(f"prevue.importscan not yet implemented (Plan 09-03): {_MISSING}")


# ---------------------------------------------------------------------------
# extract_imports tests
# ---------------------------------------------------------------------------


class TestExtractImports:
    def test_python_stdlib_import_extracted(self) -> None:
        """extract_imports returns a stdlib import from a Python diff patch."""
        _require_module()
        patch = "+import os\n+import sys\n-import os.path\n"
        imports = extract_imports("src/utils.py", patch)
        assert isinstance(imports, (list, set, frozenset)), (
            "extract_imports must return a list or set"
        )
        # At least one of os or sys must be found
        assert any("os" in imp or "sys" in imp for imp in imports), (
            f"Expected os/sys import, got: {list(imports)}"
        )

    def test_python_from_import_extracted(self) -> None:
        """from X import Y statement is captured in Python file patch."""
        _require_module()
        patch = "+from prevue.models import Finding\n+from prevue.gate import ReviewConfig\n"
        imports = extract_imports("src/review.py", patch)
        assert any("prevue" in imp for imp in imports), (
            f"Expected prevue imports, got: {list(imports)}"
        )

    def test_js_import_statement_extracted(self) -> None:
        """ES module import statement is captured from JS/TS file patch."""
        _require_module()
        patch = "+import React from 'react';\n+import { useState } from 'react';\n"
        imports = extract_imports("src/App.tsx", patch)
        assert isinstance(imports, (list, set, frozenset)), (
            "extract_imports must return a list or set"
        )
        assert any("react" in imp.lower() for imp in imports), (
            f"Expected react import, got: {list(imports)}"
        )

    def test_js_require_statement_extracted(self) -> None:
        """CommonJS require() call is captured from JS file patch."""
        _require_module()
        patch = "+const express = require('express');\n+const path = require('path');\n"
        imports = extract_imports("src/server.js", patch)
        assert any("express" in imp.lower() for imp in imports), (
            f"Expected express require, got: {list(imports)}"
        )

    def test_removed_lines_not_extracted(self) -> None:
        """Lines removed (prefixed with -) should not be treated as new imports."""
        _require_module()
        # Only a removed import line — nothing added
        patch = "-import removed_module\n"
        imports = extract_imports("src/old.py", patch)
        assert not any("removed_module" in imp for imp in imports), (
            "Removed import lines must not be included in results"
        )

    def test_empty_patch_returns_empty(self) -> None:
        """Empty patch produces no imports."""
        _require_module()
        result = extract_imports("src/file.py", "")
        assert len(result) == 0, f"Expected no imports from empty patch, got: {result}"

    def test_unparseable_content_degrades_gracefully(self) -> None:
        """Syntactically invalid or binary content does not raise; returns empty."""
        _require_module()
        malformed = "+this is not valid python syntax!!! @@@\x00\x01\xff"
        try:
            result = extract_imports("src/weird.py", malformed)
            # Should degrade to empty or partial — must not raise
            assert isinstance(result, (list, set, frozenset)), (
                "extract_imports must return a collection even on bad input"
            )
        except Exception as exc:
            pytest.fail(f"extract_imports must not raise on unparseable content, raised: {exc}")


# ---------------------------------------------------------------------------
# referenced_paths tests
# ---------------------------------------------------------------------------


class TestReferencedPaths:
    def test_relative_import_maps_to_path(self) -> None:
        """A relative import in a Python file maps to a likely path."""
        _require_module()
        patch = "+from .utils import helper\n"
        paths = referenced_paths("src/api/users.py", patch)
        assert isinstance(paths, (list, set, frozenset)), (
            "referenced_paths must return a collection"
        )
        # Relative .utils from src/api/users.py → src/api/utils.py (or similar)
        assert any("utils" in p for p in paths), (
            f"Expected utils path reference, got: {list(paths)}"
        )

    def test_js_relative_import_maps_to_path(self) -> None:
        """A relative JS import resolves to a likely file path."""
        _require_module()
        patch = "+import { Button } from './components/Button';\n"
        paths = referenced_paths("src/pages/Home.tsx", patch)
        assert isinstance(paths, (list, set, frozenset)), (
            "referenced_paths must return a collection"
        )
        assert any("Button" in p or "button" in p.lower() for p in paths), (
            f"Expected Button path, got: {list(paths)}"
        )

    def test_absolute_package_import_not_a_local_path(self) -> None:
        """Non-relative imports (packages/stdlib) do not yield local file paths."""
        _require_module()
        patch = "+import os\n+import sys\n+import pydantic\n"
        paths = referenced_paths("src/utils.py", patch)
        # os/sys/pydantic are not local files — result may be empty or very small
        for p in paths:
            assert not p.startswith("/"), f"Absolute paths should not appear in results: {p}"

    def test_empty_patch_returns_empty(self) -> None:
        """Empty patch produces no referenced paths."""
        _require_module()
        result = referenced_paths("src/file.py", "")
        assert len(result) == 0, f"Expected no paths from empty patch, got: {result}"

    def test_unparseable_content_degrades_gracefully(self) -> None:
        """Syntactically invalid content does not raise; returns empty collection."""
        _require_module()
        malformed = "+!!!not valid code at all ###\x00\x01\xff"
        try:
            result = referenced_paths("src/weird.py", malformed)
            assert isinstance(result, (list, set, frozenset)), (
                "referenced_paths must return a collection even on bad input"
            )
        except Exception as exc:
            pytest.fail(f"referenced_paths must not raise on unparseable content, raised: {exc}")
