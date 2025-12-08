import re
from pathlib import Path

import requests
from packaging.version import Version

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"

INEQ_OPS = ["==", "!=", ">=", "<=", ">", "<"]


def parse_raw_operator(raw_cond):
    m = re.compile(r"^(==|!=|>=|<=|>|<)(.*)$").match(raw_cond)
    if not m:
        return None, None
    op, ver = m.group(1), m.group(2)
    return op, ver


def expand_wildcard(ver):
    if not ver.endswith(".*"):
        return None

    base = ver[:-2]
    parts = base.split(".")
    if any(p == "*" for p in parts):
        return None
    if len(parts) > 2:
        return None

    while len(parts) < 2:
        parts.append("0")

    try:
        major = int(parts[0])
        minor = int(parts[1])
    except ValueError:
        return None

    lower = f"{major}.{minor}.0"
    upper = f"{major}.{minor + 1}.0"

    return [{"op": ">=", "ver": lower}, {"op": "<", "ver": upper}]


def parse_constraint_str(s):
    toks = s.split(" ", 1)
    toks = [t for t in toks if not t.startswith("*")]
    dep = toks[0].lower()

    if len(toks) == 1:
        return dep, []

    raw_conds = toks[1].split(",")
    conds = []

    for raw_cond in raw_conds:
        raw_cond = raw_cond.strip().split(" ")[0]

        op, ver = parse_raw_operator(raw_cond)
        if not op:
            op = "=="
            ver = raw_cond
        ver = ver.lower()

        wc = expand_wildcard(ver)
        if wc:
            wc = [{"op": w["op"], "ver": w["ver"].lower()} for w in wc]
            conds.extend(wc)
        else:
            conds.append({"op": op, "ver": ver})

    return dep, conds


def cmp_v(v1, op, v2):
    if op not in INEQ_OPS:
        print(f"[ERROR] op {op} not in INEQ_OPS")
        return False

    v1 = Version(v1)
    v2 = Version(v2)

    match op:
        case "==":
            return v1 == v2
        case "!=":
            return v1 != v2
        case ">=":
            return v1 >= v2
        case "<=":
            return v1 <= v2
        case ">":
            return v1 > v2
        case "<":
            return v1 < v2

    return False


def get_pypi_all_versions(package_name):
    url = f"https://pypi.org/pypi/{package_name}/json"
    response = requests.get(url)
    data = response.json()
    all_versions = list(data.get("releases", {}).keys())
    return sorted(all_versions)


def get_pypi_version_dependencies(package_name, version):
    url = f"https://pypi.org/pypi/{package_name}/{version}/json"
    response = requests.get(url)
    data = response.json()
    return data["info"].get("requires_dist", [])
