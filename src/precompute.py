import json
import time
import subprocess

import utils
import parse
import sys

REQ_TXTS_DIR = utils.DATA_DIR / "requirements"
DEP_SPACE_PATH = utils.DATA_DIR / "dep_space.json"


def load_all_packages(req_file=None):
    pkgs = set()
    files = [utils.DATA_DIR / "requirements" / req_file] if req_file else REQ_TXTS_DIR.glob("*.txt")
    for req_file in files:
        for line in open(req_file, "r"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-e "):
                continue
            pkgs.add(parse.extract_pkg_name(line)[0])
    return sorted(pkgs)


def run_conda_cmd(package):
    try:
        result = subprocess.run(
            ["conda", "run", "-n", "base", "conda", "search", package, "--info", "--json"],
            capture_output=True,
            text=True,
        )
    except:
        print(f"[ERROR] conda search: {package} failed")
        return [], []
    
    # print(result.stdout, result.stderr)
    data = json.loads(result.stdout)

    if package not in data:
        return [], []
    
    extracted_data = []
    all_deps = set()

    for entry in data[package]:
        depends_dict = {}
        for dep, conds in (utils.parse_constraint_str(s) for s in entry["depends"]):
            depends_dict[dep] = conds
            all_deps.add(dep)

        constrains_dict = {}
        for dep, conds in (utils.parse_constraint_str(s) for s in entry["constrains"]):
            constrains_dict[dep] = conds

        extracted_data.append({
            "version": entry["version"],
            "depends": depends_dict,
            "constrains": constrains_dict,
        })

    return extracted_data, list(all_deps)


def precompute(req_file=None):
    # load existing dep_space
    if DEP_SPACE_PATH.exists():
        with open(DEP_SPACE_PATH, "r") as f:
            dep_space = json.load(f)
        print(f"Loaded existing dep_space with {len(dep_space)} packages")
    else:
        dep_space = {}

    if req_file:
        print(f"Loading packages in {req_file} ...")
    else:
        print("Loading packages in data/*.txt ...")

    packages = load_all_packages(req_file)
    print(f"Found {len(packages)} packages")

    deps_prc_queue = list(packages)
    deps_done = set(dep_space.keys())

    while deps_prc_queue:
        pkg = deps_prc_queue.pop()

        if pkg in deps_done:
            # print(f"Skipping (cached): {pkg}")
            continue

        print(f"Processing: {pkg}")
        deps_done.add(pkg)

        metadata, child_deps = run_conda_cmd(pkg)
        if not metadata:
            print(f"[WARNING] {pkg}: no conda metadata")
            if pkg not in dep_space:
                dep_space[pkg] = {}
            continue
        
        dep_space[pkg] = {}

        for m in metadata:
            ver = m["version"]
            dep_space[pkg][ver] = {
                "depends": m["depends"],
                "constrains": m["constrains"],
            }
        for c in child_deps:
            if c not in deps_done:
                deps_prc_queue.append(c)

        time.sleep(0.05)

    with open(DEP_SPACE_PATH, "w") as f:
        json.dump(dep_space, f, indent=2)
    print(f"Saved dependency space to {DEP_SPACE_PATH}")


if __name__ == "__main__":
    req_file = sys.argv[1] if len(sys.argv) > 1 else None
    precompute()