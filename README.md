# python-dep-solver
A metaheuristic Python dependency solver.

## Instructions
0. Setting up a Conda environment may be needed (untested)
1. Put a `requirements.txt` file to solve in `data/requirements/` directory
2. `$ python precompute_pypi.py` - Precompute dependency space (Add package not included in dep_space)
3. `$ cd src` - Navigate to src/ directory
4. `$ python src/main.py --file REQTXT_PATH --dep-space data/dep_space.json` - Run GA solver.

    Example:
   ```bash
   python src/main.py \
     --file data/requirements/NeurIPS/2023/BELLE.txt \
     --dep-space data/dep_space_pypi2.json

## Evaluation
`python src/eval.py --file results/ga6_test_strong_detailed.json --dep data/dep_space_pypi2.json`