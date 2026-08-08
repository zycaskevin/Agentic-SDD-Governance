# v0.2.0-experimental Release Notes

## Outcome

This release turns the approved Evidence & Debugging plan into an executable, progressively disclosed governance module. It preserves the verified v0.1 capability baseline (`init`, `validate`, `status`, adapters, profiles, templates, tests) while adding DEP, redaction, evidence gates, telemetry, Work Claim TTL, External Action Queue, and paired benchmark scaffolding.

## Verification performed

- `python -m unittest discover -s tests -v`: 14 tests passed.
- `sddgov validate .`: passed.
- Skill Creator `quick_validate.py`: passed.
- `python -m compileall -q src tests`: passed.
- PEP 517 sdist and wheel build with no runtime dependency downloads: passed.
- Clean wheel installation into an isolated Python 3.14 environment: passed.
- Installed CLI smoke: project init/status, TTL claim, L3 External Action Queue, DEP init/collect/redact: passed.
- Leak scan of the shareable smoke artifact for the injected bearer token and email: no match.

## Important limits

- The Local Redaction Gateway is a conservative MVP, not a legal anonymization certification.
- Screenshots, trace ZIPs, videos, archives, and other binary evidence fail closed until a manually reviewed derivative exists.
- Included benchmark scores are synthetic fixture checks; no superiority claim is allowed.
- The historical v0.1 attachment could not be retrieved byte-for-byte. See `docs/BASELINE_PROVENANCE.md`.
- Public release, license selection, and external claims remain owner decisions.
