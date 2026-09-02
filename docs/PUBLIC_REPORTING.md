# Public Reporting Contract

Generated reports committed to this repository are public artifacts.

## Allowed finding fields

- vendor
- model, when it is not uniquely identifying a target
- device type
- detection confidence
- authentication method/channel
- credential classification
- timestamps at day or batch level where useful

## Forbidden finding fields

- plaintext passwords
- password candidates that succeeded
- Authorization headers
- cookies/session tokens
- private keys/API tokens
- exact live target IP addresses when paired with an authentication finding

## Redaction

Use stable one-way identifiers when correlation is needed. A public identifier should not be reversible to the original IP without a separately protected secret.

Example:

```json
{
  "target_id": "sha256:…",
  "vendor": "NETGEAR",
  "device_type": "router",
  "auth_method": "basic",
  "credential_class": "default-credential",
  "verified": true
}
```

The internal database may contain operational evidence only when access is restricted and the deployment is authorized. Public report generation must sanitize that evidence before it is committed.
