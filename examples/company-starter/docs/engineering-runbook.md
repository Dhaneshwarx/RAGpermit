---
doc_id: engineering-runbook
title: Engineering runbook
department: Engineering
clearance: 2
allowed_roles: []
---

## Technology

The inventory application uses Python for backend services and PostgreSQL for its database. Deepak maintains the backend service.

## Deployment

Production deployment requires a completed code review, passing automated tests, and Engineering lead approval. The deployment window is Tuesday from 7 PM to 8 PM.

## Recovery

If a deployment fails its health check, the on-call engineer rolls back to the previous stable release and notifies the Engineering lead. The recovery target is 30 minutes.
