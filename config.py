"""Runtime configuration for the ME5 exporter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    username: str
    password: str
    exporter_port: int
    interval: int
    connect_timeout: int
    banner_timeout: int
    auth_timeout: int
    command_timeout: int
    known_hosts: Path

    @classmethod
    def from_env(cls) -> "Config":
        required = ["ME5_HOST", "ME5_USER", "ME5_PASSWORD"]
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
        return cls(
            host=os.environ["ME5_HOST"],
            port=int(os.getenv("ME5_PORT", "22")),
            username=os.environ["ME5_USER"],
            password=os.environ["ME5_PASSWORD"],
            exporter_port=int(os.getenv("EXPORTER_PORT", "9824")),
            interval=int(os.getenv("SCRAPE_INTERVAL", "60")),
            connect_timeout=int(os.getenv("SSH_CONNECT_TIMEOUT", "30")),
            banner_timeout=int(os.getenv("SSH_BANNER_TIMEOUT", "60")),
            auth_timeout=int(os.getenv("SSH_AUTH_TIMEOUT", "30")),
            command_timeout=int(os.getenv("SSH_COMMAND_TIMEOUT", "90")),
            known_hosts=Path(os.getenv("KNOWN_HOSTS_FILE", "/app/.ssh/known_hosts")),
        )
