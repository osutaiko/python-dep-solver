import json
import time
import subprocess

import utils
import parse

REQ_TXTS_DIR = utils.DATA_DIR / "requirements"
DEP_SPACE_PATH = utils.DATA_DIR / "dep_space.json"


def load_all_packages():
    pkgs = set()
    for req_file in REQ_TXTS_DIR.glob("*.txt"):
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
        return []
    
    # print(result.stdout, result.stderr)
    data = json.loads(result.stdout)

    if package not in data:
        return []
    
    extracted_data = []

    for entry in data[package]:
        depends_dict = {}
        for dep, conds in (utils.parse_constraint_str(s) for s in entry["depends"]):
            depends_dict[dep] = conds

        constrains_dict = {}
        for dep, conds in (utils.parse_constraint_str(s) for s in entry["constrains"]):
            constrains_dict[dep] = conds

        extracted_data.append({
            "version": entry["version"],
            "depends": depends_dict,
            "constrains": constrains_dict,
        })

    return extracted_data


def precompute():
    print("Loading packages in data/*.txt ...")
    packages = load_all_packages()

    print(f"Found {len(packages)} packages")

    dep_space = {}

    for pkg in packages:
        print(f"Processing: {pkg}")
        dep_space[pkg] = {}

        metadata = run_conda_cmd(pkg)
        if not metadata:
            print(f"[WARNING] {pkg}: no conda metadata")
            continue

        for m in metadata:
            ver = m["version"]
            dep_space[pkg][ver] = {
                "depends": m["depends"],
                "constrains": m["constrains"],
            }

        time.sleep(0.05)

    with open(DEP_SPACE_PATH, "w") as f:
        json.dump(dep_space, f, indent=2)
    print(f"Saved dependency space to {DEP_SPACE_PATH}")


if __name__ == "__main__":
    precompute()