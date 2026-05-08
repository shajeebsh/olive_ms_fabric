# Tests

Use this folder for validation tests around transformation logic, data quality rules, and deployment readiness.

Recommended tests:

- Silver transformation unit tests using small synthetic DataFrames.
- DQ rule tests for nulls, ranges, dates, duplicates, and referential integrity.
- Config validation tests to ensure environment settings are complete.
- SQL smoke tests for required Gold tables.

