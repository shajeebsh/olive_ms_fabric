import os
import pytest

from src.secrets import LocalSecrets, get_secrets


class TestLocalSecrets:

    def setup_method(self):
        self.env_key = "test_scope_test_key"
        if self.env_key in os.environ:
            del os.environ[self.env_key]

    def test_get_returns_env_var(self):
        os.environ["test_scope_test_key"] = "secret_value"
        secrets = LocalSecrets()
        assert secrets.get("test_scope", "test_key") == "secret_value"

    def test_get_missing_raises_key_error(self):
        secrets = LocalSecrets()
        with pytest.raises(KeyError, match="Secret not found"):
            secrets.get("missing_scope", "missing_key")

    def test_get_with_hyphens(self):
        os.environ["my-scope_my-key"] = "val"
        secrets = LocalSecrets()
        assert secrets.get("my-scope", "my-key") == "val"

    def test_get_secrets_returns_local(self):
        fs = get_secrets()
        assert isinstance(fs, LocalSecrets)
