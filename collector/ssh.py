"""SSH client wrapper for Dell ME CLI commands."""

from __future__ import annotations

import logging

import paramiko

from config import Config

LOG = logging.getLogger("me5-exporter")


class ME5Client:
    def __init__(self, config: Config):
        self.config = config
        self.client: paramiko.SSHClient | None = None

    def __enter__(self) -> "ME5Client":
        cfg = self.config
        cfg.known_hosts.parent.mkdir(parents=True, exist_ok=True)
        self.client = paramiko.SSHClient()
        if cfg.known_hosts.exists():
            self.client.load_host_keys(str(cfg.known_hosts))
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(
            hostname=cfg.host,
            port=cfg.port,
            username=cfg.username,
            password=cfg.password,
            look_for_keys=False,
            allow_agent=False,
            timeout=cfg.connect_timeout,
            banner_timeout=cfg.banner_timeout,
            auth_timeout=cfg.auth_timeout,
        )
        self.client.save_host_keys(str(cfg.known_hosts))
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.client:
            self.client.close()

    def command(self, command: str) -> str:
        if not self.client:
            raise RuntimeError("SSH client is not connected")
        _, stdout, stderr = self.client.exec_command(command, timeout=self.config.command_timeout)
        stdout.channel.settimeout(self.config.command_timeout)
        data = stdout.read().decode("utf-8", errors="replace")
        error = stderr.read().decode("utf-8", errors="replace").strip()
        status = stdout.channel.recv_exit_status()
        if status != 0:
            raise RuntimeError(f"Command {command!r} failed with status {status}: {error}")
        if error:
            LOG.debug("Command %s stderr: %s", command, error)
        return data
