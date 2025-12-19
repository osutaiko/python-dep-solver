import re
import json
from pathlib import Path
from typing import Dict, List


REQ_PATTERN = re.compile(
    r"""
    ^
    \s*
    (?P<name>[A-Za-z0-9_.\-]+)
    \s*
    (?:
        (?P<op>==|>=|<=|>|<)
        \s*
        (?P<ver>[A-Za-z0-9_.\-]+)
    )?
    \s*
    $
    """,
    re.VERBOSE,
)


def parse_requirements(req_text: str) -> Dict[str, List[dict]]:
    dep_space_r = {}

    for line in req_text.splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        m = REQ_PATTERN.match(line)
        if not m:
            print(f"[WARN] Skip unparsable line: {line}")
            continue

        name = m.group("name")
        op = m.group("op")
        ver = m.group("ver")

        if op and ver:
            dep_space_r[name] = [{"op": op, "ver": ver}]
        else:
            dep_space_r[name] = []

    return dep_space_r


def build_output_path(input_path: Path) -> Path:
    """
    requirements/.../xxx.txt
    -> dep_space_result/.../xxx/dep_space_r.json
    """
    rel = input_path.relative_to("data/requirements")
    out_dir = Path("dep_space_result") / rel.with_suffix("")
    return out_dir / "dep_space_r.json"


def main():
    base = Path("data/requirements")
    TARGET_PREFIXES = [
        "CVPR",
        "NeurIPS",
        "ICLR",
    ]

    req_files = []
    for p in TARGET_PREFIXES:
        req_files.extend((base / p).rglob("*.txt"))

    req_files = sorted(req_files)
    print(f"[INFO] Found {len(req_files)} requirements files")

    for req_path in req_files:
        try:
            print(f"[RUN] {req_path}")

            dep_space_r = parse_requirements(req_path.read_text())
            out_path = build_output_path(req_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)

            with open(out_path, "w") as f:
                json.dump(dep_space_r, f, indent=2)

            print(f"[OK]  -> {out_path}")

        except Exception as e:
            print(f"[ERROR] Failed on {req_path}")
            print(e)


if __name__ == "__main__":
    main()