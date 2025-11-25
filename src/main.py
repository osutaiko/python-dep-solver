import argparse
from pathlib import Path
import datetime
import json

import parse
import solver

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"

def solve_project(reqs_txt):
    project_name = reqs_txt.stem
    requirements = parse.load_reqs_txt(reqs_txt)
    dep_space = parse.get_dep_space(requirements)
    # print(json.dumps(dep_space))
    solution = solver.solve(dep_space)

    return solution

def main():
    arg_parser = argparse.ArgumentParser(description="Dependency Solver")
    arg_parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="Run solver on a specified requirements.txt file (path)",
    )
    args = arg_parser.parse_args()

    req_path = Path(args.file)
    if not req_path.exists():
        print(f"[ERROR] File not found: {req_path}")
        return

    solution = solve_project(req_path)
    print(json.dumps(solution, indent=2))
    
if __name__ == "__main__": 
    main()