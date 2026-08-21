# Root Cause Hypothesis

## Hypothesis

The review failures came from several small boundary mismatches rather than one architectural defect: shell fail-fast behavior ran before the demo renderer; rollback audit exclusions existed in exact-tree comparison but not the descendant allowlist; a transformed Unicode string supplied an index into the original string; schema and runtime validation had diverged; and release smoke isolation did not erase ambient pip configuration. R3 Evidence separately used an inappropriate JSON filename for content whose generic redaction could replace bare numeric values.

## Supporting evidence

The safe PR #25 review capture maps all 11 inline findings to exact files and URLs. Regression tests reproduce the failed demo path, allow only the three declared rollback audit path classes, reject a normal product descendant, preserve `ß` before a private-key marker split across logical lines, reject blank CI exception names, propagate a nested pilot check failure, aggregate Broker `NOT_READY`, and reject an unlisted release-bundle file.

## Contradicting evidence

The existing architecture remained fail-closed: redaction rejected the original full review capture because it contained an overlong incomplete private-key marker; Merge verification still rejected all ordinary post-implementation code/config changes; and the release bundle already required exact hashes. These observations narrow the cause to inconsistent edge handling and Evidence representation, not loss of the trusted-Base model.

## Falsification test

Run the targeted regressions, full 271-test suite, repository validation, CI Guard, Doctor, offline demo, package build/twine, fresh-wheel smoke, and a disposable revert. The hypothesis is false if the demo hides FAIL, an ordinary descendant passes, an allowed audit descendant fails, Unicode text is lost or key material appears, blank exception names validate, inherited pip settings influence installation, or the reverted result tree differs from the declared Base tree.

## Conclusion

Confirmed. The bounded R4 changes make each consumer use one explicit contract and add a regression at the original failure boundary. Historical R3 Evidence remains untouched; its findings are carried forward into this new DEP with text review artifacts, explicit Git object types, and architecture limitations.
