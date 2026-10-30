"""Deterministic, evidence-preserving KB artifact generation.

Produces governed Markdown (KEDB, Runbook, Integration Catalog Doc) with stable
metadata, approved headings, canonical-term repetition (BM25), preserved runtime
evidence and short action-led steps — from live inventory + MPL error patterns +
parsed iFlow models. No fabricated runtime values.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import schema


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def base_metadata(ctx: dict, artifact_type: str, object_name: str, priority: str, **extra) -> dict:
    md = {
        "environment": ctx.get("environment", "demo"),
        "customer_id": ctx.get("customer_id", "RCA"),
        "system_id": ctx.get("system_id", "CPI-RCA"),
        "sap_sid": ctx.get("sap_sid", "CPI"),
        "artifact_type": artifact_type,
        "object_name": object_name,
        "priority": priority,
        "domain": ctx.get("domain", "CPI"),
        "technology": ctx.get("technology", "SAP CPI"),
        "review_status": "draft",
        "version": "1",
        "created_at": _now(),
        "updated_at": _now(),
    }
    md.update({k: v for k, v in extra.items() if v})
    return md


def weak_points(model: dict) -> list[str]:
    """Predict weak points from a parsed iFlow model."""
    risks = []
    if not model.get("has_error_handling"):
        risks.append("No exception subprocess — transient failures are not retried and may be lost.")
    if (model.get("receiver_adapter") or "").upper() in ("ODATA", "SOAP", "HTTPS"):
        risks.append(f"Synchronous {model.get('receiver_adapter')} receiver — backend downtime propagates as caller errors; consider async/JMS decoupling.")
    if model.get("step_count", 0) == 0:
        risks.append("No processing steps detected — verify the flow is complete.")
    if not model.get("sender_adapter"):
        risks.append("Sender adapter not identified — inbound security posture unknown.")
    return risks or ["No structural weak points detected in the current model."]


def render_catalog(model: dict, ctx: dict) -> tuple[str, dict]:
    name = model.get("name", "iFlow")
    md = base_metadata(ctx, "interface_inventory", name, ctx.get("priority", "P3"),
                       interface_name=name, integration_flow_name=name,
                       integration_flow_id=model.get("id", ""), package_name=ctx.get("package_name", ""))
    risks = weak_points(model)
    steps = "\n".join(f"- {s['name']}{(' [' + s['activity_type'] + ']') if s.get('activity_type') else ''}"
                      for s in model.get("steps", [])) or "- (no steps parsed)"
    body = f"""# Integration Catalog: {name} ({model.get('sender_adapter','?')} to {model.get('receiver_adapter','?')})

{schema.metadata_block(md)}

## PURPOSE
Catalog entry for integration flow **{name}**. Sender {model.get('sender_adapter','unknown')}, receiver {model.get('receiver_adapter','unknown')}.

## TECHNICAL LANDSCAPE
- integration_flow_name: {name}
- integration_flow_id: {model.get('id','')}
- sender_adapter: {model.get('sender_adapter','unknown')}
- receiver_adapter: {model.get('receiver_adapter','unknown')}
- process_steps: {model.get('step_count', 0)}
- error_handling: {"present" if model.get('has_error_handling') else "absent"}

## PROCESS STEPS
{steps}

## WEAK POINTS AND RELIABILITY RISKS
{chr(10).join('- ' + r for r in risks)}

## VALIDATION
Confirm the deployed runtime artifact status is STARTED and that the sender endpoint responds. Verify error handling is present before promoting to production.
"""
    return body, md


def render_kedb(pattern: dict, ctx: dict) -> tuple[str, dict]:
    sig = pattern["signature"]
    phrase = schema.canonical_phrase(sig)
    priority = pattern.get("priority", "P2")
    md = base_metadata(ctx, "kedb", schema.error_code(sig), priority,
                       interface_name=pattern.get("interface", ""),
                       integration_flow_name=pattern.get("interface", ""))
    evidence = pattern.get("evidence", pattern.get("error", ""))
    body = f"""# KEDB: {phrase} on SAP CPI ({pattern.get('interface','interface')})

{schema.metadata_block(md)}

## ERROR PATTERN
{phrase}. Observed on interface {pattern.get('interface','')}. Canonical signature: {sig}.

## SYMPTOMS
Messages fail with {phrase}. Exception: {pattern.get('exception','')}. Status FAILED in MPL.

## IMPACT
{pattern.get('count', 1)} failed message(s) in the observed window on {pattern.get('interface','')}; downstream processing delayed.

## ROOT CAUSE
{phrase} — typically caused by the condition described in the error signature ({sig}).

## CONFIRMING EVIDENCE
- interface: {pattern.get('interface','')}
- exception: {pattern.get('exception','')}
- error: {evidence}
- integration_flow_name: {pattern.get('interface','')}
- MessageGuid / MPL: preserved from the failed message log

## RESOLUTION SUMMARY
Apply the recovery for {phrase}: confirm the error signature, remediate the root cause, replay the message, and verify success.

## VALIDATION
Verify no new {phrase} occurrences after remediation; confirm the message reprocesses to COMPLETED.
"""
    return body, md


def render_runbook(pattern: dict, ctx: dict) -> tuple[str, dict]:
    sig = pattern["signature"]
    phrase = schema.canonical_phrase(sig)
    priority = pattern.get("priority", "P2")
    md = base_metadata(ctx, "runbook", schema.error_code(sig), priority,
                       interface_name=pattern.get("interface", ""),
                       integration_flow_name=pattern.get("interface", ""))
    evidence = pattern.get("evidence", pattern.get("error", ""))
    body = f"""# Runbook: Resolve {phrase} on SAP CPI ({pattern.get('interface','interface')})

{schema.metadata_block(md)}

## PURPOSE
Operational recovery for {phrase} on interface {pattern.get('interface','')}.

## BUSINESS CONTEXT
{phrase} interrupts message processing for {pattern.get('interface','')}, delaying dependent business transactions.

## TECHNICAL LANDSCAPE
- integration_flow_name: {pattern.get('interface','')}
- error signature: {sig}
- exception: {pattern.get('exception','')}

## MONITORING AND MPL EVIDENCE
- error: {evidence}
- MessageGuid and MPL status FAILED are preserved from the runtime message log.

## ERROR SIGNATURE
{phrase} — {sig}.

## KNOWN ROOT CAUSES
- Condition described by {phrase} ({sig}).
- Connectivity, authorization or backend availability related to {pattern.get('interface','')}.

## PREREQUISITES FOR INVESTIGATION
- Access to SAP CPI monitoring (MPL) with MonitoringDataRead scope.
- The failing MessageGuid and integration flow name.

## DIAGNOSIS STEPS
- Check the MPL entry for {phrase} on {pattern.get('interface','')}.
- Verify the exact error text: {evidence}.
- Confirm whether the failure is transient or permanent.

## RECOVERY STEPS
- Remediate the root cause of {phrase}.
- Replay the failed message once the cause is cleared.
- Verify the message reprocesses to COMPLETED.

## ESCALATION CRITERIA
- Escalate if {phrase} recurs after remediation or affects a P1/P2 interface beyond the SLA window.

## POST-FIX VALIDATION
- Confirm no new {phrase} occurrences.
- Validate the interface {pattern.get('interface','')} returns to a healthy state.
"""
    return body, md
