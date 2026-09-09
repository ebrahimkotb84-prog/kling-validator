import hashlib
import pathlib
import unittest

import validator

ROOT = pathlib.Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "candidate_baseline.txt"
EXPECTED_SHA = "b94f9ad3f37ba8740477cf8337343f5b9f55d66e832b0c893a6ada6b0de1d639"


class ValidatorTests(unittest.TestCase):
    def test_baseline_sha_is_locked(self):
        data = CANDIDATE.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), EXPECTED_SHA)

    def test_baseline_passes_all_t01_to_t11(self):
        text = CANDIDATE.read_text(encoding="utf-8")
        results = validator.validate(text)
        self.assertEqual(set(results), {f"T{i:02d}" for i in range(1, 12)})
        self.assertTrue(all(results.values()), results)

    def test_each_mutation_fails_its_designated_test(self):
        mutations = validator.generate_mutations(CANDIDATE.read_text(encoding="utf-8"))
        self.assertEqual(set(mutations), {f"T{i:02d}" for i in range(1, 12)})
        for test_id, mutated in mutations.items():
            results = validator.validate(mutated)
            self.assertFalse(results[test_id], f"{test_id} mutation did not fail its designated test")

    def test_mutation_failure_is_not_blanket_hash_rejection(self):
        base = CANDIDATE.read_text(encoding="utf-8")
        for test_id, mutated in validator.generate_mutations(base).items():
            results = validator.validate(mutated)
            self.assertFalse(results[test_id])
            unrelated = [v for k, v in results.items() if k != test_id]
            self.assertTrue(any(unrelated), f"{test_id} mutation caused only blanket rejection")


if __name__ == "__main__":
    unittest.main(verbosity=2)
