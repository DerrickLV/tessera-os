# Production gate checklist

Use this as an evidence register, not a self-certification. Every applicable row needs
a named owner, dated evidence link, reviewer, and explicit pass decision.

| Gate | Required evidence | Status |
|---|---|---|
| Identity | OIDC configuration, group mapping, joiner/mover/leaver and emergency-access test | Blocked |
| Authorization | Tenant/project negative tests against deployed policy gateway | Blocked |
| Reviewer roles | Named qualified reviewers and separation-of-duties acceptance tests | Blocked |
| Secrets and keys | Managed secret/key service, access review, rotation and revocation test | Blocked |
| Data protection | Classification, DLP validation, encryption evidence, retention and legal-hold approval | Blocked |
| Backup/recovery | Tenant-scoped backup plus timed restore and integrity exercise | Blocked |
| Observability | Centralized traces, alerts, budgets, on-call ownership and log-access review | Blocked |
| Repository | Protected main, required CI/reviews, CODEOWNERS enforcement, secret/code/dependency scanning | Blocked |
| Supply chain | Lockfile provenance, clean build, dependency audit and artifact integrity | Implemented locally; CI/admin validation pending |
| Pilot quality | Approved golden set and measured quality/citation/unsupported-claim targets | Blocked |
| Pilot operations | Measured latency, cost, reviewer time, support load and user acceptance | Blocked |
| Incident response | Scope leak, credential exposure, prompt injection and action-bypass exercises | Blocked |
| External actions | Separate risk decision and exact-action control for each adapter/workflow | Not authorized |
| Launch approval | Product, security, legal/records and workflow-owner sign-off | Blocked |

Repository test results are necessary evidence but do not satisfy deployed controls or
human acceptance. “Not authorized” is the expected state for every production write or
external action in the current release.
