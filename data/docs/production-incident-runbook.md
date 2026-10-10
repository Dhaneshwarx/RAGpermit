---
doc_id: production-incident-runbook
title: Production Incident Runbook
department: Engineering
clearance: 2
allowed_roles: []
---
# Orbit Labs: Production Incident Runbook

This runbook is for Engineering staff handling outages in the production system.

## Severity levels
Severity 1 means the product is down for all customers. Severity 2 means a major feature is broken for some customers. Severity 3 is a minor problem with a workaround.

## First 15 minutes
The on-call engineer acknowledges the alert within 5 minutes and opens an incident channel named #inc-YYYYMMDD. For Severity 1, the on-call engineer pages the Engineering Manager immediately.

## Database failover
If the primary database is unreachable for more than 3 minutes, the on-call engineer may start a failover to the standby database. A failover needs the approval code FO-7731-K, which is held only by the on-call rota.

## After the incident
Write a short post-incident review within 3 working days. The review lists the timeline, the root cause and at least two follow-up actions.