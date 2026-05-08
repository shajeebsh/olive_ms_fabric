# Implementation Questions Checklist

Use these questions during discovery, design reviews, and build checkpoints.

## Phase 1: Source Discovery

- What are all current data sources?
- Who owns each source?
- How often does each source change?
- Are Excel files manually maintained, exported, or system-generated?
- What are the expected keys for each file?
- Which columns contain personal or sensitive data?
- Are there known quality issues?
- What are the expected row counts per month?
- What date formats are used?
- Are historic files available for backfill?

## Phase 2: Ingestion

- How will each department deliver files?
- What naming convention will source owners follow?
- What happens when a corrected file is uploaded?
- What is the retention period for raw files?
- Which API endpoints support incremental pulls?
- How are API credentials managed?
- What is the retry strategy?
- What makes an ingestion run successful?

## Phase 3: Silver Transformation

- What is the business key for each entity?
- Which entities need SCD Type 2 history?
- Which reference data mappings are required?
- Which nulls are allowed?
- Which values should be rejected, defaulted, or quarantined?
- What quality threshold blocks Gold processing?
- How will corrected source records be reprocessed?

## Phase 4: Gold and Reporting

- What business questions must the platform answer first?
- What are the required facts and dimensions?
- Which measures need formal definitions?
- Which reports require row-level security?
- Which reports need Direct Lake freshness?
- Which semantic model tables should be hidden from users?

## Phase 5: Governance and Operations

- Which groups can access each workspace?
- Which columns need sensitivity labels?
- Which tables need masking?
- Who reviews Purview lineage?
- What is the daily operational checklist?
- Who receives alerts?
- What is the rollback process?
- What evidence is needed for audit?

