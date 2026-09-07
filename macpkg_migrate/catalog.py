"""Backend adapter for the installed macpkgmap catalog client."""
import json
import shutil
import subprocess

from .core import Identity, candidates_for

def fetch(installed, client="macpkgmap", run=subprocess.run, progress=None):
    executable=shutil.which(client) or client
    relations=[]; seen=set()
    for item in installed:
        manager=item["manager"]; package_type=item["type"]; name=item["name"]
        if progress: progress(f"Querying macpkgmap for {manager}:{name}...")
        result=run([executable,"relations",manager,package_type,name],capture_output=True,text=True)
        if result.returncode != 0: continue
        try: payload=json.loads(result.stdout)
        except json.JSONDecodeError: continue
        for relation in payload.get("results",[]):
            # Reject malformed or source-mismatched responses fail-closed.
            expected = Identity(manager, package_type, name)
            if Identity.from_record(relation.get("source", {})) != expected:
                continue
            relation = dict(relation)
            relation["catalog_version"] = payload.get("catalog_version")
            marker=json.dumps(relation,sort_keys=True)
            if marker not in seen: seen.add(marker); relations.append(relation)
    return relations
