#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pruning

def run_pruning(dep_space_path=None, proj_constraints=None, required_packages=None, output_dir=None, visualize=True, save_files=True):
    if dep_space_path is None:
        dep_space_path = Path(__file__).parent.parent / "data" / "dep_space.json"
    else:
        dep_space_path = Path(dep_space_path)

    if output_dir is None:
        output_dir = Path(__file__).parent / "results"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(exist_ok=True)

    with open(dep_space_path) as f:
        dep_space = json.load(f)

    result = pruning.preprocess_dependencies(
        dep_space,
        proj_constraints=proj_constraints,
        required_packages=required_packages,
        visualize=visualize,
        output_dir=str(output_dir),
        save_clean=save_files
    )
    return result


def main():
    print("Running pruning preprocessing...")
    result = run_pruning(
        visualize=True,
        save_files=True
    )

    print(f"\nPruning Completed:")
    print(f"  Packages in dep_space_clean: {len(result['dep_space_clean'])}")
    print(f"  Fixed versions (excluded): {len(result['fixed_versions'])}")
    print(f"  Constrained versions (excluded): {len(result['constrained_versions'])}")

if __name__ == "__main__":
    main()
