# NB_10_Purview_Lineage_Annotations
# Layer: Governance
# Purpose: Apply Delta table properties that support cataloguing and lineage review.

from datetime import datetime

TABLE_CATALOGUE = [
    {
        "table": "Bronze_Lakehouse.bronze_training_enrolments",
        "description": "Raw training enrolment data ingested from controlled Excel landing folders.",
        "source": "Files/landing/training/training_enrolments_*.xlsx",
        "owner": "data-engineering@example.org",
        "sensitivity": "Confidential_Internal",
        "layer": "Bronze",
        "pii": "false",
    },
    {
        "table": "Silver_Lakehouse.silver_training_enrolments",
        "description": "Cleansed and deduplicated training enrolments.",
        "source": "Bronze_Lakehouse.bronze_training_enrolments",
        "owner": "data-engineering@example.org",
        "sensitivity": "Confidential_Internal",
        "layer": "Silver",
        "pii": "false",
    },
    {
        "table": "Gold_Lakehouse.fact_training_completion",
        "description": "Gold fact table for training completion analytics.",
        "source": "Silver_Lakehouse.silver_training_enrolments",
        "owner": "analytics@example.org",
        "sensitivity": "Confidential_Internal",
        "layer": "Gold",
        "pii": "false",
    },
]

for entry in TABLE_CATALOGUE:
    stamp = str(datetime.utcnow())
    props = {
        "description": entry["description"],
        "lineage.source": entry["source"],
        "lineage.layer": entry["layer"],
        "owner": entry["owner"],
        "sensitivity_label": entry["sensitivity"],
        "gdpr.contains_pii": entry["pii"],
        "last_annotated": stamp,
    }
    prop_sql = ", ".join([f"'{key}' = '{value}'" for key, value in props.items()])
    try:
        spark.sql(f"ALTER TABLE {entry['table']} SET TBLPROPERTIES ({prop_sql})")
        print(f"Annotated {entry['table']}")
    except Exception as exc:
        print(f"Could not annotate {entry['table']}: {exc}")

