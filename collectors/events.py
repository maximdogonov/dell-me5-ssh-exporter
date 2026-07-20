"""Recent event text collector."""

from __future__ import annotations

from collector.ssh import ME5Client
from collector.text import label_text
from collector.xml import first, number, objects, parse_xml, response_success
from metrics import EVENT_INFO

MAX_EVENT_INFO = 20


def _event_time(props: dict[str, str]) -> str:
    return first(
        props,
        "time-stamp",
        "timestamp",
        "time",
        "event-time",
        "detected-time",
        "date-time",
        "date",
    )


def _event_time_numeric(props: dict[str, str]) -> float:
    return number(first(
        props,
        "time-stamp-numeric",
        "timestamp-numeric",
        "time-numeric",
        "event-time-numeric",
        "detected-time-numeric",
        "date-time-numeric",
        "date-numeric",
        "id",
        "event-id",
    ))


def _event_message(props: dict[str, str]) -> str:
    return first(
        props,
        "message",
        "description",
        "event",
        "reason",
        "text",
        "details",
    )


def _clear_unused(start_slot: int) -> None:
    for rank in range(start_slot, MAX_EVENT_INFO + 1):
        try:
            EVENT_INFO.remove(str(rank))
        except KeyError:
            pass


def collect(client: ME5Client) -> None:
    root = parse_xml(client.command("show events"))
    if not response_success(root):
        raise ValueError("show events returned failure")

    event_rows: list[dict[str, str]] = []
    for obj, props in objects(root):
        basetype = obj.get("basetype") or ""
        if "event" not in basetype:
            continue
        event_rows.append({**props, "_sort": str(_event_time_numeric(props))})

    event_rows.sort(key=lambda props: number(props["_sort"]), reverse=True)

    for rank, props in enumerate(event_rows[:MAX_EVENT_INFO], start=1):
        EVENT_INFO.labels(str(rank)).info({
            "id": first(props, "id", "event-id"),
            "severity": first(props, "severity", "level", "priority", "type"),
            "component": first(props, "component", "controller", "controller-id"),
            "code": first(props, "code", "event-code", "event-id", "reason-numeric"),
            "time": _event_time(props),
            "message": label_text(_event_message(props)),
        })

    _clear_unused(len(event_rows[:MAX_EVENT_INFO]) + 1)

    if not event_rows:
        raise ValueError("No event objects recognized in show events XML")
