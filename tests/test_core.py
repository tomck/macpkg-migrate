import json

from macpkg_migrate.core import (
    Identity,
    candidates_for,
    choose_candidate,
    dry_run,
    load_snapshot,
    plan_record,
)


def relation(status="automatic", target="python314", manager="macports"):
    return {
        "type": "equivalent",
        "source": {"manager": "homebrew", "package_type": "formula", "native_name": "python@3.14"},
        "target": {"manager": manager, "package_type": "port" if manager == "macports" else "package", "native_name": target},
        "confidence": 0.94,
        "matching_method": "version-family",
        "evidence": [{"kind": "upstream", "value": "https://python.org"}],
        "review_status": status,
        "source_catalog_versions": {"homebrew": "h", "macports": "m"},
    }


def test_snapshot_and_metadata_are_preserved(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"catalog_version": "v1", "relations": [relation()]}))
    data = load_snapshot(path)
    source = Identity("homebrew", "formula", "python@3.14")
    candidates = candidates_for(data["relations"], source)
    record = plan_record(source, candidates, data["catalog_version"])
    assert record["catalog_version"] == "v1"
    assert record["candidates"][0]["evidence"]
    assert record["candidates"][0]["matching_method"] == "version-family"


def test_review_only_near_hit_cannot_be_selected_or_installed():
    candidate = choose_candidate([__import__("macpkg_migrate.core", fromlist=["Candidate"]).Candidate.from_relation(relation("needs-review"))])
    assert candidate is None
    record = plan_record(Identity("homebrew", "formula", "python@3.14"), [], "v1")
    assert dry_run(record)["would_install"] is False
    assert dry_run(record)["would_remove"] is False


def test_preference_breaks_ties_between_automatic_managers():
    first = relation(target="python314", manager="macports")
    second = relation(target="python", manager="fink")
    candidates = candidates_for([first, second], Identity("homebrew", "formula", "python@3.14"))
    chosen = choose_candidate(candidates, ("fink", "macports"))
    assert chosen.target.manager == "fink"


def test_malformed_or_other_source_is_not_a_candidate():
    other = relation(); other["source"]["native_name"] = "gcc"
    assert candidates_for([other], Identity("homebrew", "formula", "python@3.14")) == []
