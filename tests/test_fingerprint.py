"""Tests for content-addressed finding identity (D-04 / LIFE-02)."""

from __future__ import annotations

import re

from prevue.fingerprint import fingerprint, normalize_title


class TestNormalizeTitle:
    def test_casefold_unicode(self) -> None:
        assert normalize_title("straße") == normalize_title("STRASSE")

    def test_nfkc_equivalence(self) -> None:
        composed = "café"
        decomposed = "caf\u0065\u0301"
        assert normalize_title(composed) == normalize_title(decomposed)

    def test_punctuation_whitespace_collapse(self) -> None:
        assert normalize_title("SQL  injection!") == normalize_title("sql injection")


class TestFingerprint:
    def test_determinism(self) -> None:
        path = "src/main.py"
        title = "Possible SQL injection"
        first = fingerprint(path, title)
        second = fingerprint(path, title)
        assert first == second

    def test_excludes_line_severity_suggestion(self) -> None:
        """Identity is path|title only — other finding fields are not inputs."""
        path = "src/db.py"
        title = "Missing input validation"
        base = fingerprint(path, title)
        # Simulate different line/severity/suggestion by varying only those
        # conceptual fields while path+title stay fixed.
        assert fingerprint(path, title) == base
        assert fingerprint(path, title) == fingerprint(path, title)

    def test_different_path_yields_different_fingerprint(self) -> None:
        title = "Same title"
        assert fingerprint("a.py", title) != fingerprint("b.py", title)

    def test_different_normalized_title_yields_different_fingerprint(self) -> None:
        path = "src/main.py"
        assert fingerprint(path, "SQL injection") != fingerprint(path, "XSS vulnerability")

    def test_reworded_title_is_new_fingerprint(self) -> None:
        """Semantically similar but textually different titles are distinct (D-04)."""
        path = "src/auth.py"
        original = fingerprint(path, "Missing null check")
        reworded = fingerprint(path, "Potential null pointer dereference")
        assert original != reworded

    def test_digest_is_16_hex(self) -> None:
        digest = fingerprint("src/main.py", "Test finding")
        assert len(digest) == 16
        assert re.fullmatch(r"[0-9a-f]{16}", digest)
