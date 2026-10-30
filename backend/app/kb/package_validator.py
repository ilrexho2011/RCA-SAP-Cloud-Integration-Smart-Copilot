#!/usr/bin/env python3
"""Validate AI4BIZ Markdown knowledge packages.

This helper performs deterministic static checks for AI4BIZ ingestion readiness.
It complements, but does not replace, full retrieval/RAG benchmarking.

Usage:
    validate_ai4biz_knowledge_package.py path/to/package_or_folder --out result.json --markdown report.md
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import zipfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

RUNBOOK_REQUIRED_SECTIONS = [
    "PURPOSE",
    "BUSINESS CONTEXT",
    "TECHNICAL LANDSCAPE",
    "MONITORING AND MPL EVIDENCE",
    "ERROR SIGNATURE",
    "KNOWN ROOT CAUSES",
    "PREREQUISITES FOR INVESTIGATION",
    "DIAGNOSIS STEPS",
    "RECOVERY STEPS",
    "ESCALATION CRITERIA",
    "POST-FIX VALIDATION",
]

KEDB_RECOMMENDED_SECTIONS = [
    "ERROR PATTERN",
    "SYMPTOMS",
    "IMPACT",
    "ROOT CAUSE",
    "CONFIRMING EVIDENCE",
    "RESOLUTION SUMMARY",
    "VALIDATION",
]

MANDATORY_METADATA = [
    "environment",
    "customer_id",
    "system_id",
    "sap_sid",
    "artifact_type",
    "object_name",
    "priority",
]

ACTION_VERBS = (
    "check", "verify", "confirm", "compare", "replay", "restart", "restore",
    "escalate", "apply", "open", "inspect", "validate", "review", "collect",
)

EVIDENCE_PATTERNS = [
    re.compile(r"\bmessageguid\b", re.I),
    re.compile(r"\bcorrelationid\b", re.I),
    re.compile(r"\bhttp\s*[1-5][0-9]{2}\b", re.I),
    re.compile(r"\b(adapter|sender|receiver|integrationflowname|integration_flow_id|mpl|exception|error)\b", re.I),
]

RB_KB_FILENAME_RE = re.compile(r"^(RB|KB)_[A-Z0-9]+_[A-Z0-9-]+_[A-Z0-9_]+_P[1-4]_v\d+\.md$", re.I)
DOC_FILENAME_RE = re.compile(r"^DOC_[A-Z0-9]+_[A-Z0-9-]+_[A-Z0-9_]+_v\d+\.md$", re.I)


def clamp(value: float) -> int:
    return int(max(0, min(100, round(value))))


def status_for_score(score: float) -> str:
    if score >= 90:
        return "Enterprise Ready"
    if score >= 80:
        return "Ready with minor improvements"
    if score >= 70:
        return "Conditional readiness"
    if score >= 60:
        return "Needs remediation"
    return "Not ready for RAG ingestion"


def normalize_heading(text: str) -> str:
    text = re.sub(r"^#+\s*", "", text.strip())
    text = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", text)
    text = text.replace("/", " / ").replace("–", "-").replace("—", "-")
    text = re.sub(r"[^A-Za-z0-9 /_-]+", "", text)
    text = re.sub(r"\s+", " ", text).strip().upper()
    return text


def safe_extract_zip(zip_path: Path, target_dir: Path) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            out = target_dir / member.filename
            resolved = out.resolve()
            if not str(resolved).startswith(str(target_dir.resolve())):
                raise ValueError(f"unsafe zip member path: {member.filename}")
        zf.extractall(target_dir)


def iter_markdown_files(path: Path) -> Tuple[Path, List[Path], Optional[tempfile.TemporaryDirectory]]:
    temp: Optional[tempfile.TemporaryDirectory] = None
    root = path
    if path.is_file() and path.suffix.lower() == ".zip":
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        safe_extract_zip(path, root)
    elif path.is_file() and path.suffix.lower() == ".md":
        return path.parent, [path], temp
    files = sorted(p for p in root.rglob("*.md") if p.is_file())
    return root, files, temp


def extract_title(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    for line in text.splitlines():
        if line.strip():
            return line.strip().strip("# ")
    return ""


def extract_headings(text: str) -> List[str]:
    headings: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            headings.append(normalize_heading(stripped))
            continue
        if re.match(r"^\d+(?:\.\d+)*\.\s+[A-Za-z].+", stripped):
            headings.append(normalize_heading(stripped))
    return headings


def normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")


def extract_metadata(text: str) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    lines = text.splitlines()

    # key: value lines
    for line in lines[:120]:
        m = re.match(r"^\s*([A-Za-z][A-Za-z0-9_ -]{1,40})\s*:\s*(.+?)\s*$", line)
        if m:
            key = normalize_key(m.group(1))
            value = m.group(2).strip()
            if value:
                metadata[key] = value

    # KEY on one line, value on next non-empty line
    known_labels = set(MANDATORY_METADATA + [
        "runbook_id", "runbook_title", "customer", "system", "version", "kedb_id",
        "document_id", "artifact_type", "object_name", "integration_flow_id",
    ])
    for i, line in enumerate(lines[:160]):
        label = normalize_key(line)
        if label in known_labels and label not in metadata:
            for nxt in lines[i + 1:i + 5]:
                if nxt.strip() and not nxt.strip().startswith("#"):
                    metadata[label] = nxt.strip()
                    break

    # aliases
    aliases = {
        "customer": "customer_id",
        "system": "system_id",
        "runbook_id": "document_id",
        "kedb_id": "document_id",
    }
    for src, dest in aliases.items():
        if src in metadata and dest not in metadata:
            metadata[dest] = metadata[src]

    return metadata


def artifact_type_from_filename(name: str, metadata: Dict[str, str]) -> str:
    if metadata.get("artifact_type"):
        return metadata["artifact_type"].lower()
    upper = name.upper()
    if upper.startswith("RB_"):
        return "runbook"
    if upper.startswith("KB_"):
        return "kedb"
    if upper.startswith("DOC_"):
        return "documentation"
    return "unknown"


def canonical_terms_from_filename(name: str) -> List[str]:
    stem = Path(name).stem
    parts = stem.split("_")
    if not parts:
        return []
    if parts[0].upper() in {"RB", "KB"} and len(parts) >= 6:
        error_parts = parts[3:-2]
    elif parts[0].upper() == "DOC" and len(parts) >= 5:
        error_parts = parts[3:-1]
    else:
        error_parts = parts[1:]
    terms = []
    phrase = " ".join(error_parts).replace("-", " ").strip()
    if phrase:
        terms.append(phrase.lower())
    for p in error_parts:
        token = p.replace("-", " ").lower().strip()
        if len(token) >= 3 and token not in {"error", "issue", "system"}:
            terms.append(token)
    # de-duplicate preserving order
    seen = set()
    unique = []
    for term in terms:
        if term not in seen:
            unique.append(term)
            seen.add(term)
    return unique


def longest_paragraph_words(text: str) -> int:
    paragraphs = re.split(r"\n\s*\n", text)
    return max((len(p.split()) for p in paragraphs), default=0)


def count_action_steps(text: str) -> int:
    count = 0
    for line in text.splitlines():
        stripped = re.sub(r"^[-*\d.)\s]+", "", line.strip()).lower()
        if any(stripped.startswith(v + " ") for v in ACTION_VERBS):
            count += 1
    return count


def count_evidence(text: str) -> int:
    return sum(1 for pat in EVIDENCE_PATTERNS if pat.search(text))


@dataclass
class Issue:
    category: str
    severity: str
    message: str
    recommendation: str


@dataclass
class DocumentResult:
    path: str
    file_name: str
    document_id: str
    artifact_type: str
    title: str
    status: str
    estimated_static_score: int
    category_scores: Dict[str, Optional[int]]
    missing_metadata: List[str]
    missing_sections: List[str]
    issues: List[Issue]


def validate_document(root: Path, file_path: Path) -> DocumentResult:
    text = file_path.read_text(encoding="utf-8", errors="replace")
    rel_path = str(file_path.relative_to(root)) if file_path.is_relative_to(root) else file_path.name
    metadata = extract_metadata(text)
    title = extract_title(text)
    headings = extract_headings(text)
    artifact_type = artifact_type_from_filename(file_path.name, metadata)
    document_id = metadata.get("document_id") or file_path.stem
    issues: List[Issue] = []

    # filename
    file_ok = bool(RB_KB_FILENAME_RE.match(file_path.name) or DOC_FILENAME_RE.match(file_path.name))
    if not file_ok:
        issues.append(Issue(
            "file_naming", "high",
            "Filename does not match the AI4BIZ naming convention.",
            "Use RB/KB_<CUSTOMER>_<SYSTEM>_<ERROR_CODE>_<P1-P4>_<vN>.md or DOC_<CUSTOMER>_<SYSTEM>_<NAME>_<vN>.md."
        ))

    missing_metadata = [field for field in MANDATORY_METADATA if field not in metadata or not metadata.get(field)]
    for field in missing_metadata:
        issues.append(Issue(
            "metadata_completeness", "high",
            f"Mandatory metadata field '{field}' is missing.",
            f"Add '{field}' to the metadata block at the top of the document."
        ))

    expected_sections: List[str] = []
    if artifact_type == "runbook":
        expected_sections = RUNBOOK_REQUIRED_SECTIONS
    elif artifact_type == "kedb":
        expected_sections = KEDB_RECOMMENDED_SECTIONS

    heading_set = set(headings)
    missing_sections = [s for s in expected_sections if s not in heading_set]
    for section in missing_sections:
        issues.append(Issue(
            "stable_headings", "medium",
            f"Expected section '{section}' is missing or renamed.",
            "Use the approved section names exactly so the parser and BM25 classifier can recognize the content."
        ))

    terms = canonical_terms_from_filename(file_path.name)
    text_lower = text.lower()
    title_lower = title.lower()
    primary_phrase = terms[0] if terms else ""
    title_has_phrase = bool(primary_phrase and primary_phrase in title_lower)
    if artifact_type in {"runbook", "kedb"} and not title_has_phrase:
        issues.append(Issue(
            "title_searchability", "medium",
            "Title does not contain the canonical retrieval phrase derived from the filename.",
            "Put the main searchable error phrase, protocol, status code, or component directly in the title."
        ))

    repeated_terms = 0
    for term in terms:
        if term and text_lower.count(term) >= 2:
            repeated_terms += 1
    if artifact_type in {"runbook", "kedb"} and terms and repeated_terms < max(1, min(3, len(terms) // 2)):
        issues.append(Issue(
            "bm25_readiness", "high",
            "Canonical terms are not repeated consistently across key sections.",
            "Repeat canonical terms in title, error signature, diagnosis, recovery/fix, and evidence sections."
        ))

    evidence_count = count_evidence(text)
    if artifact_type in {"runbook", "kedb"} and evidence_count < 2:
        issues.append(Issue(
            "evidence_presence", "medium",
            "Runtime evidence appears weak or missing.",
            "Preserve literal evidence such as MessageGuid, CorrelationId, HTTP status, adapter, sender, receiver, MPL, exception, or IntegrationFlowName."
        ))

    actions = count_action_steps(text)
    if artifact_type == "runbook" and actions < 3:
        issues.append(Issue(
            "operational_steps", "medium",
            "Runbook has few action-led operational steps.",
            "Write diagnosis, recovery, validation, and rollback as short action-led steps beginning with verbs such as Check, Verify, Confirm, Replay, Restart, Restore."
        ))

    max_para = longest_paragraph_words(text)
    if max_para > 140:
        issues.append(Issue(
            "chunking_quality", "medium",
            f"A paragraph has {max_para} words, which may create oversized or mixed chunks.",
            "Split long narrative blocks into shorter, heading-bounded and bullet-based sections."
        ))

    # category scores
    policy = 100
    if not file_ok:
        policy -= 15
    policy -= 8 * len(missing_metadata)
    policy -= 6 * len(missing_sections)

    bm25 = 20
    if title_has_phrase:
        bm25 += 30
    if terms:
        bm25 += min(30, int(30 * repeated_terms / max(1, len(terms))))
    if evidence_count >= 2:
        bm25 += 15
    if max_para <= 100:
        bm25 += 5

    chunking = 50
    if expected_sections:
        chunking += int(30 * (len(expected_sections) - len(missing_sections)) / len(expected_sections))
    if not missing_metadata:
        chunking += 10
    if max_para <= 100:
        chunking += 10

    policy = clamp(policy)
    bm25 = clamp(bm25)
    chunking = clamp(chunking)

    # Static estimate uses only categories available without an actual index/query-set.
    static_score = clamp((0.20 * policy + 0.15 * bm25 + 0.15 * chunking) / 0.50)

    return DocumentResult(
        path=rel_path,
        file_name=file_path.name,
        document_id=document_id,
        artifact_type=artifact_type,
        title=title,
        status=status_for_score(static_score),
        estimated_static_score=static_score,
        category_scores={
            "policy_compliance": policy,
            "bm25_readiness": bm25,
            "chunking_quality": chunking,
            "retrieval_precision": None,
            "retrieval_recall": None,
            "faithfulness": None,
            "citation_accuracy": None,
        },
        missing_metadata=missing_metadata,
        missing_sections=missing_sections,
        issues=issues,
    )


def package_summary(results: List[DocumentResult], source: Path) -> Dict[str, object]:
    if results:
        avg_static = clamp(sum(r.estimated_static_score for r in results) / len(results))
    else:
        avg_static = 0
    return {
        "source": str(source),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Static validation only. Retrieval precision, retrieval recall, faithfulness, and citation accuracy require benchmark queries, indexes, retrieved contexts, and answer traces.",
        "document_count": len(results),
        "estimated_static_package_score": avg_static,
        "status": status_for_score(avg_static),
        "documents": [
            {
                **{k: v for k, v in asdict(r).items() if k != "issues"},
                "issues": [asdict(i) for i in r.issues],
            }
            for r in results
        ],
    }


def render_markdown(summary: Dict[str, object]) -> str:
    lines = [
        "# AI4BIZ Static Knowledge Package Validation Report",
        "",
        f"Source: `{summary['source']}`",
        f"Generated at: {summary['generated_at']}",
        f"Document count: {summary['document_count']}",
        f"Estimated static package score: **{summary['estimated_static_package_score']}**",
        f"Status: **{summary['status']}**",
        "",
        "> This report validates static ingestion, BM25, and chunking-readiness signals only. Full RAG readiness requires retrieval and answer-generation benchmark data.",
        "",
        "## Documents",
        "",
        "| Document | Type | Score | Status | Issues |",
        "|---|---|---:|---|---:|",
    ]
    for doc in summary["documents"]:  # type: ignore[index]
        lines.append(
            f"| `{doc['file_name']}` | {doc['artifact_type']} | {doc['estimated_static_score']} | {doc['status']} | {len(doc['issues'])} |"
        )
    lines.extend(["", "## Issues", ""])
    for doc in summary["documents"]:  # type: ignore[index]
        lines.append(f"### {doc['file_name']}")
        if not doc["issues"]:
            lines.append("- No static issues detected.")
        else:
            for issue in doc["issues"]:
                lines.append(f"- **{issue['severity']} / {issue['category']}**: {issue['message']} Recommendation: {issue['recommendation']}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI4BIZ Markdown knowledge package static readiness.")
    parser.add_argument("path", help="Path to a .zip, folder, or single .md file")
    parser.add_argument("--out", help="Write JSON result to this path")
    parser.add_argument("--markdown", help="Write Markdown report to this path")
    parser.add_argument("--fail-under", type=int, default=None, help="Exit with code 2 if estimated static package score is below this value")
    args = parser.parse_args()

    source = Path(args.path).expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"Input path not found: {source}")

    root, files, temp = iter_markdown_files(source)
    try:
        results = [validate_document(root, f) for f in files]
        summary = package_summary(results, source)
        payload = json.dumps(summary, indent=2, ensure_ascii=False)
        if args.out:
            Path(args.out).write_text(payload + "\n", encoding="utf-8")
        if args.markdown:
            Path(args.markdown).write_text(render_markdown(summary) + "\n", encoding="utf-8")
        if not args.out and not args.markdown:
            print(payload)
        if args.fail_under is not None and summary["estimated_static_package_score"] < args.fail_under:
            return 2
        return 0
    finally:
        if temp is not None:
            temp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
