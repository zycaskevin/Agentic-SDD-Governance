# Root Cause Hypothesis

## Hypothesis

R18 left eight adjacent trust-boundary gaps: cleanup was not descriptor-bound,
public report writers could follow symlinks, platform aliases were inconsistent,
Darwin/WSL paths escaped redaction, installed-wheel health stopped before EOF,
withdrawal matching was DEP-wide, and Darwin native package proof was incomplete.

## Supporting evidence

The independent R18 reviewer reproduced replacement deletion, benchmark
symlink overwrite, missing Darwin/WSL masking, delayed extra Broker bytes being
accepted, an unregistered withdrawal error being suppressed, and Darwin system
aliases rejected by release walkers. CodeRabbit skipped the 312-file change.

## Contradicting evidence

R18's full unit, Linux native, package, and rollback matrices were Green. That
narrows the defects to untested publication, normalization, redaction, and
proof-selection edges without falsifying the reproduced failures.

## Falsification test

Exercise a later-writer cleanup race, leaf/parent symlink outputs, Darwin/WSL
variants across chunks, bytes after `READY\n`, and an unregistered artifact
beside a registered withdrawal; then run source and installed-wheel native
proof on Linux and macOS.

## Conclusion

Confirmed. R19 centralizes exact platform aliases, reuses descriptor-relative
ownership cleanup, makes report creation exclusive/no-follow, reads health to
EOF under one deadline, binds withdrawals to exact artifacts, and expands
hosted native package proof.
