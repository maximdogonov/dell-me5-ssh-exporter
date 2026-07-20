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


def _controller_from_object(name: str, props: dict[str, str]) -> str:
    controller = first(props, "controller", "controller-id").upper()
    if controller in {"A", "B"}:
        return controller
    lowered = name.lower()
    if "controller-a" in lowered:
        return "A"
    if "controller-b" in lowered:
        return "B"
    return controller


def _component_name(name: str, basetype: str, props: dict[str, str], index: int) -> str:
    if name == "controller-a-versions":
        return "controller-a"
    if name == "controller-b-versions":
        return "controller-b"
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


def collect(client: ME5Client) -> None:
    root = _version_root(client)
    count = 0
    for obj, props in objects(root):
        basetype = obj.get("basetype") or "unknown"
        if basetype == "status":
            continue
        name = obj.get("name") or ""
        component = _component_name(name, basetype, props, count)
        VERSION_INFO.labels(basetype, component).info({
            "version": first(props, "bundle-version", "bundle-version-only", "version"),
            "controller": _controller_from_object(name, props),
            "bundle_status": first(props, "bundle-status"),
            "bundle_base_version": first(props, "bundle-base-version"),
            "build_date": first(props, "build-date"),
            "sc_fw": first(props, "sc-fw"),
            "sc_baselevel": first(props, "sc-baselevel"),
            "sc_loader": first(props, "sc-loader"),
            "sc_asic_version": first(props, "sc-fu-version"),
            "mc_fw": first(props, "mc-fw"),
            "mc_base_fw": first(props, "mc-base-fw"),
            "mc_loader": first(props, "mc-loader"),
            "mc_os_version": first(props, "mcos-version"),
            "capi_version": first(props, "capi-version"),
            "ec_fw": first(props, "ec-fw"),
            "cpld_version": first(props, "pld-rev"),
            "hardware_version": first(props, "hw-rev"),
            "him_version": first(props, "him-rev"),
            "him_model": first(props, "him-model"),
            "help_version": first(props, "pubs-version"),
            "translation_version": first(props, "translation-version"),
        })
        count += 1

    if count == 0:
        raise ValueError("No version objects recognized in show versions XML")
