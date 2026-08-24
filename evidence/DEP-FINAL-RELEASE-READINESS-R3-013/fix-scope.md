# Fix Scope

## Smallest sufficient change

Retain all prior commits, add one commit that reverses both implementation increments to a Base-equivalent non-Evidence boundary, then revert that boundary in one implementation-only commit containing the complete release-readiness candidate.

## Files or components in scope

Git commit topology, the new atomic implementation ref, this rollback DEP, and the final Merge Gate metadata that will select this DEP after independent review.

## Explicit non-scope

No functional source changes, no authority change, no force-push/history rewrite, no trust/GitHub setting mutation, no hosted verification, no Merge, tag, or Release.

## Blast radius

The content tree of the candidate remains unchanged. Only auditable commit topology and Evidence are added so the exact rollback contract can prove complete Base restoration.
