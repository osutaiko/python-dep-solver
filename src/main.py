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
    solution = solver.solve(dep_space)

    return solution

def main():
    parser = argparse.ArgumentParser(description="Dependency Solver")
    parser.add_argument(
        "--file",
        type=str,
        help="Run solver on a specified requirements.txt file (path)",
    )
    args = parser.parse_args()

    if args.file:
        req_path = Path(args.file)
        if not req_path.exists():
            print(f"[ERROR] File not found: {req_path}")
            return

        solution = solve_project(req_path)
        print(json.dumps(solution, indent=2))
        return


    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    results_path = RESULTS_DIR / timestamp
    results_path.mkdir(parents=True, exist_ok=True)

    for reqs_txt in DATA_DIR.glob("*.txt"):
        project = reqs_txt.stem
        solution = solve_project(reqs_txt)
        result_file = results_path / f"{project}.json"

        with open(result_file, "w") as f:
            json.dump(solution, f, indent=2)
        print(f"[SOLVED] project {project}")

    print(f"[DONE] Results saved in {results_path}")

if __name__ == "__main__": 
    main()