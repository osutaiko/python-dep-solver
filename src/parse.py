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
            if not line:
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
    extracted_data = [{
        'version': entry['version'], 
        'depends': [utils.parse_constraint_str(s) for s in entry['depends']], 
        'constrains': [utils.parse_constraint_str(s) for s in entry['constrains']],
    } for entry in data[package]]

    print(json.dumps(extracted_data, indent=2))
    return extracted_data

def get_dep_space(requirements):
    space = {}
    for req in requirements:
        req = re.sub(r"\[.*\]", "", req)
        pkg = re.split(r"[<>=!~]+", req)[0]
        space[pkg] = run_conda_cmd(pkg)
    return space
    