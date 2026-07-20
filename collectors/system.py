"""System collector."""

from __future__ import annotations

from collector.ssh import ME5Client
from collector.xml import first, objects, parse_xml, response_success, state_ok
from metrics import SYSTEM_HEALTH, SYSTEM_INFO


def collect(client: ME5Client) -> None:
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
