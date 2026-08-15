# Root Cause Hypothesis

## Hypothesis

The protected inventory covered canonical source and workflows but omitted the bootstrap and installed copies that Codex/Hermes actually load first.

## Supporting evidence

Repository bootstrap instructions route Agents through `AGENTS.md` and `.agents/`, while installer state can use `.agentic-sdd-governance/`; the Base list omitted all three.

## Contradicting evidence

Canonical governance sources such as `skill/`, `policies/`, and `src/sddgov/` were already protected correctly.

## Falsification test

Add the three exact Base patterns and verify representative paths with `_protected_patterns` plus `_is_protected`; existing no-receipt Merge regression proves protected changes fail closed.

## Conclusion

Confirmed. Protection must follow every runtime load path, not only canonical authoring paths.
