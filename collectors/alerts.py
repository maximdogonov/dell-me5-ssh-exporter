"""Alert collector."""

from __future__ import annotations

from collector.ssh import ME5Client
from collector.xml import first, objects, parse_xml, response_success
from metrics import ACTIVE_ALERTS, ALERTS_BY_SEVERITY


def collect(client: ME5Client) -> None:
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
