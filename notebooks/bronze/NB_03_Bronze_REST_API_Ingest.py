# NB_03_Bronze_REST_API_Ingest
# Layer: Bronze
# Purpose: Incremental REST API ingestion using a watermark.

import uuid
import requests
from pyspark.sql.functions import current_timestamp, lit

SOURCE_SYSTEM = "rest_api_lms"
TARGET_TABLE = "Bronze_Lakehouse.bronze_lms_enrolments"

watermark_df = spark.sql(f"""
    SELECT last_run_ts
    FROM Bronze_Lakehouse.control_watermark
    WHERE source_system = '{SOURCE_SYSTEM}'
""")

last_run_ts = watermark_df.first()["last_run_ts"]

api_base = "https://example.invalid/api/v2"
api_token = mssparkutils.credentials.getSecret("fabric-secrets", "lms-api-token")

headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
params = {"updated_since": last_run_ts.isoformat(), "page_size": 500}

records = []
page = 1
while True:
    params["page"] = page
    response = requests.get(f"{api_base}/enrolments", headers=headers, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()
    records.extend(payload.get("results", []))
    if not payload.get("next"):
        break
    page += 1

if not records:
    print("No records to ingest.")
    mssparkutils.notebook.exit("NO_NEW_DATA")

batch_id = str(uuid.uuid4())
df_api = spark.createDataFrame(records)

df_bronze = (
    df_api.withColumn("_ingested_at", current_timestamp())
    .withColumn("_source_system", lit(SOURCE_SYSTEM))
    .withColumn("_batch_id", lit(batch_id))
)

df_bronze.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(TARGET_TABLE)

spark.sql(f"""
    UPDATE Bronze_Lakehouse.control_watermark
    SET last_run_ts = current_timestamp(),
        last_batch_id = '{batch_id}',
        last_row_count = {len(records)},
        status = 'SUCCESS',
        updated_at = current_timestamp()
    WHERE source_system = '{SOURCE_SYSTEM}'
""")

print(f"Loaded {len(records)} records into {TARGET_TABLE}.")

