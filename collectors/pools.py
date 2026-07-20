"""Pool collector."""

from __future__ import annotations

from collector.ssh import ME5Client
from collector.xml import bytes_from_value, first, number, objects, parse_xml, response_success, state_ok
from metrics import POOL_FREE, POOL_HEALTH, POOL_SIZE, POOL_USED, POOL_USED_PERCENT


def collect(client: ME5Client) -> None:
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
