import argparse
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "pruning"))
from main_pruning import run_pruning

import parse
import solver

import shutil

def get_output_dir(req_path: Path) -> Path:
    rel = req_path.relative_to("data/requirements")
    # CVPR/2021/qdtrack.txt → CVPR/2021/qdtrack/
    return Path("dep_space_result") / rel.with_suffix("")

def move_pruning_outputs(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    files = [
        "dep_space_req.json",
        "dep_space_clean.json",
        "precomputed.json",
    ]

    cwd = Path.cwd()

    for fname in files:
        src = cwd / fname
        if src.exists():
            shutil.move(str(src), out_dir / fname)

        else:
            print(f"[WARN] {fname} not found in {cwd}")

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

    out_dir = get_output_dir(req_path)
    move_pruning_outputs(out_dir)

    ##try:
    #    rel = req_path.relative_to("data/requirements")
    #except ValueError:
    #    print("[ERROR] requirements file must be under data/requirements/")
    #    return
    

    #out_path = Path("dep_space_result") / rel.with_suffix(".json")
    #out_path.parent.mkdir(parents=True, exist_ok=True)
    solution_path = out_dir / "solution.json"
    with open(solution_path, "w") as f:
        json.dump(solution, f, indent=2)

    print("Solution found!")
    print(json.dumps(solution, indent=2))
    
if __name__ == "__main__": 
    main()