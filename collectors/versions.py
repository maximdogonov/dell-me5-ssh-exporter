"""Firmware and software versions collector."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from collector.ssh import ME5Client
from collector.xml import first, objects, parse_xml, response_success
from metrics import VERSION_INFO

LOG = logging.getLogger("me5-exporter")


def _version_root(client: ME5Client) -> ET.Element:
    try:
        root = parse_xml(client.command("show versions detail"))
        if response_success(root):
            return root
    except Exception:
        LOG.debug("show versions detail failed; falling back to show versions", exc_info=True)

    root = parse_xml(client.command("show versions"))
    if not response_success(root):
        raise ValueError("show versions returned failure")
    return root


def _component_name(basetype: str, props: dict[str, str], index: int) -> str:
    return first(
        props,
        "name",
        "component",
        "controller",
        "controller-id",
        "module",
        "slot",
        "durable-id",
        "serial-number",
        default=f"{basetype}-{index}",
    )


def _version_value(props: dict[str, str]) -> str:
    return first(
        props,
        "version",
        "bundle-version",
        "firmware-version",
        "fw-version",
        "revision",
        "rev",
        "sc-fw",
        "mc-fw",
    )


def collect(client: ME5Client) -> None:
    root = _version_root(client)
    count = 0
    for obj, props in objects(root):
        basetype = obj.get("basetype") or "unknown"
        if basetype == "status":
            continue
        component = _component_name(basetype, props, count)
        VERSION_INFO.labels(basetype, component).info({
            "version": _version_value(props),
            "controller": first(props, "controller", "controller-id"),
            "model": first(props, "model", "product-id", "part-number"),
            "serial_number": first(props, "serial-number"),
            "vendor": first(props, "vendor", "vendor-name"),
            "description": first(props, "description", "name", default=component),
        })
        count += 1

    if count == 0:
        raise ValueError("No version objects recognized in show versions XML")
