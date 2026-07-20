"""Volume collector."""

from __future__ import annotations

from collector.ssh import ME5Client
from collector.xml import bytes_from_value, first, objects, parse_xml, response_success, state_ok
from metrics import VOLUME_ALLOCATED, VOLUME_HEALTH, VOLUME_INFO, VOLUME_ONLINE, VOLUME_SIZE, VOLUME_USED_PERCENT


def collect(client: ME5Client) -> None:
    root = parse_xml(client.command("show volumes"))
    if not response_success(root):
        raise ValueError("show volumes returned failure")
    count = 0
    for obj, props in objects(root):
        if obj.get("basetype") not in {"volume", "volumes", "virtual-volume", "virtual-volumes"}:
            continue
        volume = first(props, "volume-name", "name", "durable-id", "serial-number", default=f"volume-{count}")
        health = first(props, "health")
        status = first(props, "status", "state", default=health)
        size = bytes_from_value(first(props, "size", "total-size", "capacity"))
        allocated = bytes_from_value(first(props, "allocated-size", "allocated", "used-size", "used"))
        VOLUME_HEALTH.labels(volume).set(state_ok(health, ("ok",)))
        VOLUME_ONLINE.labels(volume).set(state_ok(status))
        VOLUME_SIZE.labels(volume).set(size)
        VOLUME_ALLOCATED.labels(volume).set(allocated)
        VOLUME_USED_PERCENT.labels(volume).set((allocated / size * 100) if size else 0)
        VOLUME_INFO.labels(volume).info({
            "serial_number": first(props, "serial-number"),
            "pool": first(props, "pool", "pool-name", "storage-pool-name"),
            "raid_type": first(props, "raid-type", "raidtype"),
            "owner": first(props, "owner", "preferred-owner"),
            "type": first(props, "type", "volume-type"),
        })
        count += 1
    if count == 0:
        raise ValueError("No volume objects recognized in show volumes XML")
