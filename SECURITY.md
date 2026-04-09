# Security Policy

The Ferro Labs team takes the security of `ferrolabsai` and the broader Ferro Labs AI Gateway ecosystem seriously. This document explains how to report vulnerabilities and what you can expect from us in response.

## Supported Versions

We currently ship security fixes for the latest minor release on PyPI. Older versions receive fixes only for critical issues, at the maintainers' discretion.

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |
| < 0.1   | No        |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues, discussions, or pull requests.**

Instead, report them privately using either of the following channels:

- **Email:** `security@ferrolabs.ai` (preferred). Encrypt sensitive content with our PGP key if possible.
- **GitHub private vulnerability reporting:** https://github.com/ferro-labs/ferrolabs-python-sdk/security/advisories/new

Please include as much of the following as you can:

- A clear description of the issue and its impact.
- The affected version(s) of `ferrolabsai` and the Python version.
- A minimal reproduction — code, request, or steps.
- Any proof-of-concept exploit you have.
- Whether the issue is already public or known to other parties.

## What to Expect

- **Acknowledgement** within 3 business days of your report.
- **Triage and initial assessment** within 7 business days, including a severity estimate.
- **Status updates** at least every 7 days until the issue is resolved.
- **Coordinated disclosure.** We will work with you on a disclosure timeline. Default is 90 days from the first report, or sooner if a fix ships earlier.
- **Credit.** With your permission, we will credit you in the release notes and the security advisory.

## Scope

In scope:

- The `ferrolabsai` Python package and its published releases.
- Code in this repository that runs on user machines (SDK, examples, tests).

Out of scope:

- Vulnerabilities in third-party LLM providers accessed through the gateway.
- Vulnerabilities in self-hosted deployments of the gateway that result from misconfiguration.
- Social engineering, physical attacks, or issues requiring a compromised developer workstation.
- Reports generated solely from automated scanners without a demonstrated impact.

For vulnerabilities in the gateway itself, report at the [ai-gateway repository](https://github.com/ferro-labs/ai-gateway/security/advisories/new).

## Secure Usage Guidelines

If you are integrating `ferrolabsai` into your own application:

- **Never hardcode API keys.** Load them from environment variables or a secret manager.
- **Use HTTPS** for any non-localhost `base_url`.
- **Rotate keys** periodically and immediately if you suspect exposure.
- **Validate `trace_id` and cost fields** on responses if you store them — treat them as untrusted data at your application boundary.
- **Pin the SDK version** in production and review the changelog before upgrading.

## Questions

For security questions that are not vulnerability reports, email `security@ferrolabs.ai`.
