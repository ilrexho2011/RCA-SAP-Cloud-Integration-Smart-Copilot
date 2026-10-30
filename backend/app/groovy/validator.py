"""Static validation for generated CPI Groovy (no JVM available)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GroovyValidation:
    ok: bool = True
    checks: list[dict] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            self.ok = False


def validate(code: str) -> GroovyValidation:
    v = GroovyValidation()
    v.add("Message import present",
          "com.sap.gateway.ip.core.customdev.util.Message" in code)
    v.add("processData signature",
          "Message processData(Message message)" in code)
    v.add("returns message", "return message" in code)
    v.add("balanced braces", code.count("{") == code.count("}"),
          f"{{={code.count('{')} }}={code.count('}')}")
    v.add("balanced parentheses", code.count("(") == code.count(")"))
    v.add("no obvious secret logging",
          not any(s in code.lower() for s in ("println(password", "print(secret")))
    return v
