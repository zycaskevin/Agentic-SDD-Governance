# Root Cause Hypothesis

## Hypothesis

The rollback contract proves only a tree-level inverse and declares only a Python test module, so installed-governance reconciliation and Doctor are prose rather than an executable post-condition. Separately, CI Cost Guard validates per-workflow safety controls but does not reject an automatic post-merge `push` trigger when the budget is one run.

## Supporting evidence

- The non-Evidence tree comparison returns Green while Doctor returns exit 1.
- Base has `.sddgov/project.json` at experimental.8 and the installed manifest at experimental.7.
- The v2 rollback parser accepts only `git_revert` plus a Python module and does not model reconciliation or Doctor.
- `.github/workflows/governance.yml` listens to both `pull_request_target` and `push: main`.
- GitHub has one successful run for each event on the same Work Package.

## Contradicting evidence

The current `main` installation is healthy, all existing tests pass, both hosted jobs succeeded, and the static rollback tree proof is valid. These facts show that the defects concern recovery completeness and cost enforcement rather than current feature correctness.

## Falsification test

Reject the hypothesis if a closed declarative rollback with reconciliation returns Doctor and its declared tests to Green in a fresh rollback drill, and if CI verification rejects automatic `push` while the one-run/manual-post-merge policy is active.

## Conclusion

Confirmed. The implementation adds the missing executable rollback
post-condition and the missing one-run event constraint without changing
product behavior or expanding authority.
