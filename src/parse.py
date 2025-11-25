import subprocess
import pathlib
import re
import json

import utils

def load_reqs_txt(path):
    deps = []
    with open(path, 'r') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-e "):
                continue
            deps.append(line)
    return deps

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
        print(f"[WARN] conda cannot find package: {package}")
        return []
    
    extracted_data = [{
        'version': entry['version'], 
        'depends': [utils.parse_constraint_str(s) for s in entry['depends']], 
        'constrains': [utils.parse_constraint_str(s) for s in entry['constrains']],
    } for entry in data[package]]

    return extracted_data

def parse_reqs(requirements):
    proj_constraints = {}
    dep_space = {}

    for req in requirements:
        req_clean = re.sub(r"\[.*?\]", "", req).strip()
        if not utils.is_conda_pkg(req_clean):
            print(f"[WARNING] not a conda package: {req_clean}")
            continue
        
        req_norm = re.sub(r"([<>=!~]=?|==)", r" \1", req_clean)
        pkg = re.split(r"[<>=!~]+", req_clean)[0].strip()
        proj_constraints[pkg] = utils.parse_constraint_str(req_norm)['conds']
        dep_space[pkg] = run_conda_cmd(pkg)

    return proj_constraints, dep_space
    