"""Minimal in-memory RAG grounding for iFlow generation.

A curated set of SAP CPI pattern snippets. Retrieval is keyword-scored (a stand
-in for the BM25 + vector hybrid described in the roadmap) and returns citations
so every generated artifact is grounded and traceable. This module is the seam
where the real vector store (Qdrant + BM25) plugs in later.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Pattern:
    doc_id: str
    title: str
    terms: list[str]
    body: str


_KB: list[Pattern] = [
    Pattern("PAT-HTTPS-SENDER", "HTTPS sender adapter",
            ["http", "https", "rest", "api", "sender", "inbound"],
            "Expose an HTTPS endpoint; set CSRF protection off for service calls; "
            "restrict by client certificate or OAuth; address /http/<path>."),
    Pattern("PAT-CONTENT-MODIFIER", "Content Modifier",
            ["header", "property", "content", "modifier", "enrich", "set"],
            "Use a Content Modifier to set exchange properties and headers before mapping; "
            "keep correlation IDs in properties for MPL traceability."),
    Pattern("PAT-MESSAGE-MAPPING", "Message Mapping (JSON/XML)",
            ["map", "mapping", "json", "xml", "transform", "convert", "structure"],
            "Model source and target; use JSON-to-XML converter before mapping when the "
            "sender is JSON; validate against target XSD."),
    Pattern("PAT-ODATA-RECEIVER", "OData receiver (S/4HANA)",
            ["odata", "s/4", "s4", "s4hana", "receiver", "sap", "outbound"],
            "Call S/4HANA via OData V2/V4 receiver; batch for bulk upserts; map keys carefully; "
            "handle 4xx as functional errors, 5xx as retryable."),
    Pattern("PAT-GROOVY-STEP", "Groovy script step",
            ["groovy", "script", "custom", "enrich", "transform"],
            "Use a Groovy script for logic not expressible in mapping; access message body, "
            "headers, properties; never log secrets; keep it idempotent."),
    Pattern("PAT-ERROR-SUBPROCESS", "Exception subprocess & retry",
            ["error", "exception", "retry", "backoff", "fault", "handling"],
            "Add an exception subprocess; classify transient vs permanent; retry transient with "
            "exponential backoff; route permanent failures to a dead-letter/alert."),
    Pattern("PAT-JMS-QUEUE", "JMS queue (async decoupling)",
            ["jms", "queue", "async", "decouple", "buffer"],
            "Use JMS to decouple sender and receiver; size queues; monitor depth; "
            "retry poison messages only after root-cause, not blindly."),
]


def retrieve(query: str, k: int = 4) -> list[dict]:
    q = query.lower()
    scored: list[tuple[int, Pattern]] = []
    for p in _KB:
        score = sum(1 for t in p.terms if t in q)
        if score:
            scored.append((score, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:k] if scored else [(0, _KB[0]), (0, _KB[3])]
    return [
        {"doc_id": p.doc_id, "title": p.title, "score": s, "snippet": p.body}
        for s, p in top
    ]
