import json
import urllib.request
from pathlib import Path

DEFAULT_URL="https://tomck.github.io/macpkg-catalog/relations.json"

def fetch(path="~/.cache/macpkg-migrate/relations.json",url=DEFAULT_URL,refresh=False):
    destination=Path(path).expanduser()
    if not refresh and destination.exists(): return json.loads(destination.read_text()).get("relations",[])
    request=urllib.request.Request(url,headers={"User-Agent":"macpkg-migrate"})
    with urllib.request.urlopen(request,timeout=120) as response: data=response.read()
    destination.parent.mkdir(parents=True,exist_ok=True); destination.write_bytes(data)
    return json.loads(data).get("relations",[])

def index(relations):
    result={}
    for relation in relations:
        source=relation.get("source",{}); target=relation.get("target",{})
        if not source.get("native_name") or not target.get("native_name"): continue
        left=(source.get("manager"),source.get("package_type"),source["native_name"])
        right=(target.get("manager"),target.get("package_type"),target["native_name"])
        result.setdefault(left,[]).append({"identity":right,"confidence":relation.get("confidence",0),"status":relation.get("review_status","needs-review"),"method":relation.get("matching_method","catalog")})
    return result
