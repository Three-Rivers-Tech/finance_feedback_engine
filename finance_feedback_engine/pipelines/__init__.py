"""Data pipeline modules for Finance Feedback Engine.

This package contains scalable, production-ready data pipelines for:
- Batch ingestion (historical backfill with incremental loading)
- Streaming ingestion (real-time market data via Kafka)
- Transformation (dbt models + Spark jobs)
- Data quality (Great Expectations validation)
- Orchestration (Airflow DAGs)
- Monitoring (Prometheus metrics + Grafana dashboards)

Architecture: Lakehouse pattern with Delta Lake storage
Layers: Bronze (raw) → Silver (curated) → Gold (aggregated marts)
"""

__version__ = "1.0.0"
