import json,os,shutil,subprocess

def homebrew(run=subprocess.run):
    if shutil.which("brew") is None:
        return []
    try:
        data = json.loads(run(["brew","info","--json=v2","--installed"],capture_output=True,text=True,check=True).stdout)
    except (OSError, subprocess.CalledProcessError, ValueError):
        return []
    result = []
    for item in data.get("formulae",[]):
        if any(x.get("installed_on_request") for x in item.get("installed",[])):
            result.append({"manager":"homebrew","type":"formula","name":item.get("name") or item.get("full_name"),"version":(item.get("installed") or [{}])[-1].get("version","")})
    for x in data.get("casks",[]):
        name = x.get("token") or x.get("name")
        if isinstance(name, list):
            name = name[0] if name else ""
        result.append({"manager":"homebrew","type":"cask","name":name,"version":x.get("version","")})
    return result

def macports(run=subprocess.run):
    port = shutil.which("port")
    if port is None:
        port = "/opt/local/bin/port" if os.path.exists("/opt/local/bin/port") else None
    if port is None:
        return []
    try:
        result = run([port,"installed"],capture_output=True,text=True)
    except OSError:
        return []
    if result.returncode:
        return []
    rows = []
    for line in result.stdout.splitlines():
        fields = line.split()
        # "No ports are installed." trailer is not a port (port names are lowercase).
        if len(fields) >= 2 and fields[0] not in ("The","None","No"):
            rows.append({"manager":"macports","type":"port","name":fields[0],"version":fields[1]})
    return rows

def fink(run=subprocess.run):
    if not shutil.which("fink"):
        return []
    try:
        result = run(["fink","list","-i"],capture_output=True,text=True)
    except OSError:
        return []
    if result.returncode:
        return []
    rows = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0][0:1] in ("i"," "):
            name = fields[-2] if len(fields) > 2 else fields[0].lstrip("i ")
            rows.append({"manager":"fink","type":"package","name":name,"version":fields[-1]})
    return rows

def all_managers(run=subprocess.run): return homebrew(run)+macports(run)+fink(run)
