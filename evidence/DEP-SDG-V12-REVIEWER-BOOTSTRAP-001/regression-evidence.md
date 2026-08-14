# Regression Evidence

## Regression test added or strengthened

Added thirteen Reviewer tests for external owner-only identity creation, overwrite prevention, Repo-local rejection, exact Receipt acceptance, dirty checkout rejection, Builder identity rejection, broad-permission rejection for keys and trust stores, explicit Review verdict, independently selected Base, unsupported key normalization, public/private-key mismatch, and Repo-bounded Merge gate input. Merge regression also proves an external bootstrap store cannot replace an active base-anchored Reviewer.

## Related tests executed

Targeted RED failed with missing module before implementation. Targeted Green `PYTHONPATH=src python3 -m unittest tests.test_reviewer -v` passed 13/13 after security review. Complete regression `PYTHONPATH=src python3 -m unittest discover -s tests -v` passed 100/100 at implementation commit `83cc5a4abdb1ca33efd0888bb84b845f92ed7347`.

## Unaffected paths sampled

Existing autonomy, L3 one-use approval, Merge Gate tamper checks, DEP/Redaction, CI Cost Guard, installer, artifact integrity, and benchmark paths remain in the complete regression suite.
