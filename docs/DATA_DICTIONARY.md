# Dashboard semantic layer

The Tableau source has one row per unique `commercial_account_id` and 57 fields. The most important analytical fields are below.

| Field | Grain / meaning | Treatment |
|---|---|---|
| `commercial_account_id` | Stable unique account key | Required; no duplicates or nulls |
| `account_type` | Physician group, hospital, or health system | Descriptive segmentation |
| `account_name` | Certified display name | Not a customer/prospect assertion |
| `authoritative_identifier_type` | Identifier family | Used with source provenance |
| `authoritative_identifier_value` | Source identifier | Identifier, never an additive measure |
| `geocode_state` | Approved state used for mapping | Null/invalid geography is excluded from maps only |
| `postal_code_original` | Source postal identifier | Preserved; not padded or truncated |
| `postal_code_classification` | Domestic, military, foreign, missing, or unresolved class | Prevents unsafe ZIP coercion |
| `provider_relationship_count` | Certified provider-account relationship count | Additive at account grain |
| `unique_provider_count` | Unique linked providers for the account | Descriptive network measure |
| `direct_child_account_count` | Explicit direct child relationships | Missing is not zero unless source evidence says zero |
| `candidate_relationship_count` | Unresolved/candidate relationships | Review evidence, not a confirmed link |
| `has_targeted_enrichment` | Whether targeted enrichment evidence exists | Coverage flag, not quality or priority |
| `ahrq_health_system_link_count` | AHRQ-linked system relationships | CY2023 temporal limitation applies |
| `review_attention_required` | Evidence-quality review flag | Never interpreted as sales priority |
| `review_attention_reason` | Human-readable reason for review | Preserved in the review queue |
| `data_scope_note` | Certified scope caveat | Displayed in documentation/tooltips |

Portfolio totals repeated on account rows are presentation conveniences and must be aggregated with `MIN`/`MAX`, not `SUM`. The delivered KPI sheets instead use distinct account counts and certified additive relationship counts.
