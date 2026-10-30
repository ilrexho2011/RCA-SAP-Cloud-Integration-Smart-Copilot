"""Serialize a design brief into a Cloud Integration iFlow (.iflw) model.

This mirrors, field-for-field, a real working iFlow exported from the target
tenant (First Run with Basic Auth): HTTPS sender → Content Modifier step(s) →
message end, with the tenant's exact `ifl:property` sets, `cmdVariantUri`
component versions, and a complete BPMNDI diagram (float bounds, edges with
`sourceElement`/`targetElement`, `xsi:type="dc:Point"` waypoints). Keeping to
this proven shape is what lets the Web IDE open the flow instead of failing with
"Error while loading the details of the integration flow".

Dynamic parts layered on the known-good scaffold: the sender URL path, the
sender system name, and one Content Modifier per middle step of the plan.
Receivers/adapters are configured by the user in the Web IDE afterwards.
"""
from __future__ import annotations

from xml.sax.saxutils import escape

_NS = (
    'xmlns:bpmn2="http://www.omg.org/spec/BPMN/20100524/MODEL" '
    'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" '
    'xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
    'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" '
    'xmlns:ifl="http:///com.sap.ifl.model/Ifl.xsd" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
)


def _prop(key: str, value: str = "") -> str:
    return (f"<ifl:property><key>{escape(key)}</key>"
            f"<value>{escape(value)}</value></ifl:property>")


def _props(pairs: list[tuple[str, str]]) -> str:
    return "".join(_prop(k, v) for k, v in pairs)


def _slug(text: str) -> str:
    keep = [c.lower() if c.isalnum() else "_" for c in (text or "")]
    s = "".join(keep).strip("_")
    while "__" in s:
        s = s.replace("__", "_")
    return s[:60] or "flow"


# --- exact property sets copied from the working tenant iFlow ---
def _collab_props() -> str:
    return _props([
        ("namespaceMapping", ""), ("httpSessionHandling", "None"),
        ("accessControlMaxAge", ""), ("returnExceptionToSender", "false"),
        ("log", "All events"), ("corsEnabled", "false"), ("exposedHeaders", ""),
        ("componentVersion", "1.2"), ("allowedHeaderList", ""), ("ServerTrace", "false"),
        ("allowedOrigins", ""), ("accessControlAllowCredentials", "false"),
        ("allowedHeaders", ""), ("allowedMethods", ""),
        ("cmdVariantUri", "ctype::IFlowVariant/cname::IFlowConfiguration/version::1.2.4"),
    ])


def _process_props() -> str:
    return _props([
        ("transactionTimeout", "30"), ("componentVersion", "1.2"),
        ("cmdVariantUri", "ctype::FlowElementVariant/cname::IntegrationProcess/version::1.2.1"),
        ("transactionalHandling", "Not Required"),
    ])


def _sender_props(url_path: str, system: str) -> str:
    return _props([
        ("ComponentType", "HTTPS"), ("Description", ""), ("maximumBodySize", "40"),
        ("ComponentNS", "sap"), ("componentVersion", "1.5"), ("urlPath", url_path),
        ("Name", "HTTPS"), ("TransportProtocolVersion", "1.5.1"),
        ("ComponentSWCVName", "external"), ("system", system), ("xsrfProtection", "0"),
        ("TransportProtocol", "HTTPS"),
        ("cmdVariantUri", "ctype::AdapterVariant/cname::sap:HTTPS/tp::HTTPS/mp::None/direction::Sender/version::1.5.1"),
        ("userRole", "ESBMessaging.send"), ("senderAuthType", "RoleBased"),
        ("MessageProtocol", "None"), ("MessageProtocolVersion", "1.5.1"),
        ("ComponentSWCVId", "1.5.1"), ("direction", "Sender"), ("clientCertificates", ""),
    ])


def _enricher_props(body: str) -> str:
    return _props([
        ("bodyType", "constant"), ("propertyTable", ""), ("headerTable", ""),
        ("wrapContent", body), ("componentVersion", "1.6"), ("activityType", "Enricher"),
        ("cmdVariantUri", "ctype::FlowstepVariant/cname::Enricher/version::1.6.0"),
    ])


# Step-type library. Only inline single-node flow steps that keep the linear
# topology are typed here (they render as their real step and open fine even if
# left unconfigured). Steps that need extra participants or gateways (receivers,
# Request-Reply, Router, Multicast) fall back to a Content Modifier placeholder
# that carries the description — building that topology needs a real per-adapter
# template, so it is created for the user to complete rather than guessed.
def _mapping_props() -> str:
    return _props([
        ("mappingType", "MessageMapping"), ("mappingReference", ""), ("mappingname", ""),
        ("mappinguri", ""), ("componentVersion", "1.5"), ("activityType", "Mapping"),
        ("cmdVariantUri", "ctype::FlowstepVariant/cname::MessageMapping/version::1.5.1"),
    ])


def _script_props() -> str:
    return _props([
        ("scriptFunction", "processData"), ("script", ""), ("subActivityType", "GroovyScript"),
        ("componentVersion", "1.1"), ("activityType", "Script"),
        ("cmdVariantUri", "ctype::FlowstepVariant/cname::GroovyScript/version::1.1.2"),
    ])


def _filter_props() -> str:
    return _props([
        ("xpath", ""), ("valueType", "NODELIST"), ("componentVersion", "1.1"),
        ("activityType", "Filter"),
        ("cmdVariantUri", "ctype::FlowstepVariant/cname::Filter/version::1.1.0"),
    ])


# Flip to True only once Mapping/Script/Filter step metadata is confirmed
# against the tenant (mirror a real export, like the Content Modifier). While
# False, all steps are safe Content Modifiers that render and open.
TYPED_STEPS = False


def _classify_step(name: str) -> str:
    n = (name or "").lower()
    if any(k in n for k in ("message mapping", "mapping", "validate against", ".xsd",
                            "canonical xml", "convert json", "convert to canonical")):
        return "mapping"
    if any(k in n for k in ("groovy", "script", ".gsh")):
        return "script"
    if n.startswith("filter") or "filter:" in n:
        return "filter"
    return "content_modifier"


def _step_props(kind: str) -> str:
    return {"mapping": _mapping_props(), "script": _script_props(),
            "filter": _filter_props()}.get(kind, _enricher_props(""))


def _start_props() -> str:
    return _props([("componentVersion", "1.0"),
                   ("cmdVariantUri", "ctype::FlowstepVariant/cname::MessageStartEvent/version::1.0")])


def _end_props() -> str:
    return _props([("componentVersion", "1.1"),
                   ("cmdVariantUri", "ctype::FlowstepVariant/cname::MessageEndEvent/version::1.1.0")])


def _f(v: int) -> str:
    return f"{float(v)}"


def _shape(el_id: str, x: int, y: int, w: int, h: int) -> str:
    return (f'<bpmndi:BPMNShape bpmnElement="{el_id}" id="BPMNShape_{el_id}">'
            f'<dc:Bounds height="{_f(h)}" width="{_f(w)}" x="{_f(x)}" y="{_f(y)}"/>'
            f'</bpmndi:BPMNShape>')


def _edge(flow_id: str, src_shape: str, tgt_shape: str, pts: list[tuple[int, int]]) -> str:
    wps = "".join(f'<di:waypoint x="{_f(x)}" xsi:type="dc:Point" y="{_f(y)}"/>' for x, y in pts)
    return (f'<bpmndi:BPMNEdge bpmnElement="{flow_id}" id="BPMNEdge_{flow_id}" '
            f'sourceElement="BPMNShape_{src_shape}" targetElement="BPMNShape_{tgt_shape}">'
            f'{wps}</bpmndi:BPMNEdge>')


def build_iflow_xml(iflow_id: str, iflow_name: str, classification: dict, brief: dict) -> str:
    steps = [str(s) for s in (brief.get("steps") or []) if s]
    middle = steps[1:-1] if len(steps) >= 2 else steps
    middle = middle[:10] or ["Content Modifier"]
    n = len(middle)
    url_path = "/" + _slug(iflow_id)
    system = str((classification or {}).get("sender") or "Sender")

    # --- ids ---
    start_id, end_id, mf_id = "StartEvent_2", "EndEvent_2", "MessageFlow_2"
    act_ids = [f"CallActivity_{5 + i}" for i in range(n)]
    node_ids = [start_id] + act_ids + [end_id]
    seq_ids = [f"SequenceFlow_{10 + i}" for i in range(len(node_ids) - 1)]

    def inc(nid: str) -> str:
        i = node_ids.index(nid)
        return f"<bpmn2:incoming>{seq_ids[i-1]}</bpmn2:incoming>" if i > 0 else ""

    def out(nid: str) -> str:
        i = node_ids.index(nid)
        return f"<bpmn2:outgoing>{seq_ids[i]}</bpmn2:outgoing>" if i < len(seq_ids) else ""

    # --- geometry (mirrors the template's coordinate system) ---
    ev, ay = 32, 158  # event box, shared vertical centre line
    start_x = 292
    act_x = [455 + i * 160 for i in range(n)]
    end_x = act_x[-1] + 100 + 148
    proc_x, proc_y, proc_h = 250, 60, 220
    proc_w = end_x - 134

    def cx(nid: str) -> int:
        if nid == start_id:
            return start_x + 16
        if nid == end_id:
            return end_x + 16
        return act_x[act_ids.index(nid)] + 50

    # --- collaboration ---
    sender_part = (
        '<bpmn2:participant id="Participant_1" ifl:type="EndpointSender" '
        f'name="{escape(system)}"><bpmn2:extensionElements>'
        f'{_props([("enableBasicAuthentication", "false"), ("ifl:type", "EndpointSender")])}'
        '</bpmn2:extensionElements></bpmn2:participant>'
    )
    proc_part = (
        '<bpmn2:participant id="Participant_Process_1" ifl:type="IntegrationProcess" '
        'name="Integration Process" processRef="Process_1">'
        '<bpmn2:extensionElements/></bpmn2:participant>'
    )
    mf = (
        f'<bpmn2:messageFlow id="{mf_id}" name="HTTPS" sourceRef="Participant_1" '
        f'targetRef="{start_id}"><bpmn2:extensionElements>{_sender_props(url_path, system)}'
        '</bpmn2:extensionElements></bpmn2:messageFlow>'
    )
    collaboration = (
        '<bpmn2:collaboration id="Collaboration_1" name="Default Collaboration">'
        f'<bpmn2:extensionElements>{_collab_props()}</bpmn2:extensionElements>'
        f'{sender_part}{proc_part}{mf}</bpmn2:collaboration>'
    )

    # --- process ---
    start_ev = (
        f'<bpmn2:startEvent id="{start_id}" name="Start"><bpmn2:extensionElements>'
        f'{_start_props()}</bpmn2:extensionElements>{out(start_id)}'
        '<bpmn2:messageEventDefinition/></bpmn2:startEvent>'
    )
    end_ev = (
        f'<bpmn2:endEvent id="{end_id}" name="End"><bpmn2:extensionElements>'
        f'{_end_props()}</bpmn2:extensionElements>{inc(end_id)}'
        '<bpmn2:messageEventDefinition/></bpmn2:endEvent>'
    )
    # Every step is emitted as a Content Modifier — the only step type verified
    # against this tenant (renders + opens). Typed steps (Mapping/Script/Filter,
    # receivers, Router, Multicast) are gated behind TYPED_STEPS until each has a
    # tenant-verified template; guessed metadata makes the property sheet fail
    # ("Metadata not available or not registered"). The description is kept as
    # the step name so the intended type is clear for the user to convert.
    activities = "".join(
        f'<bpmn2:callActivity id="{aid}" name="{escape(name[:120])}">'
        f'<bpmn2:extensionElements>'
        f'{_step_props(_classify_step(name)) if TYPED_STEPS else _enricher_props("")}'
        f'</bpmn2:extensionElements>'
        f'{inc(aid)}{out(aid)}</bpmn2:callActivity>'
        for aid, name in zip(act_ids, middle)
    )
    seq_flows = "".join(
        f'<bpmn2:sequenceFlow id="{sid}" sourceRef="{node_ids[i]}" targetRef="{node_ids[i+1]}"/>'
        for i, sid in enumerate(seq_ids)
    )
    process = (
        '<bpmn2:process id="Process_1" name="Integration Process">'
        f'<bpmn2:extensionElements>{_process_props()}</bpmn2:extensionElements>'
        f'{start_ev}{end_ev}{activities}{seq_flows}</bpmn2:process>'
    )

    # --- diagram ---
    shapes = [
        _shape(end_id, end_x, 142, ev, ev),
        _shape(start_id, start_x, 142, ev, ev),
    ]
    for aid, x in zip(act_ids, act_x):
        shapes.append(_shape(aid, x, 128, 100, 60))
    shapes += [
        _shape("Participant_1", 40, 100, 100, 140),
        _shape("Participant_Process_1", proc_x, proc_y, proc_w, proc_h),
    ]
    edges = []
    for i, sid in enumerate(seq_ids):
        src, tgt = node_ids[i], node_ids[i + 1]
        edges.append(_edge(sid, src, tgt, [(cx(src), ay), (cx(tgt), ay)]))
    edges.append(_edge(mf_id, "Participant_1", start_id, [(90, 170), (cx(start_id), ay)]))
    diagram = (
        '<bpmndi:BPMNDiagram id="BPMNDiagram_1" name="Default Collaboration Diagram">'
        '<bpmndi:BPMNPlane bpmnElement="Collaboration_1" id="BPMNPlane_1">'
        f'{"".join(shapes)}{"".join(edges)}'
        '</bpmndi:BPMNPlane></bpmndi:BPMNDiagram>'
    )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<bpmn2:definitions {_NS} id="Definitions_1">'
        f'{collaboration}{process}{diagram}</bpmn2:definitions>'
    )
