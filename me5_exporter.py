#!/usr/bin/env python3
"""Prometheus exporter for Dell PowerVault ME5 over SSH/XML CLI."""

from __future__ import annotations

import logging
import os
import signal
import socket
import threading
import time
from collections.abc import Callable

import paramiko
from prometheus_client import start_http_server

from collector.ssh import ME5Client
from config import Config, env_bool
from collectors import alerts, controllers, disks, events, pools, ports, system, versions, volumes
from metrics import (
    ALERTS_BY_SEVERITY,
    COLLECTION_DURATION,
    COLLECTION_ERRORS,
    COLLECTOR_DURATION,
    COLLECTOR_ERRORS,
    COLLECTOR_UP,
    EXPORTER_UP,
    LAST_SUCCESS,
)

LOG = logging.getLogger("me5-exporter")
STOP = threading.Event()

Collector = Callable[[ME5Client], None]

COLLECTORS: dict[str, tuple[str, Collector]] = {
    "system": ("ENABLE_SYSTEM", system.collect),
    "controllers": ("ENABLE_CONTROLLERS", controllers.collect),
    "disks": ("ENABLE_DISKS", disks.collect),
    "pools": ("ENABLE_POOLS", pools.collect),
    "volumes": ("ENABLE_VOLUMES", volumes.collect),
    "alerts": ("ENABLE_ALERTS", alerts.collect),
    "events": ("ENABLE_EVENTS", events.collect),
    "ports": ("ENABLE_PORTS", ports.collect),
    "versions": ("ENABLE_VERSIONS", versions.collect),
}


def initialize_metrics() -> None:
    EXPORTER_UP.set(0)
    COLLECTION_DURATION.set(0)
    LAST_SUCCESS.set(0)
    for name in COLLECTORS:
        COLLECTOR_UP.labels(name).set(0)
        COLLECTOR_DURATION.labels(name).set(0)
        COLLECTOR_ERRORS.labels(name)
    for severity in ("critical", "error", "warning", "informational", "unknown"):
        ALERTS_BY_SEVERITY.labels(severity).set(0)


def run_cycle(config: Config) -> None:
    started = time.monotonic()
    cycle_ok = True
    ssh_ok = False
    try:
        with ME5Client(config) as client:
            ssh_ok = True
            for name, (env_name, collector) in COLLECTORS.items():
                if not env_bool(env_name, True):
                    continue
                collector_started = time.monotonic()
                try:
                    collector(client)
                    COLLECTOR_UP.labels(name).set(1)
                except Exception:
                    cycle_ok = False
                    COLLECTOR_UP.labels(name).set(0)
                    COLLECTOR_ERRORS.labels(name).inc()
                    LOG.exception("Collector %s failed", name)
                finally:
                    COLLECTOR_DURATION.labels(name).set(time.monotonic() - collector_started)
    except (paramiko.SSHException, socket.error, TimeoutError, OSError):
        cycle_ok = False
        LOG.exception("SSH collection failed")
    except Exception:
        cycle_ok = False
        LOG.exception("Unexpected collection failure")
    finally:
        EXPORTER_UP.set(1 if ssh_ok else 0)
        COLLECTION_DURATION.set(time.monotonic() - started)
        if cycle_ok:
            LAST_SUCCESS.set(time.time())
        else:
            COLLECTION_ERRORS.inc()


def handle_signal(signum: int, frame: object) -> None:
    LOG.info("Received signal %s, stopping", signum)
    STOP.set()


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = Config.from_env()
    initialize_metrics()
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    start_http_server(config.exporter_port)
    LOG.info(
        "Exporter listening on :%d; target=%s:%d interval=%ds",
        config.exporter_port,
        config.host,
        config.port,
        config.interval,
    )
    while not STOP.is_set():
        run_cycle(config)
        STOP.wait(config.interval)


if __name__ == "__main__":
    main()
