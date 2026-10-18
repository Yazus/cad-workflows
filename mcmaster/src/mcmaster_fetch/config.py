"""Credential loading.

Values come from environment variables first, then from a local TOML file
(default ``mcmaster.toml`` in the current directory, which is gitignored).
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("mcmaster.toml")

# config-file key -> environment variable
_FIELDS = {
    "username": "MCMASTER_USERNAME",
    "password": "MCMASTER_PASSWORD",
    "cert": "MCMASTER_CERT",
    "key": "MCMASTER_KEY",
}


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str
    cert: Path
    key: Path | None = None

    @property
    def requests_cert(self) -> str | tuple[str, str]:
        """The value to pass as ``requests``' ``cert=`` argument."""
        if self.key:
            return (str(self.cert), str(self.key))
        return str(self.cert)


def load_credentials(config_path: Path | None = None) -> Credentials:
    path = config_path or Path(os.environ.get("MCMASTER_CONFIG", DEFAULT_CONFIG_PATH))
    file_values: dict = {}
    if path.is_file():
        with path.open("rb") as f:
            file_values = tomllib.load(f).get("mcmaster", {})
    elif config_path is not None:
        raise ConfigError(f"Config file not found: {path}")

    values = {}
    for field, env in _FIELDS.items():
        values[field] = os.environ.get(env) or file_values.get(field)

    missing = [_FIELDS[f] for f in ("username", "password", "cert") if not values[f]]
    if missing:
        raise ConfigError(
            "Missing McMaster-Carr credentials: "
            + ", ".join(missing)
            + f". Set them as environment variables or in {path}."
        )

    cert = Path(values["cert"]).expanduser()
    if not cert.is_file():
        raise ConfigError(f"Client certificate not found: {cert}")
    key = Path(values["key"]).expanduser() if values["key"] else None
    if key and not key.is_file():
        raise ConfigError(f"Client certificate key not found: {key}")
    if cert.suffix.lower() in (".pfx", ".p12"):
        raise ConfigError(
            f"{cert} is a PFX/PKCS#12 file. Convert it to PEM first (see README, "
            "'Convert the certificate')."
        )

    return Credentials(values["username"], values["password"], cert, key)
