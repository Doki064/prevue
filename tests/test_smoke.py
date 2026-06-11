"""Wave 0 smoke test — ensures pytest collects and the package imports."""


def test_package_imports() -> None:
    import prevue
    import prevue.engines
    import prevue.github

    assert prevue.__version__ == "0.1.0"
