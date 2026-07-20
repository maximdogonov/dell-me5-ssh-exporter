"""Host and expansion port collector."""

from __future__ import annotations

import logging
from collections.abc import Callable

from collector.ssh import ME5Client
from collector.xml import first, number, objects, parse_xml, response_success, state_ok
from metrics import (
    EXPANDER_PORT_HEALTH,
    EXPANDER_PORT_SPEED_GBPS,
    EXPANDER_PORT_UP,
    HOST_PORT_HEALTH,
    HOST_PORT_SPEED_GBPS,
    HOST_PORT_UP,
    MGMT_HEALTH,
    MGMT_LINK_UP,
)

LOG = logging.getLogger("me5-exporter")


def _controller_from_props(props: dict[str, str]) -> str:
    controller = first(props, "controller", "controller-id", "controller-module").upper()
    if controller in {"A", "B"}:
        return controller
    durable_id = first(props, "durable-id", "port", "name").upper()
    if durable_id.startswith("A") or "-A" in durable_id:
        return "A"
    if durable_id.startswith("B") or "-B" in durable_id:
        return "B"
    return controller


def _speed_gbps(props: dict[str, str]) -> float:
    value = first(props, "actual-speed", "speed", "link-speed", "configured-speed")
    speed = number(value)
    lowered = value.lower()
    if "mb" in lowered or "mbit" in lowered or "mbps" in lowered:
        return speed / 1000
    return speed


def _collect_response(
    client: ME5Client,
    command: str,
    parser: Callable[[dict[str, str]], bool],
) -> int:
    root = parse_xml(client.command(command))
    if not response_success(root):
        raise ValueError(f"{command} returned failure")
    count = 0
    for _, props in objects(root):
        if parser(props):
            count += 1
    return count


def _collect_host_port(props: dict[str, str]) -> bool:
    controller = _controller_from_props(props)
    port = first(props, "port", "port-id", "durable-id", "name")
    media = first(props, "media", "port-type", "type", default="unknown")
    if controller and port:
        HOST_PORT_UP.labels(controller, port, media).set(state_ok(first(props, "status", "state"), ("up", "online", "connected")))
        HOST_PORT_HEALTH.labels(controller, port, media).set(state_ok(first(props, "health"), ("ok",)))
        HOST_PORT_SPEED_GBPS.labels(controller, port, media).set(_speed_gbps(props))
        return True
    return False


def _collect_expander_port(props: dict[str, str]) -> bool:
    controller = _controller_from_props(props)
    port = first(props, "port", "port-id", "durable-id", "name")
    if controller and port:
        EXPANDER_PORT_UP.labels(controller, port).set(state_ok(first(props, "status", "state"), ("up", "online", "connected")))
        EXPANDER_PORT_HEALTH.labels(controller, port).set(state_ok(first(props, "health"), ("ok",)))
        EXPANDER_PORT_SPEED_GBPS.labels(controller, port).set(_speed_gbps(props))
        return True
    return False


def _collect_management_port(props: dict[str, str]) -> bool:
    name = first(props, "name", "durable-id").lower()
    controller = _controller_from_props(props)
    if not controller:
        controller = "A" if name.endswith("-a") else "B" if name.endswith("-b") else ""
    if controller:
        MGMT_LINK_UP.labels(controller).set(1 if number(first(props, "link-speed")) > 0 else 0)
        MGMT_HEALTH.labels(controller).set(state_ok(first(props, "health"), ("ok",)))
        return True
    return False


def collect(client: ME5Client) -> None:
    total_count = 0

    for command, parser in (
        ("show ports", _collect_host_port),
        ("show sas-link-health", _collect_expander_port),
        ("show network-parameters", _collect_management_port),
    ):
        try:
            total_count += _collect_response(client, command, parser)
        except Exception:
            LOG.warning("Optional ports command failed: %s", command, exc_info=True)

    if total_count == 0:
        raise ValueError("No port objects recognized in ports XML")
