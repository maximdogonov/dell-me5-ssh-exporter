#!/usr/bin/env python3
"""Prometheus exporter for Dell PowerVault ME5 over SSH/XML CLI."""

from __future__ import annotations

import logging
import os
import re
import signal
import socket
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import paramiko
from prometheus_client import Counter, Gauge, Info, start_http_server

LOG = logging.getLogger("me5-exporter")
STOP = threading.Event()


def env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def first(props: dict[str, str], *names: str, default: str = "") -> str:
    for name in names:
        value = props.get(name, "").strip()
        if value:
            return value
    return default


def number(value: str, default: float = 0.0) -> float:
    if not value:
        return default
    match = re.search(r"[-+]?\d+(?:\.\d+)?", value.replace(",", ""))
    return float(match.group(0)) if match else default


def bytes_from_value(value: str, unit_hint: str = "") -> float:
    """Parse sizes such as '1.2TB', '1024 GB', or plain values with a unit hint."""
    if not value:
        return 0.0
    match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*([kmgtpe]?i?b)?", value, re.I)
    if not match:
        return 0.0
    amount = float(match.group(1))
    unit = (match.group(2) or unit_hint or "B").upper()
    powers = {
        "B": 0,
        "KB": 1,
        "KIB": 1,
        "MB": 2,
        "MIB": 2,
        "GB": 3,
        "GIB": 3,
        "TB": 4,
        "TIB": 4,
        "PB": 5,
        "PIB": 5,
        "EB": 6,
        "EIB": 6,
    }
    return amount * (1024 ** powers.get(unit, 0))


def state_ok(value: str, accepted: Iterable[str] = ("ok", "operational", "up", "online", "available", "ready")) -> float:
    return 1.0 if value.strip().lower() in set(accepted) else 0.0


def extract_xml(text: str) -> str:
    start = text.find("<?xml")
    if start < 0:
        start = text.find("<RESPONSE")
    end_tag = "</RESPONSE>"
    end = text.rfind(end_tag)
    if start < 0 or end < 0:
        raise ValueError("ME5 XML RESPONSE not found")
    return text[start : end + len(end_tag)]


def parse_xml(text: str) -> ET.Element:
    return ET.fromstring(extract_xml(text))


def properties(obj: ET.Element) -> dict[str, str]:
    return {
        prop.get("name", ""): (prop.text or "").strip()
        for prop in obj.findall("PROPERTY")
    }


def objects(root: ET.Element, basetype: str | None = None, name: str | None = None):
    for obj in root.findall("OBJECT"):
        if basetype is not None and obj.get("basetype") != basetype:
            continue
        if name is not None and obj.get("name") != name:
            continue
        yield obj, properties(obj)


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


# Exporter/self metrics
EXPORTER_UP = Gauge("dell_me_exporter_up", "1 when the last collection cycle completed with an SSH connection")
COLLECTION_DURATION = Gauge("dell_me_collection_duration_seconds", "Duration of the last collection cycle")
LAST_SUCCESS = Gauge("dell_me_last_success_unixtime", "Unix timestamp of the last fully successful collection cycle")
COLLECTION_ERRORS = Counter("dell_me_collection_errors", "Total failed collection cycles")
COLLECTOR_UP = Gauge("dell_me_collector_up", "1 when the collector command and parser succeeded", ["collector"])
COLLECTOR_DURATION = Gauge("dell_me_collector_duration_seconds", "Collector execution duration", ["collector"])
COLLECTOR_ERRORS = Counter("dell_me_collector_errors", "Collector failures", ["collector"])

# System
SYSTEM_HEALTH = Gauge("dell_me_system_health", "System health: 1=OK, 0=not OK or unknown")
SYSTEM_INFO = Info("dell_me_system", "Static ME system information")
ACTIVE_ALERTS = Gauge("dell_me_active_alerts", "Number of active alerts")
ALERTS_BY_SEVERITY = Gauge("dell_me_alerts", "Number of active alerts by severity", ["severity"])

# Controllers
CONTROLLER_HEALTH = Gauge("dell_me_controller_health", "Controller health: 1=OK", ["controller"])
CONTROLLER_OPERATIONAL = Gauge("dell_me_controller_operational", "Controller status is Operational", ["controller"])
CONTROLLER_FAILED_OVER = Gauge("dell_me_controller_failed_over", "Controller is currently failed over", ["controller"])
CONTROLLER_CACHE_LOCK = Gauge("dell_me_controller_cache_lock", "Controller cache lock enabled", ["controller"])
CONTROLLER_WRITE_BACK = Gauge("dell_me_controller_write_back", "Controller cache write policy is write-back", ["controller"])
CONTROLLER_MEMORY = Gauge("dell_me_controller_memory_bytes", "Controller system memory", ["controller"])
CONTROLLER_CACHE = Gauge("dell_me_controller_cache_bytes", "Controller cache memory", ["controller"])
CONTROLLER_CPU_MHZ = Gauge("dell_me_controller_cpu_mhz", "Controller CPU clock in MHz", ["controller"])
CONTROLLER_REDUNDANT = Gauge("dell_me_controller_redundant", "Controller redundancy status is Redundant", ["controller"])
CONTROLLER_INFO = Info("dell_me_controller", "Static controller information", ["controller"])
MGMT_LINK_UP = Gauge("dell_me_management_link_up", "Management link is up", ["controller"])
MGMT_HEALTH = Gauge("dell_me_management_health", "Management interface health is OK", ["controller"])
HOST_PORT_UP = Gauge("dell_me_host_port_up", "Host port link status is Up", ["controller", "port", "media"])
HOST_PORT_HEALTH = Gauge("dell_me_host_port_health", "Host port health is OK", ["controller", "port", "media"])
HOST_PORT_SPEED_GBPS = Gauge("dell_me_host_port_speed_gbps", "Host port negotiated speed in Gbit/s", ["controller", "port", "media"])

# Disks
DISK_HEALTH = Gauge("dell_me_disk_health", "Disk health is OK", ["disk", "enclosure", "slot"])
DISK_ONLINE = Gauge("dell_me_disk_online", "Disk state is online/available", ["disk", "enclosure", "slot"])
DISK_SIZE = Gauge("dell_me_disk_size_bytes", "Disk raw size", ["disk", "enclosure", "slot"])
DISK_TEMP = Gauge("dell_me_disk_temperature_celsius", "Disk temperature", ["disk", "enclosure", "slot"])
DISK_RPM = Gauge("dell_me_disk_rpm", "Disk rotational speed; zero for SSD", ["disk", "enclosure", "slot"])
DISK_LIFE = Gauge("dell_me_disk_life_remaining_percent", "SSD life remaining percent", ["disk", "enclosure", "slot"])
DISK_INFO = Info("dell_me_disk", "Static disk information", ["disk", "enclosure", "slot"])

# Pools
POOL_HEALTH = Gauge("dell_me_pool_health", "Pool health is OK", ["pool"])
POOL_SIZE = Gauge("dell_me_pool_size_bytes", "Pool total size", ["pool"])
POOL_USED = Gauge("dell_me_pool_used_bytes", "Pool used capacity", ["pool"])
POOL_FREE = Gauge("dell_me_pool_free_bytes", "Pool free capacity", ["pool"])
POOL_USED_PERCENT = Gauge("dell_me_pool_used_percent", "Pool used capacity percent", ["pool"])

# Volumes
VOLUME_HEALTH = Gauge("dell_me_volume_health", "Volume health is OK", ["volume"])
VOLUME_ONLINE = Gauge("dell_me_volume_online", "Volume is online/available", ["volume"])
VOLUME_SIZE = Gauge("dell_me_volume_size_bytes", "Volume size", ["volume"])
VOLUME_INFO = Info("dell_me_volume", "Static volume information", ["volume"])


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


def response_success(root: ET.Element) -> bool:
    for _, props in objects(root, "status", "status"):
        return first(props, "response-type").lower() == "success" and first(props, "return-code", default="0") == "0"
    return True


def collect_system(client: ME5Client) -> None:
    root = parse_xml(client.command("show system"))
    if not response_success(root):
        raise ValueError("show system returned failure")
    candidates = list(objects(root))
    chosen = None
    for obj, props in candidates:
        if obj.get("basetype") in {"system", "systems", "system-information"}:
            chosen = props
            break
    if chosen is None:
        for _, props in candidates:
            if "health" in props and any(k in props for k in ("system-name", "product-id", "model")):
                chosen = props
                break
    if chosen is None:
        raise ValueError("System object not found")
    health = first(chosen, "health", "status")
    SYSTEM_HEALTH.set(state_ok(health))
    SYSTEM_INFO.info({
        "name": first(chosen, "system-name", "name"),
        "model": first(chosen, "model", "product-id", "product-brand"),
        "serial_number": first(chosen, "serial-number", "midplane-serial-number"),
        "firmware": first(chosen, "firmware-version", "bundle-version", "sc-fw"),
    })


def collect_controllers(client: ME5Client) -> None:
    root = parse_xml(client.command("show controllers"))
    if not response_success(root):
        raise ValueError("show controllers returned failure")
    found: set[str] = set()
    for _, props in objects(root, "controllers", "controller"):
        controller = first(props, "controller-id").upper()
        if controller not in {"A", "B"}:
            continue
        found.add(controller)
        health = first(props, "health")
        status = first(props, "status")
        CONTROLLER_HEALTH.labels(controller).set(state_ok(health, ("ok",)))
        CONTROLLER_OPERATIONAL.labels(controller).set(state_ok(status, ("operational",)))
        CONTROLLER_FAILED_OVER.labels(controller).set(1 if first(props, "failed-over").lower() == "yes" else 0)
        CONTROLLER_CACHE_LOCK.labels(controller).set(1 if first(props, "cache-lock").lower() == "yes" else 0)
        CONTROLLER_WRITE_BACK.labels(controller).set(1 if first(props, "write-policy").lower() == "write-back" else 0)
        CONTROLLER_MEMORY.labels(controller).set(bytes_from_value(first(props, "system-memory-size"), "MB"))
        CONTROLLER_CACHE.labels(controller).set(bytes_from_value(first(props, "cache-memory-size"), "MB"))
        CONTROLLER_CPU_MHZ.labels(controller).set(number(first(props, "sc-cpu-speed")))
        CONTROLLER_REDUNDANT.labels(controller).set(1 if first(props, "redundancy-status").lower() == "redundant" else 0)
        CONTROLLER_INFO.labels(controller).info({
            "serial_number": first(props, "serial-number"),
            "model": first(props, "model"),
            "firmware": first(props, "sc-fw"),
            "hardware_version": first(props, "hardware-version"),
            "ip_address": first(props, "ip-address"),
            "position": first(props, "position"),
        })
    for controller in {"A", "B"} - found:
        CONTROLLER_HEALTH.labels(controller).set(0)
        CONTROLLER_OPERATIONAL.labels(controller).set(0)

    for obj, props in objects(root):
        bt = obj.get("basetype")
        if bt == "network-parameters":
            name = (obj.get("name") or "").lower()
            controller = "A" if name.endswith("-a") else "B" if name.endswith("-b") else ""
            if controller:
                MGMT_LINK_UP.labels(controller).set(1 if number(first(props, "link-speed")) > 0 else 0)
                MGMT_HEALTH.labels(controller).set(state_ok(first(props, "health"), ("ok",)))
        elif bt == "port":
            controller = first(props, "controller").upper()
            port = first(props, "port", "durable-id")
            media = first(props, "media", "port-type", default="unknown")
            if controller and port:
                HOST_PORT_UP.labels(controller, port, media).set(state_ok(first(props, "status"), ("up",)))
                HOST_PORT_HEALTH.labels(controller, port, media).set(state_ok(first(props, "health"), ("ok",)))
                HOST_PORT_SPEED_GBPS.labels(controller, port, media).set(number(first(props, "actual-speed")))


def collect_disks(client: ME5Client) -> None:
    root = parse_xml(client.command("show disks"))
    if not response_success(root):
        raise ValueError("show disks returned failure")
    count = 0
    for obj, props in objects(root):
        if obj.get("basetype") not in {"drive", "drives", "disk", "disks"}:
            continue
        disk = first(props, "durable-id", "disk", "location", "serial-number", default=f"disk-{count}")
        enclosure = first(props, "enclosure-id", "enclosure", default="unknown")
        slot = first(props, "slot", "slot-number", default="unknown")
        labels = (disk, enclosure, slot)
        DISK_HEALTH.labels(*labels).set(state_ok(first(props, "health"), ("ok",)))
        DISK_ONLINE.labels(*labels).set(state_ok(first(props, "status", "state")))
        size_value = first(props, "size", "raw-size", "total-size", "capacity")
        DISK_SIZE.labels(*labels).set(bytes_from_value(size_value))
        DISK_TEMP.labels(*labels).set(number(first(props, "temperature", "temperature-celsius")))
        DISK_RPM.labels(*labels).set(number(first(props, "rpm", "rotation-speed")))
        DISK_LIFE.labels(*labels).set(number(first(props, "ssd-life-left", "life-remaining", "remaining-life")))
        DISK_INFO.labels(*labels).info({
            "serial_number": first(props, "serial-number"),
            "vendor": first(props, "vendor"),
            "model": first(props, "model"),
            "revision": first(props, "revision", "firmware-revision"),
            "type": first(props, "type", "drive-type", "media"),
        })
        count += 1
    if count == 0:
        raise ValueError("No disk objects recognized in show disks XML")


def collect_pools(client: ME5Client) -> None:
    root = parse_xml(client.command("show pools"))
    if not response_success(root):
        raise ValueError("show pools returned failure")
    count = 0
    for obj, props in objects(root):
        if obj.get("basetype") not in {"pool", "pools", "storage-pool", "storage-pools"}:
            continue
        pool = first(props, "name", "pool", "serial-number", "durable-id", default=f"pool-{count}")
        total = bytes_from_value(first(props, "total-size", "size", "capacity"))
        free = bytes_from_value(first(props, "free-size", "available-size", "available", "free"))
        used = bytes_from_value(first(props, "used-size", "allocated-size", "used"))
        if total and not used and free:
            used = max(total - free, 0)
        if total and not free and used:
            free = max(total - used, 0)
        pct = number(first(props, "percent-used", "used-percent"), (used / total * 100) if total else 0)
        POOL_HEALTH.labels(pool).set(state_ok(first(props, "health", "status")))
        POOL_SIZE.labels(pool).set(total)
        POOL_USED.labels(pool).set(used)
        POOL_FREE.labels(pool).set(free)
        POOL_USED_PERCENT.labels(pool).set(pct)
        count += 1
    if count == 0:
        raise ValueError("No pool objects recognized in show pools XML")


def collect_volumes(client: ME5Client) -> None:
    root = parse_xml(client.command("show volumes"))
    if not response_success(root):
        raise ValueError("show volumes returned failure")
    count = 0
    for obj, props in objects(root):
        if obj.get("basetype") not in {"volume", "volumes", "virtual-volume", "virtual-volumes"}:
            continue
        volume = first(props, "volume-name", "name", "durable-id", "serial-number", default=f"volume-{count}")
        VOLUME_HEALTH.labels(volume).set(state_ok(first(props, "health"), ("ok",)))
        VOLUME_ONLINE.labels(volume).set(state_ok(first(props, "status", "state")))
        VOLUME_SIZE.labels(volume).set(bytes_from_value(first(props, "size", "total-size", "capacity")))
        VOLUME_INFO.labels(volume).info({
            "serial_number": first(props, "serial-number"),
            "pool": first(props, "pool", "pool-name", "storage-pool-name"),
            "raid_type": first(props, "raid-type"),
            "type": first(props, "type", "volume-type"),
        })
        count += 1
    if count == 0:
        raise ValueError("No volume objects recognized in show volumes XML")


def collect_alerts(client: ME5Client) -> None:
    root = parse_xml(client.command("show alerts"))
    if not response_success(root):
        raise ValueError("show alerts returned failure")
    counts = {"critical": 0, "error": 0, "warning": 0, "informational": 0, "unknown": 0}
    total = 0
    for obj, props in objects(root):
        bt = obj.get("basetype") or ""
        if "alert" not in bt:
            continue
        severity = first(props, "severity", "level", "priority", default="unknown").lower()
        if severity in {"info", "information"}:
            severity = "informational"
        if severity not in counts:
            severity = "unknown"
        counts[severity] += 1
        total += 1
    ACTIVE_ALERTS.set(total)
    for severity, count in counts.items():
        ALERTS_BY_SEVERITY.labels(severity).set(count)


COLLECTORS = {
    "system": ("ENABLE_SYSTEM", collect_system),
    "controllers": ("ENABLE_CONTROLLERS", collect_controllers),
    "disks": ("ENABLE_DISKS", collect_disks),
    "pools": ("ENABLE_POOLS", collect_pools),
    "volumes": ("ENABLE_VOLUMES", collect_volumes),
    "alerts": ("ENABLE_ALERTS", collect_alerts),
}


def run_cycle(config: Config) -> None:
    started = time.monotonic()
    cycle_ok = True
    try:
        with ME5Client(config) as client:
            EXPORTER_UP.set(1)
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
        EXPORTER_UP.set(0)
        cycle_ok = False
        LOG.exception("SSH collection failed")
    except Exception:
        EXPORTER_UP.set(0)
        cycle_ok = False
        LOG.exception("Unexpected collection failure")
    finally:
        COLLECTION_DURATION.set(time.monotonic() - started)
        if cycle_ok:
            LAST_SUCCESS.set(time.time())
        else:
            COLLECTION_ERRORS.inc()


def handle_signal(signum, frame) -> None:
    LOG.info("Received signal %s, stopping", signum)
    STOP.set()


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = Config.from_env()
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    start_http_server(config.exporter_port)
    LOG.info("Exporter listening on :%d; target=%s:%d interval=%ds", config.exporter_port, config.host, config.port, config.interval)
    while not STOP.is_set():
        run_cycle(config)
        STOP.wait(config.interval)


if __name__ == "__main__":
    main()
