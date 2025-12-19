import unittest
from ga.ga6 import normalize_version, cmp_version, check_one_constraint, run_ga

# File: ga/test_ga6.py

class TestGA6(unittest.TestCase):

    def test_normalize_version(self):
        self.assertEqual(normalize_version("3.10.0a0"), (3, 10, 0))
        self.assertEqual(normalize_version("3.9"), (3, 9))
        self.assertEqual(normalize_version("2.7.18"), (2, 7, 18))
        self.assertEqual(normalize_version("invalid"), (0,))

    def test_cmp_version(self):
        self.assertEqual(cmp_version("3.9", "3.10"), -1)
        self.assertEqual(cmp_version("3.10", "3.10"), 0)
        self.assertEqual(cmp_version("3.11", "3.10"), 1)

    def test_check_one_constraint(self):
        self.assertTrue(check_one_constraint("3.9", ">=", "3.8"))
        self.assertFalse(check_one_constraint("3.9", "<", "3.8"))
        self.assertTrue(check_one_constraint("3.9", "==", "3.9"))
        self.assertFalse(check_one_constraint("3.9", "!=", "3.9"))

    def test_run_ga(self):
        repo = {
            "packageA": {
                "1.0.0": {
                    "depends": {
                        "packageB": [{"op": ">=", "ver": "2.0.0"}]
                    },
                    "constrains": {}
                }
            },
            "packageB": {
                "2.0.0": {
                    "depends": {},
                    "constrains": {}
                }
            }
        }
        best_f, best_py, best_pkgs = run_ga(
            repo,
            python_candidates=["3.8", "3.9", "3.10"],
            pop_size=10,
            n_generations=5,
            seed=42
        )
        self.assertGreater(best_f, 0)
        self.assertIn(best_py, ["3.8", "3.9", "3.10"])
        self.assertIn("packageA", best_pkgs)
        self.assertIn("packageB", best_pkgs)

if __name__ == "__main__":
    unittest.main()