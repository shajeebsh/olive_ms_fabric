from __future__ import annotations

import importlib
import pkgutil

from src.connectors.registry import ConnectorRegistry


def register_all(registry: ConnectorRegistry, config: dict | None = None):
    import src.connectors as pkg
    for _finder, name, _ispkg in pkgutil.walk_packages(
        pkg.__path__, prefix=pkg.__name__ + "."
    ):
        mod = importlib.import_module(name)
        if hasattr(mod, "register_connectors"):
            mod.register_connectors(registry, config)


__all__ = ["register_all"]
