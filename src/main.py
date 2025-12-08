import argparse
from pathlib import Path
import json
import sys

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
    # print(json.dumps(proj_constraints))

    missing_pkgs = [pkg for pkg in proj_constraints if pkg not in dep_space]

    if missing_pkgs:
        print(f"[ERROR] Missing packages in dependancy space (run precompute.py first): {missing_pkgs}")
        exit(1)

    print("Running pruning preprocessing...")
    result = run_pruning(
        proj_constraints=proj_constraints,
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
    print("Solution found!")
    print(json.dumps(solution, indent=2))
    
if __name__ == "__main__": 
    main()