"""Disk collector."""

from __future__ import annotations

from collector.ssh import ME5Client
from collector.xml import bytes_from_value, first, number, objects, parse_xml, response_success, state_ok
from metrics import DISK_HEALTH, DISK_INFO, DISK_LIFE, DISK_ONLINE, DISK_RPM, DISK_SIZE, DISK_TEMP


def collect(client: ME5Client) -> None:
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
        DISK_SIZE.labels(*labels).set(bytes_from_value(first(props, "size", "raw-size", "total-size", "capacity")))
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
