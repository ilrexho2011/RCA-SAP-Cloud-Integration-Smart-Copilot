"""Namespace-tolerant parser for SAP CPI iFlow (.iflw) BPMN2 files.

Works on both real Integration Suite exports and the skeletons produced by the
generator. Matches by local element name so BPMN/ifl namespace prefixes don't
matter. Extracts sender/receiver adapters, ordered process steps, and whether
error handling is present — the grounded facts an explanation is built from.
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET


@dataclass
class IFlowModel:
    name: str = "iFlow"
    sender_adapter: str = ""
    receiver_adapter: str = ""
    participants: list[dict] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    has_error_handling: bool = False

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "sender_adapter": self.sender_adapter,
            "receiver_adapter": self.receiver_adapter,
            "participants": self.participants,
            "steps": self.steps,
            "has_error_handling": self.has_error_handling,
        }


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _props(el: ET.Element) -> dict:
    """Read SAP ifl:property key/value pairs from extensionElements."""
    out: dict[str, str] = {}
    for ext in el.iter():
        if _local(ext.tag) == "property":
            key = val = None
            for child in ext:
                lt = _local(child.tag)
                if lt == "key":
                    key = (child.text or "").strip()
                elif lt == "value":
                    val = (child.text or "").strip()
            if key:
                out[key] = val or ""
    return out


_STEP_TAGS = {
    "callActivity": "step",
    "serviceTask": "service",
    "exclusiveGateway": "router",
    "subProcess": "subprocess",
    "startEvent": "start",
    "endEvent": "end",
}


def parse_iflow_xml(xml: str) -> IFlowModel:
    root = ET.fromstring(xml)
    m = IFlowModel()

    # name from collaboration/process
    for el in root.iter():
        lt = _local(el.tag)
        if lt in ("collaboration", "process") and el.get("name"):
            m.name = el.get("name") or m.name
            break

    # participants + adapter roles
    for el in root.iter():
        if _local(el.tag) != "participant":
            continue
        ptype = ""
        for k, v in el.attrib.items():
            if _local(k) == "type":
                ptype = v
        m.participants.append({"name": el.get("name", ""), "type": ptype})

    # adapters from messageFlow (ComponentType property, else name)
    for el in root.iter():
        if _local(el.tag) != "messageFlow":
            continue
        props = _props(el)
        adapter = props.get("ComponentType") or props.get("Name") or el.get("name", "")
        src = el.get("sourceRef", "")
        if src.lower().startswith("participant") and "sender" in src.lower():
            m.sender_adapter = adapter
        elif not m.sender_adapter and ("start" in el.get("targetRef", "").lower()):
            m.sender_adapter = adapter
        else:
            m.receiver_adapter = adapter or m.receiver_adapter

    # ordered process steps
    for proc in root.iter():
        if _local(proc.tag) != "process":
            continue
        for el in list(proc):
            lt = _local(el.tag)
            if lt in _STEP_TAGS:
                props = _props(el)
                m.steps.append({
                    "kind": _STEP_TAGS[lt],
                    "name": el.get("name", lt),
                    "activity_type": props.get("activityType", ""),
                })
                if lt == "subProcess" and ("error" in (el.get("name", "").lower())
                                            or "error" in props.get("activityType", "").lower()):
                    m.has_error_handling = True
        break

    if not m.has_error_handling:
        m.has_error_handling = any(
            s["kind"] == "subprocess" and "error" in (s["name"] + s["activity_type"]).lower()
            for s in m.steps
        )
    return m


def extract_iflw_from_zip(data: bytes) -> str:
    """Return the .iflw XML text from an exported iFlow ZIP."""
    with zipfile.ZipFile(_bytes_io(data)) as zf:
        candidates = [n for n in zf.namelist() if n.endswith(".iflw")]
        if not candidates:
            raise ValueError("No .iflw file found in the ZIP.")
        return zf.read(candidates[0]).decode("utf-8", errors="replace")


def extract_scripts_from_zip(data: bytes, limit: int = 6) -> list[dict]:
    """Return the Groovy/JS scripts bundled in an exported iFlow ZIP.

    Scripts live under src/main/resources/script/*.groovy (or *.js). Returns
    [{name, code}] with the code capped so an explanation stays grounded in the
    real script bodies without shipping huge payloads."""
    out: list[dict] = []
    try:
        with zipfile.ZipFile(_bytes_io(data)) as zf:
            names = [n for n in zf.namelist()
                     if (n.endswith(".groovy") or n.endswith(".js")) and not n.endswith("/")]
            for n in sorted(names)[:limit]:
                code = zf.read(n).decode("utf-8", errors="replace")
                out.append({"name": n.rsplit("/", 1)[-1], "code": code[:8000]})
    except Exception:  # noqa: BLE001 — a missing/broken ZIP just means "no scripts"
        return []
    return out


def _bytes_io(data: bytes):
    import io
    return io.BytesIO(data)
