"""Publish an eval run to AWS: the report files to S3, and the headline numbers as CloudWatch
metrics so regressions show up as a trend line, not only as a failed check.

S3 layout: ``s3://<bucket>/runs/<YYYY-MM-DD>/<run_id>/{results.json,summary.md,report.html}``.
Metrics: namespace ``AgentEvals``, one datum per variant with dimension ``Variant``, plus one
with ``Variant`` + ``Source`` (e.g. ``harness``, ``agent-pr``), so trends can be split by
where the run came from.
"""

from __future__ import annotations

import json
from pathlib import Path

NAMESPACE = "AgentEvals"
FILES = ("results.json", "summary.md", "report.html")
_CONTENT_TYPES = {".json": "application/json", ".md": "text/markdown", ".html": "text/html"}

# summary key -> (metric name, unit, scale)
METRICS = {
    "accuracy": ("Accuracy", "Percent", 100),
    "cost_per_task_usd": ("CostPerTaskUSD", "None", 1),
    "tokens_per_task": ("TokensPerTask", "Count", 1),
    "latency_p50_s": ("LatencyP50", "Seconds", 1),
    "latency_p95_s": ("LatencyP95", "Seconds", 1),
    "errors": ("Errors", "Count", 1),
}


def metric_data(summaries: dict[str, dict], source: str) -> list[dict]:
    data = []
    for variant, summary in summaries.items():
        for key, (name, unit, scale) in METRICS.items():
            if summary.get(key) is None:
                continue
            for dims in (
                [{"Name": "Variant", "Value": variant}],
                [{"Name": "Variant", "Value": variant}, {"Name": "Source", "Value": source}],
            ):
                data.append(
                    {
                        "MetricName": name,
                        "Dimensions": dims,
                        "Value": summary[key] * scale,
                        "Unit": unit,
                    }
                )
    return data


def publish(
    run_dir: Path,
    *,
    bucket: str | None,
    run_id: str,
    source: str,
    metrics: bool = True,
    s3=None,
    cloudwatch=None,
) -> dict:
    """Upload ``run_dir`` to S3 (if ``bucket``) and put metrics (if ``metrics``)."""
    import boto3

    results = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    out: dict = {"uploaded": [], "metrics": 0}

    if bucket:
        s3 = s3 or boto3.client("s3")
        day = results["meta"]["timestamp"][:10]
        prefix = f"runs/{day}/{run_id}"
        for name in FILES:
            path = run_dir / name
            if not path.exists():
                continue
            s3.upload_file(
                str(path),
                bucket,
                f"{prefix}/{name}",
                ExtraArgs={"ContentType": _CONTENT_TYPES[path.suffix]},
            )
            out["uploaded"].append(f"s3://{bucket}/{prefix}/{name}")

    if metrics:
        cloudwatch = cloudwatch or boto3.client("cloudwatch")
        data = metric_data(results["summaries"], source)
        for i in range(0, len(data), 500):  # PutMetricData accepts up to 1000 datums per call
            cloudwatch.put_metric_data(Namespace=NAMESPACE, MetricData=data[i : i + 500])
        out["metrics"] = len(data)
    return out
