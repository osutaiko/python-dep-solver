# python-dep-solver
A metaheuristic Python dependency solver.

## Instructions
0. Setting up a Conda environment may be needed (untested)
1. Put a `requirements.txt` file to solve in `data/requirements/` directory
2. `$ python precompute.py` - Precompute dependency space
3. `$ cd src` - Navigate to src/ directory
4. `$ python main.py --file REQTXT_PATH --dep-space ../data/dep_space.json` - Run GA solver
