# Fix Scope

## Smallest sufficient change

Add a descriptor-owning directory abstraction and route release enumeration, opening, copying, hashing, archive creation, output creation, and recursive inventory through retained descriptors. Move Evidence size enforcement ahead of buffering and share descriptor-relative owned-generation cleanup. Tighten the specifically reviewed CI, environment, benchmark, README, rollback-runbook, service parity, and fresh-wheel contracts.

## Files or components in scope

`scripts/{release_files,prepare_release_bundle,fresh_wheel_smoke,check_release_environment,benchmark_monorepo_rollback}.py`; `src/sddgov/{ci_guard,evidence,fs_security,redaction,merge_gate}.py`; canonical/package/installed rollback and service resources; README copies; Work Package; and focused unit/repository-contract tests.

## Explicit non-scope

No TestPyPI/PyPI upload, GitHub Release, protected-environment/ruleset mutation, Owner key creation, real L3 approval, root service installation, WSL2/macOS target-host rehearsal, production mock Broker, affected-path-only rollback substitution, independent-reviewer self-signing, or review-thread reply/resolution.

## Blast radius

Release-bundle and fresh-wheel filesystem handling, Evidence input/cleanup safety, CI contract validation, GitHub release-environment inspection, benchmark reporting, operator documentation, and packaged-resource parity. Cryptographic receipt schemas, action risk levels, trusted Base, and Production authority boundaries are unchanged.
