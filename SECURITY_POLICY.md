# Security Policy

## Scope

RouterScan is for defensive research and assessment of systems that are owned by the operator or for which the operator has explicit authorization.

## Target authorization

Active probing and authentication checks MUST run only against an explicitly authorized target set. CI, scheduled jobs, and distributed workers MUST NOT infer authorization from scan results alone.

Recommended controls:

- provide an explicit target/allowlist at job start;
- fail closed when the authorization context is missing;
- record the authorization reference, not its secret contents;
- keep production credentials and API tokens outside Git;
- use least-privilege service accounts.

## Credential handling

Credential dictionaries may be used as test inputs in an authorized assessment, but discovered credentials are sensitive security findings.

The project MUST NOT publish:

- plaintext discovered passwords;
- reusable authentication headers or session tokens;
- private keys or API tokens;
- public reports containing a live target IP together with a working credential.

Public reports should use a redacted target identifier and a classification such as `default-credential`, `weak-credential`, or `verified-auth-channel`.

## Logging

Logs and reports must be treated as potentially sensitive. Sanitization is required before committing generated artifacts to a public repository.

## Disclosure

Verified findings should be disclosed to the affected owner/provider through an appropriate channel. Do not use this repository as a mechanism for unauthorized access or credential distribution.
