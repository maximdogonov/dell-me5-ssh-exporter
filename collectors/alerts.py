"""Alert collector."""

from __future__ import annotations

from collector.ssh import ME5Client
from collector.text import label_text
from collector.xml import first, objects, parse_xml, response_success
from metrics import ACTIVE_ALERTS, ALERTS_BY_SEVERITY, ALERT_INFO

MAX_ALERT_INFO = 20


def collect(client: ME5Client) -> None:
    root = parse_xml(client.command("show alerts"))
    if not response_success(root):
        raise ValueError("show alerts returned failure")
    counts = {"critical": 0, "error": 0, "warning": 0, "informational": 0, "unknown": 0}
    active_alerts: list[dict[str, str]] = []
    total = 0
    for obj, props in objects(root):
        bt = obj.get("basetype") or ""
        if "alert" not in bt:
            continue
        if first(props, "resolved").lower() in {"yes", "true", "1"}:
            continue
        severity = first(props, "severity", "level", "priority", default="unknown").lower()
        if severity in {"info", "information"}:
            severity = "informational"
        if severity not in counts:
            severity = "unknown"
        counts[severity] += 1
        total += 1
        active_alerts.append({**props, "normalized_severity": severity})
    ACTIVE_ALERTS.set(total)
    for severity, count in counts.items():
        ALERTS_BY_SEVERITY.labels(severity).set(count)

    for slot, props in enumerate(active_alerts[:MAX_ALERT_INFO], start=1):
        ALERT_INFO.labels(str(slot)).info({
            "id": first(props, "id"),
            "severity": first(props, "normalized_severity", "severity"),
            "component": first(props, "component"),
            "description": label_text(first(props, "description")),
            "reason": label_text(first(props, "reason")),
            "recommended_action": label_text(first(props, "recommended-action")),
            "detected_time": first(props, "detected-time"),
            "resolved": first(props, "resolved"),
        })
    for slot in range(len(active_alerts[:MAX_ALERT_INFO]) + 1, MAX_ALERT_INFO + 1):
        try:
            ALERT_INFO.remove(str(slot))
        except KeyError:
            pass
