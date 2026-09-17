"""On-demand binary lookups with a TTL cache. Fallback only.

Catalog data first: this fills targets whose relation carries no binaries
(unknown). Probes only the unknown; failures stay unknown, never block.
Cache lives at ~/.cache/macpkg-migrate/binaries.json with a 7-day TTL.
"""
import json
import os
import re
import subprocess
import time
import urllib.request

CACHE_TTL = 7 * 24 * 3600
BINDIST_BASE = "http://bindist.finkmirrors.net"
BINDIST_TARGETS = (("10.14", "x86_64"), ("10.15", "x86_64"))
ARCHIVE_FILENAME = re.compile(r"\.((darwin_\d+)\.(arm64|x86_64|ppc|i386))\.tbz2(?=[\"'<\s])")


def cache_file():
    root = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
    return os.path.join(root, "macpkg-migrate", "binaries.json")


def load_cache(path=None):
    try:
        with open(path or cache_file()) as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_cache(data, path=None):
    path = path or cache_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        json.dump(data, handle, sort_keys=True)


def fresh(entry, now=None):
    return bool(entry) and (now if now is not None else time.time()) - entry.get("seen", 0) < CACHE_TTL


def brew_bottle_tags(name, run=subprocess.run):
    """Bottle tags for a formula via local brew (fast, no network beyond brew)."""
    try:
        result = run(["brew", "info", "--json=v2", "--formula", name], capture_output=True, text=True)
        if result.returncode:
            return []
        formulae = json.loads(result.stdout).get("formulae", [])
        files = ((formulae[0].get("bottle") or {}).get("stable") or {}).get("files") or {} if formulae else {}
        return sorted(files)
    except (OSError, ValueError, IndexError, KeyError):
        return []


def macports_platforms(name, fetch=None):
    """Platform tokens from the per-port archive page."""
    request = urllib.request.Request(
        f"https://packages.macports.org/{name}/", headers={"User-Agent": "macpkg-migrate"})
    opener = fetch or (lambda request: urllib.request.urlopen(request, timeout=60))
    try:
        with opener(request) as response:
            html = response.read().decode("utf-8", "replace")
    except OSError:
        return []
    return sorted({match.group(1) for match in ARCHIVE_FILENAME.finditer(html)})


def bindist_names(os_tree, arch, fetch=None):
    """Package names with bindist debs for one OS tree and architecture."""
    request = urllib.request.Request(
        f"{BINDIST_BASE}/{os_tree}/dists/stable/main/binary-darwin-{arch}/Packages",
        headers={"User-Agent": "macpkg-migrate"})
    opener = fetch or (lambda request: urllib.request.urlopen(request, timeout=120))
    try:
        with opener(request) as response:
            text = response.read().decode("utf-8", "replace")
    except OSError:
        return set()
    names = set()
    for line in text.splitlines():
        if line.startswith("Package:"):
            names.add(line.split(":", 1)[1].strip())
    return names


def ensure_binaries(relations, cache_path=None, brew_run=subprocess.run, fetch=None, progress=None, now=None):
    """Fill empty target binaries in place; unknown stays unknown on failure."""
    now = now if now is not None else time.time()
    cache = load_cache(cache_path)
    changed = False

    def cached(key, probe):
        nonlocal changed
        entry = cache.get(key)
        if fresh(entry, now):
            return entry["tokens"]
        tokens = probe()
        cache[key] = {"tokens": tokens, "seen": now}
        changed = True
        return tokens

    bindist_indexes = {}
    for relation in relations:
        target = relation.get("target") or {}
        if target.get("binaries"):
            continue
        manager = target.get("manager")
        name = target.get("native_name")
        package_type = target.get("package_type")
        if not name:
            continue
        if manager == "homebrew" and package_type == "cask":
            target["binaries"] = ["any"]
        elif manager == "homebrew":
            target["binaries"] = cached(f"brew/{name}", lambda: brew_bottle_tags(name, brew_run))
        elif manager == "macports":
            target["binaries"] = cached(f"macports/{name}", lambda: macports_platforms(name, fetch))
        elif manager == "fink":
            tokens = []
            for os_tree, arch in BINDIST_TARGETS:
                index_key = f"bindist/{os_tree}/{arch}"
                entry = cache.get(index_key)
                if not fresh(entry, now):
                    entry = {"names": sorted(bindist_names(os_tree, arch, fetch)), "seen": now}
                    cache[index_key] = entry
                    changed = True
                if name in entry.get("names", []):
                    tokens.append(f"{os_tree}/binary-darwin-{arch}")
            target["binaries"] = sorted(tokens)
        if progress and not target.get("binaries") and manager in ("macports", "fink"):
            progress(f"Note: no recorded binary for {manager}:{name}; install may build from source.")
    if changed:
        try:
            save_cache(cache, cache_path)
        except OSError:
            pass
    return relations
