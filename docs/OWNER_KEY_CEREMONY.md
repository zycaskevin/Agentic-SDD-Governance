# Owner Key Ceremony and Recovery Runbook

Owner keys are external trust roots. They authorize bounded L2 product decisions and exact, one-use L3 operations; they must never be generated, stored, backed up, or used inside an Agent workspace.

## Trust domains

Use a different Ed25519 key for every domain whose compromise should have a different blast radius. At minimum, separate:

| Trust domain | Example authority | Must not share a key with |
| --- | --- | --- |
| Development | Staging-only product decisions | Production, release signing |
| Production customer data | Exact MyHermes or clinic operations | Payments, unrelated repositories |
| Payments | Exact live payment operations | Patient/customer data, development |
| Package release | TestPyPI/PyPI release control | Runtime L2/L3 approvals |

Do not make one Owner key the common trust root for every repository. A repository may trust more than one active public key during rotation, but each key ID must identify one domain and one custody policy.

## Ceremony participants and record

For a regulated trust domain, use two people: a custodian operating the signing device and a witness verifying identity, custody, and the machine-verification result in the ceremony record. For a lower-risk domain, one owner may fill both roles, but the record must say so.

Record only non-secret metadata:

- key ID and trust domain;
- algorithm (`Ed25519`), creation time, custodian, witness, and approved signing device;
- SHA-256 fingerprint of the raw 32-byte public key;
- public key in padded Base64 for the trusted approver store;
- backup location identifiers, never recovery secrets;
- activation, next review, rotation, revocation, and destruction dates;
- one synthetic receipt signature/verification result.

Store the ceremony record in the governed audit system. The private key and its recovery material stay in an owner-controlled hardware token, offline encrypted medium, or enterprise password/key manager that the Agent identity cannot access.

## Creation ceremony

1. Start from a clean owner-controlled device with networking disabled when practical.
2. Select a new unique key ID such as `myhermes-production-2026q3`; never reuse an old ID.
3. Generate an Ed25519 key in the approved device or vault. Disable export when the device supports it.
4. Export only the raw 32-byte public key. Run a reviewed ceremony tool that rejects any other length or algorithm, emits padded standard Base64 and the SHA-256 fingerprint, then independently re-exports the public key and makes the machine compare the exact bytes. Preserve the command, tool version, and PASS result.
5. Have the witness confirm the device identity, custodian, trust domain, and recorded machine PASS. Humans do not copy, calculate, compare, or approve digests.
6. Add the public record with status `active` only to the fixed root-controlled `/etc/sddgov/trusted-approvers.json` store, and add the same key ID's exact canonical GitHub repository, exact canonical host-local repository root, and trust domain to `/etc/sddgov/trusted-approver-domains.json`. The separate audience sidecar preserves the trusted Base's approver-record and receipt schema while the current verifier prevents cross-repository replay; candidate-controlled Git configuration alone is not authority. On macOS these logical paths are validated through only the platform-owned `/etc` to `/private/etc` alias; arbitrary symlinks remain forbidden. The Agent rejects `SDDGOV_TRUSTED_APPROVERS_FILE`; migrate legacy deployments by removing that variable and atomically provisioning both reviewed control-plane files. This provisioning is a separate privileged Operational/L3 action, not part of the L2 code decision.
7. Sign a synthetic, non-Production receipt and verify it through SDG. Never use a real customer, patient, payment, or Production payload for ceremony testing.
8. Confirm `sddgov broker doctor --path <repo>` is `READY` from the non-root Agent account before enabling L3 operations.

The trusted store contains public keys only:

```json
{
  "schema_version": "1.0",
  "approvers": [
    {
      "approver_id": "myhermes-production-2026q3",
      "algorithm": "ed25519",
      "public_key": "<REPLACE_WITH_PADDED_BASE64_RAW_32_BYTE_ED25519_PUBLIC_KEY>",
      "status": "active"
    }
  ]
}
```

The angle-bracket value is a deliberately invalid non-key placeholder. Never install this example as a trust store: replace it with machine-exported public bytes and require schema validation plus `sddgov broker doctor` to pass. Doctor fails closed on the placeholder.

The Base-compatible audience sidecar contains no key material:

```json
{
  "schema_version": "1.0",
  "bindings": [
    {
      "approver_id": "myhermes-production-2026q3",
      "repository_id": "github.com/example/myhermes",
      "repository_root": "/srv/myhermes/repository",
      "trust_domain": "myhermes-production-2026q3",
      "status": "active"
    }
  ]
}
```

## Routine signing controls

- The signer displays the complete canonical operation payload, environment, scope, target, effects, expiry, and nonce before signing.
- L3 validity must not exceed 24 hours. Use the shortest practical window.
- Never place a secret value in `operation_payload.parameters`; reference an owner-controlled secret identifier instead.
- Never sign a receipt copied from untrusted chat text without reconstructing and inspecting its typed fields.
- Preserve the signed receipt and Broker consumption audit record under the domain retention policy.

## Bounded Owner approval client

The Owner decides product meaning; the independent Reviewer and machines review code, Evidence, hashes, and Gate state. Do not ask an Owner to edit receipt JSON, calculate a digest, paste a signature, or expose a private-key path.

The Agent-side command can only validate and render a governed request:

```bash
sddgov decision show-product-approval work-packages/DEC-EXACT.request.json --path .
```

The installed package exposes signing through the separate `sddgov-owner` entry point. Run it from an Owner-controlled terminal and an independently installed, reviewed wheel—not from an Agent-driven candidate checkout. The request itself fixes the canonical assumption paths, Owner key ID, validity policy, and reviewed Owner-client source digest; the same client binding must occur exactly once inside the signed decision assumption contract. The CLI provides no overrides for them. It reads the same validated card, binds the exact repository, trust domain, installed source identity, assumptions, and validity, asks for one A/B choice on `/dev/tty`, constructs the receipt, computes the nonce, requests a signature from the matching Ed25519 identity, verifies that signature against both fixed root-controlled stores, and writes a new `0600` receipt. There is no private-key or raw-signature CLI argument.

Start outside the repository, clear Python import injection variables, and invoke the reviewed Owner venv by absolute path:

```bash
cd /owner-controlled/terminal
env -u PYTHONPATH -u PYTHONHOME \
  /absolute/owner-venv/bin/sddgov-owner \
  approve-product work-packages/DEC-EXACT.request.json \
  --output /owner-controlled-outbox/DEC-EXACT.signed.json \
  --path /exact/repository
```

The matching raw Ed25519 identity must already be held by an Owner-controlled SSH agent whose custody policy requires separate confirmation for every signature. An unconstrained Agent-accessible SSH key is not valid Owner custody. `SSH_AUTH_SOCK` is only a transport: a missing agent, zero or duplicate matching identities, rejection, timeout, malformed response, wrong algorithm, wrong signature, or trust-store mismatch fails closed without a receipt. Option B or any non-recommended refusal creates no signature. After a successful external confirmation, the Main Agent imports and re-verifies the signed result; the Owner does not relay its JSON or machine hashes through chat.

## Rotation

1. Generate a new domain-specific key with a new key ID and complete the full ceremony.
2. Add the new public key as `active` while the old key remains active.
3. Deploy the trust store atomically to every relevant control plane and run a synthetic verification plus `broker doctor` on each host.
4. Stop issuing receipts with the old key.
5. After every old receipt has expired, change the old public record to `revoked`. Do not delete it; historical identity must remain auditable.
6. Re-run readiness checks, record the change digest, and destroy or archive the old private key according to retention policy.

Rotation does not reset or delete the Broker nonce ledger.

## Revocation and suspected compromise

1. Stop the Broker and the affected operational executor. Do not ask the Agent to continue around the failure.
2. Mark the affected public key `revoked` in the root-owned store and distribute it atomically.
3. Treat every unexpired receipt from that key as invalid. Preserve them for investigation; do not edit them.
4. Audit Broker ledger entries, executor logs, runtime context, repository decisions, and external action records from the earliest possible compromise time.
5. Create a new key only through a fresh ceremony. Do not reactivate or rename the compromised key.
6. Resume L3 only after incident closure, readiness checks, and a synthetic end-to-end rehearsal.

## Loss recovery

If the private key is lost but not believed compromised, mark its public record `revoked`, let no pending receipt proceed, and create a replacement through a fresh ceremony. A backup may be restored only by the recorded custodians, on an approved device, with the witness confirming identity and custody while the ceremony tool compares the re-exported public bytes against the recorded public key.

If the only backup or its unlock material is lost, there is no cryptographic bypass. Keep L3 blocked and provision a new trust root. Never add a `--skip-signature`, mock Broker, repository-local trust store, or shared emergency private key.
