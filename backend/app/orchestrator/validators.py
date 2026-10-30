"""Deterministic validation of a generated iFlow artifact."""
from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree import ElementTree as ET


@dataclass
class ValidationResult:
    ok: bool
    checks: list[dict] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append({"name": name, "passed": passed, "detail": detail})


_BPMN = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"


def validate_iflow(xml: str) -> ValidationResult:
    res = ValidationResult(ok=True)

    # 1) well-formedness
    try:
        root = ET.fromstring(xml)
        res.add("well_formed_xml", True)
    except ET.ParseError as e:
        res.add("well_formed_xml", False, str(e))
        res.ok = False
        return res

    # 2) required structural elements
    def has(tag: str) -> bool:
        return root.find(f".//{_BPMN}{tag}") is not None

    for tag, label in [
        ("collaboration", "collaboration present"),
        ("process", "integration process present"),
        ("startEvent", "start event present"),
        ("endEvent", "end event present"),
    ]:
        ok = has(tag)
        res.add(label, ok)
        if not ok:
            res.ok = False

    # 3) participants (sender endpoint + integration process; receivers are
    # added in the Web IDE — a sender→process flow is valid, matching the
    # tenant's exported iFlow shape)
    parts = root.findall(f".//{_BPMN}participant")
    res.add("sender + process participants", len(parts) >= 2,
            f"found {len(parts)} participants")
    if len(parts) < 2:
        res.ok = False

    # 4) message flow with adapter (sender endpoint wired to the process)
    res.add("sender message flow", root.find(f".//{_BPMN}messageFlow") is not None)

    return res
