# HIPPRA Targeted Account Enrichment — Methodology

Workflow: `hippra_targeted_account_enrichment_v1`  
Run: `hippra_targeted_enrichment_20260810T213116Z`  
Created: `2026-08-10T21:32:08+00:00`

This release is a separate, joinable enrichment layer over immutable Stage 12. It does not replace
`commercial_account`. Six accepted public federal files were downloaded as immutable snapshots,
hashed, schema-validated and registered. Final identities require an observed source identifier or
a deterministic composite key explicitly allowed by the source. Final Stage 12 candidate resolution
requires one CMS clinic enrollment sharing the Stage 12 parent PAC ID and the exact normalized
street address, city, state and five-digit postal prefix.

Normalized name plus full address is retained only as a candidate. Health-system name plus state is
retained only as a candidate. Clinic networks come only from explicit HRSA Health Center Number to
BPHC site relationships. Hospital-system membership comes only from AHRQ's published health-system
ID. The accepted managed-care file does not document clinic-level plan coverage, so that bridge is
empty. No market sizing, pricing, revenue, forecasting, customer, contract, Power BI or DAX work is
performed by this workflow.

Source-period differences are preserved in the source registry and the gap register. The certified
analytical system for this release is DuckDB plus Parquet/CSV.
