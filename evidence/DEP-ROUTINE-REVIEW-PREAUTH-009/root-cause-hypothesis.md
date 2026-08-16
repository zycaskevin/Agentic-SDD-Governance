# Root Cause Hypothesis

## Hypothesis

SDG classified Review as routine engineering but did not separately define which external review payload and destination are already authorized. Agents therefore had to infer a data-sharing boundary and could conservatively escalate every PR submission.

## Supporting evidence

- The Policy Kernel says Review is not an approval point but does not define a safe external payload.
- The machine policy has no configured-Reviewer sharing contract.
- Codex and Hermes adapters do not distinguish a committed public diff from Private Repo, Secret, or raw Evidence content.
- The observed prompt asked for approval even though the repository and requested review material were already public.

## Contradicting evidence

Existing policy already forbids raw Evidence export and unnecessary L0/L1 approval prompts. Those controls reduce risk but do not tell an Agent when a third-party review submission is eligible.

## Falsification test

The hypothesis is supported if one narrow policy can let eligible configured public review proceed automatically while tests still require fail-closed handling for Private Repo content, sensitive payloads, new vendors/access, and new cost. It is falsified if those boundaries cannot be expressed without broadly authorizing third-party sharing.

## Conclusion

Confirmed. The missing piece is a destination-and-payload contract, not removal of privacy or access gates.
