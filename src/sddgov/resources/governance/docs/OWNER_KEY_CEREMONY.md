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

For a regulated trust domain, use two people: a custodian operating the signing device and a witness verifying the public fingerprint and ceremony record. For a lower-risk domain, one owner may fill both roles, but the record must say so.

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
4. Export only the raw 32-byte public key. Encode it with padded standard Base64 and calculate its SHA-256 fingerprint twice using independent tools or devices.
5. Have the witness compare the displayed fingerprints and ceremony metadata. Humans verify identity and custody here; they do not manually approve runtime digests.
6. Add the public record to the root-owned out-of-band trusted approver store with status `active`.
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
      "public_key": "base64-encoded-raw-32-byte-public-key",
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

If the private key is lost but not believed compromised, mark its public record `revoked`, let no pending receipt proceed, and create a replacement through a fresh ceremony. A backup may be restored only by the recorded custodians, on an approved device, with the witness validating the public fingerprint before use.

If the only backup or its unlock material is lost, there is no cryptographic bypass. Keep L3 blocked and provision a new trust root. Never add a `--skip-signature`, mock Broker, repository-local trust store, or shared emergency private key.
