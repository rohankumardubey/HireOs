# MinIO Layout

Local lakehouse assets can be mirrored into MinIO buckets such as:

- `hireos-raw-events`
- `hireos-clean-events`
- `hireos-analytics`

The MVP writes local JSONL and SQLite/PostgreSQL records first, then exposes a structure ready for object-store exports.

