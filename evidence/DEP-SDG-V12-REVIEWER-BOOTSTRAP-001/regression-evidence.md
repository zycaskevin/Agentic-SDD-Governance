# Regression Evidence

## Regression test added or strengthened

Added eleven tests for external owner-only identity creation, overwrite prevention, Repo-local rejection, exact Receipt acceptance, dirty checkout rejection, Builder identity rejection, broad-permission rejection for keys and trust stores, explicit Review verdict, public/private-key mismatch, and Repo-bounded Merge gate input.

## Related tests executed

Targeted RED failed with missing module before implementation. Targeted Green `PYTHONPATH=src python3 -m unittest tests.test_reviewer -v` passed 11/11 after security review. Complete regression `PYTHONPATH=src python3 -m unittest discover -s tests -v` passed 94/94.

## Unaffected paths sampled

Existing autonomy, L3 one-use approval, Merge Gate tamper checks, DEP/Redaction, CI Cost Guard, installer, artifact integrity, and benchmark paths remain in the complete regression suite.
