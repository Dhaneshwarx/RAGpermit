---
doc_id: engineering-development
title: Engineering development workflow
department: Engineering
clearance: 2
allowed_roles: []
---

## Planning

Fictional NovaWorks example. Deepak breaks approved work into issues with acceptance criteria. Each issue records an owner, expected behavior and a verification approach before implementation starts.

## Code review

Fictional NovaWorks example. Every production change requires review by another authorized engineer. Review covers correctness, permissions, error handling and automated checks. The author addresses blocking feedback before merging.

## Testing

Fictional NovaWorks example. Run unit tests for changed business logic and integration checks for changed API behavior. Permission changes require both an allowed-user test and a denied-user test.

## Release readiness

Fictional NovaWorks example. Release readiness requires a passing test suite, documented configuration changes and a rollback plan. Production deployment follows the separate engineering runbook and its approval requirements.
