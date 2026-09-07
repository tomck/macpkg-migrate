from collections import defaultdict
from .core import Identity, candidates_for, plan_record

def make_plan(installed, relations, preference=("macports","fink","homebrew")):
    index={}
    for relation in relations:
        source=relation.get("source",{}); target=relation.get("target",{})
        left=(source.get("manager"),source.get("package_type"),source.get("native_name")); right=(target.get("manager"),target.get("package_type"),target.get("native_name"))
        if left[2] and right[2]: index.setdefault(left,[]).append((right,relation))
    groups=[]; seen=set()
    for item in installed:
        identity=(item["manager"],item["type"],item["name"])
        if identity in seen: continue
        family=[item]; seen.add(identity); queue=[identity]
        while queue:
            current=queue.pop()
            neighbors=[x[0] for x in index.get(current,[])] + [left for left,edges in index.items() if any(x[0]==current for x in edges)]
            for neighbor in neighbors:
                matches=[x for x in installed if (x["manager"],x["type"],x["name"])==neighbor]
                for match in matches:
                    key=(match["manager"],match["type"],match["name"])
                    if key not in seen: seen.add(key); family.append(match); queue.append(key)
        groups.append(family)
    rows=[]
    for family in groups:
        options=[]
        for item in family:
            key=(item["manager"],item["type"],item["name"])
            for target,relation in index.get(key,[]):
                options.append({"manager":target[0],"type":target[1],"name":target[2],"confidence":relation.get("confidence",0),"status":relation.get("review_status","needs-review"),"method":relation.get("matching_method","catalog")})
        options.extend({"manager":x["manager"],"type":x["type"],"name":x["name"],"confidence":1.0,"status":"installed","method":"already-installed"} for x in family)
        options.sort(key=lambda x:(x["status"] not in ("automatic","installed"),-x["confidence"],preference.index(x["manager"]) if x["manager"] in preference else 99))
        chosen=options[0] if options else None
        source = Identity.from_record(family[0])
        catalog_candidates = candidates_for(relations, source)
        if catalog_candidates:
            catalog_version = next((r.get("catalog_version") for r in relations if r.get("catalog_version")), None)
            record = plan_record(source, catalog_candidates, catalog_version, preference)
            record["members"] = family
            record["options"] = options[:10]
            rows.append(record)
        else:
            rows.append({"members":family,"options":options[:10],"recommendation":chosen,"action":"review" if not chosen or chosen["status"] not in ("automatic","installed") else "consolidate"})
    return rows
