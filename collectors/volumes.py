"""Volume collector."""

from __future__ import annotations

from collector.ssh import ME5Client
from collector.xml import bytes_from_value, first, objects, parse_xml, response_success, state_ok
from metrics import VOLUME_HEALTH, VOLUME_INFO, VOLUME_ONLINE, VOLUME_SIZE


def collect(client: ME5Client) -> None:
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
