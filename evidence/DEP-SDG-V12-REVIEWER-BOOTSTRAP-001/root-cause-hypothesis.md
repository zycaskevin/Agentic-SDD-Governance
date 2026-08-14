# Root Cause Hypothesis

## Hypothesis

The Merge Gate could verify an independently signed Receipt, but SDG provided no safe executable capability for the independent host to create its identity, export public trust, or sign the exact gate. The adapter also did not explicitly route a Reviewer to such a playbook.

## Supporting evidence

`src/sddgov/merge_gate.py` verifies public keys and signatures, while the CLI previously exposed only `merge digest|gate-digest|verify`. The first GB10 Hermes Pilot therefore improvised and asked the product owner for key material.

## Contradicting evidence

The existing cryptographic verification, candidate-key rejection, exact digest binding, and 83 tests were Green. The defect is the missing independent-host execution path, not a failure of the verifier itself.

## Falsification test

Add tests that require external owner-only identity creation, reject Repo-local/dirty/mismatched/Builder signing attempts, and accept a generated Receipt through the existing Merge verifier.

## Conclusion

Confirmed. The targeted test initially failed because `sddgov.reviewer` did not exist; the bounded implementation now passes all eleven Reviewer bootstrap/signing tests.
