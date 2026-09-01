# Avi Pilot Preparation — Current-State Note

**Date:** 01/09/2026  
**Scope:** Telegram-first partner read isolation and bounded pilot diagnostics.  
**Evidence level:** `CODE_DONE` / `STATIC_VERIFIED` on branch `codex/avi-pilot-prep`; not merged, deployed, or runtime-verified.

This slice prepares the initial Avi pilot without changing the Airtable schema,
UI, services, or write ownership. The selected role is `partner`; reads are
restricted to the configured partner domains. Leads, Deals, Payments, Tasks,
and digest reads use domain scoping. Contact reads require a relationship to an
allowed Deal and fail closed when that relationship is unavailable. Dispatcher
entry points pass the resolved identity through to lead search and digest
generation.

The pilot remains gated on a real `IDENTITY_MAP` entry, production deployment
of the merged SHA, and owner-approved live canaries. Local tests prove only the
static isolation behavior and do not establish production readiness.
