"""XML parsing helpers for Dell ME CLI responses."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator


def first(props: dict[str, str], *names: str, default: str = "") -> str:
    for name in names:
        value = props.get(name, "").strip()
        if value:
            return value
    return default


def number(value: str, default: float = 0.0) -> float:
    if not value:
        return default
    match = re.search(r"[-+]?\d+(?:\.\d+)?", value.replace(",", ""))
    return float(match.group(0)) if match else default


def bytes_from_value(value: str, unit_hint: str = "") -> float:
    if not value:
        return 0.0
    match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*([kmgtpe]?i?b)?", value, re.I)
    if not match:
        return 0.0
    amount = float(match.group(1))
    unit = (match.group(2) or unit_hint or "B").upper()
    powers = {
        "B": 0,
        "KB": 1,
        "KIB": 1,
        "MB": 2,
        "MIB": 2,
        "GB": 3,
        "GIB": 3,
        "TB": 4,
        "TIB": 4,
        "PB": 5,
        "PIB": 5,
        "EB": 6,
        "EIB": 6,
    }
    return amount * (1024 ** powers.get(unit, 0))


def state_ok(
    value: str,
    accepted: Iterable[str] = ("ok", "operational", "up", "online", "available", "ready"),
) -> float:
    return 1.0 if value.strip().lower() in set(accepted) else 0.0


def extract_xml(text: str) -> str:
    start = text.find("<?xml")
    if start < 0:
        start = text.find("<RESPONSE")
    end_tag = "</RESPONSE>"
    end = text.rfind(end_tag)
    if start < 0 or end < 0:
        raise ValueError("ME5 XML RESPONSE not found")
    return text[start : end + len(end_tag)]


def parse_xml(text: str) -> ET.Element:
    return ET.fromstring(extract_xml(text))


def properties(obj: ET.Element) -> dict[str, str]:
    return {
        prop.get("name", ""): (prop.text or "").strip()
        for prop in obj.findall("PROPERTY")
    }


def objects(
    root: ET.Element,
    basetype: str | None = None,
    name: str | None = None,
) -> Iterator[tuple[ET.Element, dict[str, str]]]:
    for obj in root.findall("OBJECT"):
        if basetype is not None and obj.get("basetype") != basetype:
            continue
        if name is not None and obj.get("name") != name:
            continue
        yield obj, properties(obj)


def response_success(root: ET.Element) -> bool:
    for _, props in objects(root, "status", "status"):
        return first(props, "response-type").lower() == "success" and first(props, "return-code", default="0") == "0"
    return True
