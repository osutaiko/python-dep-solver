import argparse
from pathlib import Path
import json
import sys
import subprocess

sys.path.insert(0, str(Path(__file__).parent.parent / "pruning"))
from main_pruning import run_pruning

import parse
import solver

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        print(f"[ERROR] Failed to load JSON: {path}")
        exit(1)

def solve_project(reqs_txt, dep_space):
    requirements = parse.load_reqs_txt(reqs_txt)
    proj_constraints = parse.parse_reqs(requirements)
    required_packages = parse.get_all_package_names(requirements)
    # print(json.dumps(proj_constraints))

    missing_pkgs = [pkg for pkg in proj_constraints if pkg not in dep_space]

    if missing_pkgs:
        print(f"[ERROR] Missing packages in dependancy space (run precompute.py first): {missing_pkgs}")
        exit(1)

    print("Running pruning preprocessing...")
    result = run_pruning(
        proj_constraints=proj_constraints,
        required_packages=required_packages,
        visualize=False,
        save_files=True
    )

    print(f"Pruning completed:")
    if result['dep_space_req'] is not None:
        print(f"  - dep_space_req.json: {len(result['dep_space_req'])} packages")
    print(f"  - dep_space_clean.json: {len(result['dep_space_clean'])} packages")
    print(f"  - precomputed.json: {len(result['precomputed_dep_space'])} packages")
    print(f"    (Fixed: {len(result['fixed_versions'])}, Constrained: {len(result['constrained_versions'])})")

    dep_space_pruned = result['dep_space_clean']
    return solver.solve(proj_constraints, dep_space_pruned)

def main():
    arg_parser = argparse.ArgumentParser(description="Dependency Solver")
    arg_parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="Path to requirements.txt",
    )
    arg_parser.add_argument(
        "--dep-space",
        type=str,
        required=True,
        help="Path to dependency space JSON",
    )
    args = arg_parser.parse_args()

    req_path = Path(args.file)
    if not req_path.exists():
        print(f"[ERROR] File not found: {req_path}")
        return

    dep_space = load_json(args.dep_space)

    solution = solve_project(req_path, dep_space)
    #print("Solution found!")
    #print(json.dumps(solution, indent=2))

    print("\nRunning GA solver...")

    # requirements 경로로부터 프로젝트 결과 디렉토리 계산
    # data/requirements/NeurIPS/2023/BELLE.txt
    # -> dep_space_result/NeurIPS/2023/BELLE/
    rel = req_path.relative_to("data/requirements").with_suffix("")
    project_dir = Path("dep_space_result") / rel

    dep_space_req = Path("data/dep_space_req.json")
    hard_constraints = project_dir / "dep_space_r.json"

    if not dep_space_req.exists():
        print(f"[ERROR] Missing file: {dep_space_req}")
        sys.exit(1)

    if not hard_constraints.exists():
        print(f"[ERROR] Missing file: {hard_constraints}")
        sys.exit(1)

    ga_cmd = [
        sys.executable,
        "ga/ga6.py",
        "--dep-space", str(dep_space_req),
        "--hard-constraints", str(hard_constraints),
        "--population-size", "250",
        "--generations", "250",
        "--python-versions", "3.9",
        "--output", "results/ga6_test_strong.json",
    ]

    print("[GA CMD]")
    print(" ".join(ga_cmd))

    try:
        completed = subprocess.run(
            ga_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=True,
        )

        print("\n[GA OUTPUT]")
        print(completed.stdout)

    except subprocess.CalledProcessError as e:
        print("\n[ERROR] GA solver failed")
        print(e.stdout)
        sys.exit(1)
    
if __name__ == "__main__": 
    main()

   