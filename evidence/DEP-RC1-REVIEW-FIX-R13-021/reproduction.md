# Reproduction

## Expected

An independent reviewer must be able to validate the candidate with the exact trusted Base verifier. Every commit after the atomic rollback reference and before the reviewed Head must remain inside the Base verifier's `evidence/**` allowance, and the Merge Gate must be added only after that Head is fixed. The isolated virtual environment that runs the complete publish-workflow test suite must install both hash-locked governance and release requirements so `packaging` is available to the release-helper tests.

## Actual

Independent review of PR #34 withheld the protected-file receipt. The exact Base verifier returned exit 3 with `rollback record is missing or incomplete`: old `.sddgov/merge-gate.json` commits were interleaved between R12's atomic rollback reference and reviewed Head. Separately, a fresh virtual environment containing only `requirements-governance.lock` failed during complete test discovery with `ModuleNotFoundError: packaging`; the publish workflow constructed that same incomplete environment.

## Deterministic steps

1. Check out PR #34 Gate Head `6a680814aef063e8083f0958e3f5473671e3091f` in a fresh clone and load `src/sddgov` from trusted Base `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`.
2. Run Base `merge verify --base-ref 1a5a0b214eccc2b9edd076fd5e2f222c4a456725 --skip-local-checks`; observe exit 3. The rollback parser, range, and digest pass, while Base `_rollback_ref_is_cleanly_revertible` is false because non-Evidence gate commits occur before reviewed Head.
3. Create a fresh virtual environment, install only `requirements-governance.lock`, and run `python -m unittest discover -s tests -v`; observe `tests/test_release_bundle.py` fail to import `packaging`.
4. Run the strengthened workflow-contract assertion on the pre-fix source; observe that the isolated validate step does not install `requirements-release.lock` before the full suite.
5. Rebuild the candidate as one product commit directly above Base, replay only `evidence/**` audit commits, install both locks in the isolated workflow environment, and rerun the complete proof matrix.

## Environment and preconditions

The independent review used a clean clone, exact GitHub refs, and a repository-external hash-locked reviewer environment. The R13 implementation is commit `096624a529dea88d091777c8012bbdba3346cdbe`, whose sole parent is trusted Base `1a5a0b214eccc2b9edd076fd5e2f222c4a456725`. Inputs are source code, synthetic fixtures, and repository metadata only; no credential, private key, real customer/patient data, privileged Broker install, or public release is involved.
