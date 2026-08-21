# Root Cause Hypothesis

## Hypothesis

The failures came from boundary contracts being implemented independently: the release policy parser ignored API completeness metadata; release scripts duplicated divergent path helpers; Broker request framing assumed client EOF; Broker permission code requested a platform-unsupported no-follow chmod; private-key streaming retained only complete BEGIN/END prefixes; fresh smoke confused source validation with installed validation; and the demo selected any CLI on `PATH` instead of binding a source checkout to its own module. Review metadata also relied on a UUID/numeric URL representation that generic redaction could not preserve.

## Supporting evidence

The targeted Red suite reproduced each condition independently. The production response shape includes `total_count`; the shared helper test proves `expanduser()` must precede stat; the Broker no-EOF test blocks before the newline fix; the native Linux permission probe fails at the no-follow chmod; the fragmented marker test publishes the synthetic body before the fail-closed rule; static and fresh-wheel evidence show no installed `validate`; and the clean clone imports the older global CLI until `PYTHONPATH` is explicitly bound to checkout `src`. GitHub API readback maps PR 25/26 to stable `PRR_...` nodes and exact inline URLs.

## Contradicting evidence

The existing trusted-Base, signature, nonce, exact-tree, size-limit, output-transaction, and offline hash inventory controls remained fail-closed. The new wheel passed its pilot even while the source demo failed, narrowing that case to interpreter/source selection. The review evidence redactor correctly redacted the numeric portion of a CodeRabbit run UUID while leaving review nodes and `discussion_r...` URLs intact, confirming that the new authoritative identity representation is robust rather than a redaction bypass.

## Falsification test

Run the targeted regressions and full suite from the exact implementation commit; execute the demo from a clean clone without `.venv`; build the wheel/sdist, create the exact offline bundle, and require Codex/Hermes installed validation; run Local Green; and revert the implementation in a disposable clone. The hypothesis is false if a later policy page is accepted, request framing waits for EOF, startup still uses unsupported chmod flags, fragmented key material is published, source demo resolves the global CLI, fresh validation is absent, or the revert result differs from the exact Base tree.

## Conclusion

Confirmed. R5 centralizes release file validation, makes API completeness and Broker framing explicit, replaces the unsupported socket call while retaining identity checks, fails closed on a split delimiter, adds installed-tree validation, binds source demos to source code, and records stable review nodes plus authoritative inline URLs. Each original boundary now has a regression test or executable runbook control.
