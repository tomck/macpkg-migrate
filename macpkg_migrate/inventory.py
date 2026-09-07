import json,shutil,subprocess

def homebrew(run=subprocess.run):
    data=json.loads(run(["brew","info","--json=v2","--installed"],capture_output=True,text=True,check=True).stdout); result=[]
    for item in data.get("formulae",[]):
        if any(x.get("installed_on_request") for x in item.get("installed",[])):
            result.append({"manager":"homebrew","type":"formula","name":item.get("name") or item.get("full_name"),"version":(item.get("installed") or [{}])[-1].get("version","")})
    result += [{"manager":"homebrew","type":"cask","name":x.get("token") or x.get("name"),"version":x.get("version","")} for x in data.get("casks",[])]
    return result

def macports(run=subprocess.run):
    port=shutil.which("port") or "/opt/local/bin/port"
    result=run([port,"installed"],capture_output=True,text=True)
    if result.returncode: return []
    rows=[]
    for line in result.stdout.splitlines():
        fields=line.split()
        if len(fields)>=2 and fields[0] not in ("The","None"):
            rows.append({"manager":"macports","type":"port","name":fields[0],"version":fields[1]})
    return rows

def fink(run=subprocess.run):
    if not shutil.which("fink"): return []
    result=run(["fink","list","-i"],capture_output=True,text=True)
    if result.returncode: return []
    rows=[]
    for line in result.stdout.splitlines():
        fields=line.split()
        if len(fields)>=2 and fields[0][0:1] in ("i"," "):
            name=fields[-2] if len(fields)>2 else fields[0].lstrip("i ")
            rows.append({"manager":"fink","type":"package","name":name,"version":fields[-1]})
    return rows

def all_managers(): return homebrew()+macports()+fink()
