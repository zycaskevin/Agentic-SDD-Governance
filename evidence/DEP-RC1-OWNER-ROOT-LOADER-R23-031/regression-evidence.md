# Regression Evidence

## Regression test added or strengthened

- The Agent loader still rejects effective UID zero.
- The root Owner loader accepts a simulated root-owned fixed path but rejects non-root callers and every caller-selected path.
- Root Owner card construction succeeds through the Owner loader while the Agent loader is poisoned to fail.
- Existing receipt reuse and A/sign/final local verification succeed with the Agent loader poisoned and prove the Owner loader handles both key and domain lookups.
- Repository-contract coverage prevents production modules outside `autonomy.py` and `owner_approval.py` from supplying a control-plane loader.

## Related tests executed

The focused Agent/Owner/filesystem matrix reports 121 pass plus 1 sandbox skip. After cryptographic receipt import, the complete source suite reports 509 pass plus 14 platform/sandbox skips and no failures; the exact configured Local Green, including stored-decision verification, passes.

## Unaffected paths sampled

Source validation, CI verification, owner-client identity binding, request/Decision Contract self-assumptions, exact validity reuse, fixed outbox modes, and the prior package/native boundaries remain in the verification matrix. The root rehearsal used the exact independently reviewed wheel and a root-custodied post-copy hash check before the Owner choice.

The exact trusted Base independently accepted the authoritative DEP in portable-strict mode and its static rollback predicate accepted the final product commit. An actual revert restored the exact Base non-audit tree and returned Base validation plus 237 tests to Green with 1 expected skip.
