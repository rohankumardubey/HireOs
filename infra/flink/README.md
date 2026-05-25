# Flink Notes

The local MVP does not require a full Flink cluster to demo the recruiter workflow.

Recommended production path:

1. Consume `hireos.*` lifecycle topics from Kafka/Redpanda.
2. Derive windowed metrics such as interviews started per hour, completion rate, scoring failures, and latency percentiles.
3. Sink cleaned metrics into PostgreSQL analytics tables and Parquet outputs in MinIO.

`HireOsMetricsJob.java` is included as a Java skeleton for that path.

