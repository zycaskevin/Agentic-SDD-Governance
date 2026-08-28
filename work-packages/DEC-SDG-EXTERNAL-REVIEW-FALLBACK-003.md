# Decision: automated review is advisory, not sole merge authority

Decision ID: `DEC-SDG-EXTERNAL-REVIEW-FALLBACK-003`

Status: approved product direction

Decision date: 2026-08-29 Asia/Taipei

Decision source: after observing that GitHub reported CodeRabbit success while
the provider explicitly skipped review, the Owner instructed the Agent to begin
the bounded fallback adjustment.

## Decision

1. Valid findings from a configured automated reviewer must be verified, fixed,
   and rechecked.
2. A status that explicitly skipped review is not accepted as review evidence.
3. One automatic attempt is allowed for each exact revision. If the provider
   skips or is unavailable, the signed independent reviewer receipt, full Merge
   Gate, and hosted CI are the sufficient bounded fallback.
4. An external review vendor is not a sole authority and its outage never
   creates Owner relay work, login ceremonies, paid-plan escalation, or
   indefinite retries.

## Safety invariant

The fallback does not remove independent review, exact refs, Local Green,
Evidence, rollback, protected-file receipt, or hosted CI. It only removes the
external provider as a single point of availability.

## Reopen conditions

Reopen only if the fallback permits an independently confirmed defect that an
available automated reviewer would have blocked, or repository policy makes a
specific provider a legally required control.
