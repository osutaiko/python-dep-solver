import re

import utils

def extract_pkg_name(req):
    req = req.split("@")[0]
    req = re.sub(r"\[.*?\]", "", req)
    req = req.strip()

    m = re.split(r"([<>=!~]+.*)", req, maxsplit=1)
    pkg = m[0].strip()

    if len(m) > 1:
        constraint_str = m[1].strip()
    else:
        constraint_str = ""
    return pkg, constraint_str

def load_reqs_txt(path):
    deps = []
    with open(path, 'r') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-e "):
                continue
            deps.append(line)
    return deps

def parse_reqs(requirements):
    proj_constraints = {}
    for req in requirements:
        pkg, constraint_str = extract_pkg_name(req)
        dep, conds = utils.parse_constraint_str(f"{pkg} {constraint_str}".strip())
        proj_constraints[dep] = conds
    return proj_constraints
    