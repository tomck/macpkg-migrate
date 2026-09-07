"""Shared, manager-neutral migration planning primitives.

This module deliberately knows nothing about Homebrew, MacPorts, or Fink
commands.  It only handles catalog records, candidate selection, plan records,
and the safety policy shared by manager-specific front ends.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


AUTOMATIC = "automatic"
REVIEW = "needs-review"
SAFE_STATUSES = frozenset({AUTOMATIC, "installed"})


@dataclass(frozen=True)
class Identity:
    manager: str
    package_type: str
    native_name: str

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "Identity":
        return cls(
            record.get("manager", ""),
            record.get("package_type", record.get("type", "")),
            record.get("native_name", record.get("name", "")),
        )

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class Candidate:
    target: Identity
    relation_type: str
    confidence: float
    review_status: str
    matching_method: str
    evidence: tuple[Any, ...]
    source_catalog_versions: Mapping[str, Any]

    @classmethod
    def from_relation(cls, relation: Mapping[str, Any]) -> "Candidate":
        target = Identity.from_record(relation.get("target", {}))
        return cls(
            target=target,
            relation_type=relation.get("type", "equivalent"),
            confidence=float(relation.get("confidence", 0)),
            review_status=relation.get("review_status", REVIEW),
            matching_method=relation.get("matching_method", "unknown"),
            evidence=tuple(relation.get("evidence", ())),
            source_catalog_versions=relation.get("source_catalog_versions", {}),
        )

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["target"] = self.target.as_dict()
        result["evidence"] = list(self.evidence)
        result["source_catalog_versions"] = dict(self.source_catalog_versions)
        return result


def load_snapshot(path: str | Path) -> dict[str, Any]:
    """Load a catalog JSON snapshot or SQLite export without network access."""

    path = Path(path)
    if path.suffix in {".sqlite", ".db"}:
        with sqlite3.connect(path) as connection:
            packages = [dict(row) for row in connection.execute("SELECT * FROM packages")]
            relations = [dict(row) for row in connection.execute("SELECT * FROM relations")]
            metadata = {
                key: json.loads(value)
                for key, value in connection.execute("SELECT key, value FROM metadata")
            } if _has_table(connection, "metadata") else {}
        return {"packages": packages, "relations": relations, **metadata}
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return {"relations": data}
    if not isinstance(data, dict):
        raise ValueError("catalog snapshot must be a JSON object or relation array")
    return data


def _has_table(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def candidates_for(
    relations: Iterable[Mapping[str, Any]], source: Identity
) -> list[Candidate]:
    """Return catalog candidates whose source exactly matches ``source``."""

    candidates = []
    for relation in relations:
        if Identity.from_record(relation.get("source", {})) == source:
            candidate = Candidate.from_relation(relation)
            if candidate.target.native_name:
                candidates.append(candidate)
    return candidates


def choose_candidate(
    candidates: Iterable[Candidate], preference: Iterable[str] = ()
) -> Candidate | None:
    """Choose only an automatic candidate, never a review-only near-hit."""

    preference = tuple(preference)
    eligible = [candidate for candidate in candidates if candidate.review_status == AUTOMATIC]
    eligible.sort(
        key=lambda candidate: (
            -candidate.confidence,
            preference.index(candidate.target.manager)
            if candidate.target.manager in preference
            else len(preference),
            candidate.target.native_name,
        )
    )
    return eligible[0] if eligible else None


def plan_record(
    source: Identity,
    candidates: Iterable[Candidate],
    catalog_version: str | None,
    preference: Iterable[str] = (),
) -> dict[str, Any]:
    """Build a serializable, manager-neutral migration plan record."""

    candidates = list(candidates)
    chosen = choose_candidate(candidates, preference)
    recommendation = None
    if chosen:
        recommendation = {
            "manager": chosen.target.manager,
            "type": chosen.target.package_type,
            "name": chosen.target.native_name,
            "confidence": chosen.confidence,
            "status": chosen.review_status,
            "method": chosen.matching_method,
            "relation_type": chosen.relation_type,
            "evidence": list(chosen.evidence),
            "source_catalog_versions": dict(chosen.source_catalog_versions),
            "review_status": chosen.review_status,
            "target": chosen.target.as_dict(),
        }
    return {
        "source": source.as_dict(),
        "catalog_version": catalog_version,
        "candidates": [candidate.as_dict() for candidate in candidates],
        "recommendation": recommendation,
        "action": "consolidate" if chosen else "review",
        "install_authorized": bool(chosen),
    }


def install_allowed(record: Mapping[str, Any]) -> bool:
    """Return whether shared policy permits unattended installation."""

    recommendation = record.get("recommendation") or {}
    return bool(
        record.get("install_authorized")
        and recommendation.get("review_status") == AUTOMATIC
        and recommendation.get("target", {}).get("manager") in {"macports", "fink"}
    )


def dry_run(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return a safe preview result; this function never invokes a manager."""

    return {
        "source": record.get("source"),
        "recommendation": record.get("recommendation"),
        "would_install": install_allowed(record),
        "would_remove": False,
        "rollback": "No packages changed; discard the plan or uninstall only after explicit review.",
    }
