"""Backend adapter for the installed macpkgmap catalog client."""
import json
import shutil
import subprocess

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
            marker=json.dumps(relation,sort_keys=True)
            if marker not in seen: seen.add(marker); relations.append(relation)
    return relations
