"""evalh publish: S3 layout and CloudWatch metrics, against moto."""

import json
import os

import pytest

boto3 = pytest.importorskip("boto3")
moto = pytest.importorskip("moto")

from evalh.publish import NAMESPACE, metric_data, publish  # noqa: E402
from evalh.runner import Variant  # noqa: E402

SUMMARY = {
    "accuracy": 0.925,
    "cost_per_task_usd": 0.0102,
    "tokens_per_task": 7400.0,
    "latency_p50_s": 9.2,
    "latency_p95_s": 14.0,
    "errors": 0,
}


@pytest.fixture
def run_dir(tmp_path):
    results = {"meta": {"timestamp": "2026-10-07T18:00:00+00:00"}, "summaries": {"v2": SUMMARY}}
    (tmp_path / "results.json").write_text(json.dumps(results), encoding="utf-8")
    (tmp_path / "summary.md").write_text("# summary", encoding="utf-8")
    return tmp_path


def test_metric_data_scales_accuracy_and_adds_source_dimension():
    data = metric_data({"v2": SUMMARY}, "agent-pr")
    acc = [d for d in data if d["MetricName"] == "Accuracy"]
    assert {d["Value"] for d in acc} == {92.5} and acc[0]["Unit"] == "Percent"
    assert [len(d["Dimensions"]) for d in acc] == [1, 2]
    assert len(data) == 2 * len(SUMMARY)


def test_publish_uploads_run_and_pushes_metrics(run_dir):
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    with moto.mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="evals")
        cw = boto3.client("cloudwatch", region_name="us-east-1")
        out = publish(
            run_dir, bucket="evals", run_id="pr-17", source="agent-pr", s3=s3, cloudwatch=cw
        )

        keys = sorted(o["Key"] for o in s3.list_objects_v2(Bucket="evals")["Contents"])
        assert keys == ["runs/2026-10-07/pr-17/results.json", "runs/2026-10-07/pr-17/summary.md"]
        head = s3.head_object(Bucket="evals", Key=keys[0])
        assert head["ContentType"] == "application/json"
        names = {m["MetricName"] for m in cw.list_metrics(Namespace=NAMESPACE)["Metrics"]}
        assert {"Accuracy", "CostPerTaskUSD", "TokensPerTask", "LatencyP50"} <= names
        assert out["metrics"] == 12


def test_default_provider_keeps_cache_keys_stable():
    v = Variant(name="x", model="claude-haiku-4-5")
    assert "provider" not in v.cache_identity()
    assert (
        Variant(name="x", model="m", provider="bedrock").cache_identity()["provider"] == "bedrock"
    )
