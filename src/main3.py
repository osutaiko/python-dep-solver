import argparse
from pathlib import Path
import json
import sys

import shutil

sys.path.insert(0, str(Path(__file__).parent.parent / "pruning"))
from main_pruning import run_pruning

import parse
import solver

def get_output_dir(req_path: Path) -> Path:
    """
    data/requirements/CVPR/2022/CRIS.txt
    -> dep_space_result/CVPR/2022/CRIS/
    """
    rel = req_path.relative_to("data/requirements")
    return Path("dep_space_result") / rel.with_suffix("")

def copy_pruning_outputs(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    files = [
        Path("data/dep_space_clean.json"),
        Path("data/dep_space_req.json"),
        Path("data/precomputed.json"),
    ]

    for f in files:
        if f.exists():
            shutil.copy2(f, output_dir / f.name)
        else:
            print(f"[WARN] File not found, skip: {f}")    

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

    output_dir = get_output_dir(req_path)
    copy_pruning_outputs(output_dir)

    print("Solution found!")
    print(json.dumps(solution, indent=2))
    
if __name__ == "__main__": 
    main()