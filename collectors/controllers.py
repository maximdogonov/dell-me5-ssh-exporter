"""Controller collector."""

from __future__ import annotations

from collector.ssh import ME5Client
from collector.xml import bytes_from_value, first, number, objects, parse_xml, response_success, state_ok
from metrics import (
    CONTROLLER_CACHE,
    CONTROLLER_CACHE_LOCK,
    CONTROLLER_CPU_MHZ,
    CONTROLLER_FAILED_OVER,
    CONTROLLER_HEALTH,
    CONTROLLER_INFO,
    CONTROLLER_MEMORY,
    CONTROLLER_OPERATIONAL,
    CONTROLLER_REDUNDANT,
    CONTROLLER_WRITE_BACK,
)


def collect(client: ME5Client) -> None:
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
