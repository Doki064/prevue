"""Engine name → adapter registry with fail-closed selection (D-03/D-04/ENGN-10).

The registry auto-populates by iterating CLI_ENGINE_SPECS — adding a CLI engine
is one CliEngineSpec data entry in spec.py; no manual import+dict edit here (D-01).

API siblings (future): key on name + store a factory; CliEngineAdapter is the
CLI-family factory. An ApiEngineAdapter can be registered without going through
CliEngineSpec (D-02). Do not build it here — just keep the name→factory design.
"""

from __future__ import annotations

from prevue.engines.cli_adapter import CliEngineAdapter
from prevue.engines.spec import CLI_ENGINE_SPECS

DEFAULT_ENGINE = "copilot-cli"

# name → spec (public symbol; tests import ENGINES)
# Downstream code calls get_adapter(name) which returns CliEngineAdapter(spec).
ENGINES: dict[str, object] = {spec.name: spec for spec in CLI_ENGINE_SPECS}


class UnknownEngineError(ValueError):
    """Raised when PREVUE_ENGINE names an unregistered adapter."""


class NonFunctionalEngineError(ValueError):
    """Raised when a registered non-functional engine is selected for review."""


def get_adapter(name: str) -> CliEngineAdapter:
    """Resolve a CliEngineAdapter for the given engine name.

    Raises UnknownEngineError for unregistered names (fail-closed, D-04).
    """
    spec = ENGINES.get(name)
    if spec is None:
        valid = ", ".join(sorted(ENGINES))
        raise UnknownEngineError(f"Unknown PREVUE_ENGINE {name!r}; valid engines: {valid}")
    return CliEngineAdapter(spec)  # type: ignore[arg-type]


def require_functional_adapter(name: str) -> CliEngineAdapter:
    """Resolve an adapter that can run reviews (excludes non-functional specs).

    Raises NonFunctionalEngineError if the spec has functional=False.
    The mechanism is kept for future API siblings/skeletons (D-02/D-03).
    """
    spec = ENGINES.get(name)
    if spec is None:
        valid = ", ".join(sorted(ENGINES))
        raise UnknownEngineError(f"Unknown PREVUE_ENGINE {name!r}; valid engines: {valid}")
    # spec is a CliEngineSpec; check functional flag (D-03)
    from prevue.engines.spec import CliEngineSpec  # local import avoids any re-export confusion

    if isinstance(spec, CliEngineSpec) and not spec.functional:
        functional = ", ".join(
            n for n, s in ENGINES.items() if not isinstance(s, CliEngineSpec) or s.functional
        )
        raise NonFunctionalEngineError(
            f"Engine {name!r} is registered but not yet functional; choose one of: {functional}"
        )
    return CliEngineAdapter(spec)  # type: ignore[arg-type]
