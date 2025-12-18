import argparse
import json
import re

import utils


def parse_version_constraint(op, ver):
    """Handle cases where ver contains operator (data quality issue) or ~= operator."""
    # If ver starts with an operator, extract it
    match = re.match(r"^(~=|==|!=|>=|<=|>|<)(.+)$", ver)
    if match:
        op = match.group(1)
        ver = match.group(2)

    # Handle ~= (compatible release) operator
    if op == "~=":
        # ~=X.Y means >=X.Y, ==X.*
        parts = ver.split(".")
        if len(parts) >= 2:
            # Extract numeric part of minor version
            minor_match = re.match(r"^(\d+)", parts[1])
            if minor_match:
                minor_num = int(minor_match.group(1))
                next_minor = f"{parts[0]}.{minor_num + 1}"
                return [(">=", ver), ("<", next_minor)]
        # Fallback: just use >=
        return [(">=", ver)]

    return [(op, ver)]


def validate_solution(solution_path: str, dep_space_path: str):
    print("Loading files...")
    with open(solution_path, "r", encoding="utf-8") as f:
        sol_data = json.load(f)
    with open(dep_space_path, "r", encoding="utf-8") as f:
        dep_space = json.load(f)

    packages = sol_data.get("packages", sol_data.get("all_packages", {}))
    current_python_ver = sol_data.get("python_version", "3.8")

    errors = []
    print(f"🔍 Validating {len(packages)} packages against Dependency Space...")

    for pkg_name, pkg_ver in packages.items():
        if pkg_ver is None:
            errors.append(f"[{pkg_name}] Version is null/unresolved.")
            continue

        if pkg_name not in dep_space:
            errors.append(f"[{pkg_name}] Not found in dependency space keys.")
            continue

        if pkg_ver not in dep_space[pkg_name]:
            errors.append(
                f"[{pkg_name}] Version '{pkg_ver}' does not exist in dep_space."
            )
            continue

        pkg_meta = dep_space[pkg_name][pkg_ver]
        dependencies = pkg_meta.get("depends", {})

        for dep_pkg, constraints in dependencies.items():
            if dep_pkg == "python":
                target_ver = current_python_ver
            elif dep_pkg in packages:
                target_ver = packages[dep_pkg]
                if target_ver is None:
                    errors.append(
                        f"[{pkg_name} {pkg_ver}] Requires '{dep_pkg}' but its version is null"
                    )
                    continue
            else:
                errors.append(
                    f"[{pkg_name} {pkg_ver}] Requires missing package '{dep_pkg}'"
                )
                continue

            for const in constraints:
                op = const["op"]
                req_ver = const["ver"]

                # Parse and expand constraints (handles ~= and data issues)
                expanded = parse_version_constraint(op, req_ver)
                for exp_op, exp_ver in expanded:
                    if not exp_ver:  # Skip empty version strings
                        continue
                    try:
                        if not utils.cmp_v(target_ver, exp_op, exp_ver):
                            errors.append(
                                f"❌ Conflict: [{pkg_name} {pkg_ver}] requires "
                                f"'{dep_pkg} {op} {req_ver}', but found '{target_ver}'"
                            )
                            break
                    except Exception as e:
                        errors.append(
                            f"⚠️ Parse error: [{pkg_name} {pkg_ver}] constraint "
                            f"'{dep_pkg} {op} {req_ver}': {e}"
                        )
                        break

    if not errors:
        print("\n Valid solution!")
        return True
    else:
        print(f"\n❌ [FAILED] Found {len(errors)} conflicts.")
        for e in errors:
            print(e)
        return False


if __name__ == "__main__":
    # python src/eval.py --file ga_solution.json --dep data/dep_space.json
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--dep", required=True)
    args = parser.parse_args()

    validate_solution(args.file, args.dep)
