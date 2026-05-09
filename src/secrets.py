from __future__ import annotations

import os
from abc import ABC, abstractmethod


class SecretsProvider(ABC):

    @abstractmethod
    def get(self, scope: str, key: str) -> str:
        ...


class FabricSecrets(SecretsProvider):

    def get(self, scope: str, key: str) -> str:
        from mssparkutils import credentials
        return credentials.getSecret(scope, key)


class LocalSecrets(SecretsProvider):

    def get(self, scope: str, key: str) -> str:
        env_var = f"{scope}_{key}"
        val = os.environ.get(env_var)
        if val is None:
            raise KeyError(
                f"Secret not found. Set environment variable {env_var}"
            )
        return val


def get_secrets() -> SecretsProvider:
    try:
        from mssparkutils import credentials
        return FabricSecrets()
    except (ImportError, NameError):
        return LocalSecrets()
