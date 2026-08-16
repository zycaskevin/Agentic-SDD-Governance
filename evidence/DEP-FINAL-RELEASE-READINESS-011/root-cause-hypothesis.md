# Root Cause Hypothesis

## Hypothesis

The remaining blockers were separate contract gaps rather than one implementation defect: JSON state was treated as enough terminal proof, escalation rendering was not exact-authority-bound, first-consumer verification assumed a governed Base, and historical Proof metadata was not continuously migrated.

## Supporting evidence

The complete Security and Autonomy audits reproduced every Red case independently. Permanent tests now fail if process control, package binding, signature revalidation, trusted first-consumer policy, portable Proof association, or structured CI errors regress.

## Contradicting evidence

L0/L1 routine engineering, trusted L2 reuse, exact L3 consumption, rollback, package installation, Doctor, and the offline pilot were already Green on the baseline; the repair must preserve those paths.

## Falsification test

Re-run the hostile cases with a locally forged `completed` row, mismatched package payload, same-UID first-consumer trust file, duplicate UAT, malformed exemption, and every tracked Proof DEP.

## Conclusion

Confirmed. The Green matrix rejects forged or mismatched authority, deduplicates owner interaction, and keeps routine engineering autonomous.
