import subprocess
import pathlib
import re

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
            ["conda", "search", package, "--info", "--json"],
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout).get(package, [])
    except:
        print(f"[ERROR] conda search: {package} failed")
        return []

def get_dep_space(requirements):
    space = {}
    for req in requirements:
        req = re.sub(r"\[.*\]", "", req)
        pkg = re.split(r"[<>=!~]+", req)[0]
        space[pkg] = run_conda_cmd(pkg)
    return space
    