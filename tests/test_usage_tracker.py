"""
Tests for usage tracking: cost calculation, record aggregation, time ranges.
"""

import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'auth-proxy'))

from usage_tracker import UsageTracker, get_time_range


class TestCostCalculation:
    """Test cost calculation for different model types."""

    def test_chat_model_cost(self, tmp_path):
        tracker = UsageTracker(os.path.join(str(tmp_path), "usage.json"))
        cost = tracker.calculate_cost("gpt-oss-120b", tokens=1_000_000)
        assert cost == pytest.approx(5.0)

    def test_embedding_model_cost(self, tmp_path):
        tracker = UsageTracker(os.path.join(str(tmp_path), "usage.json"))
        cost = tracker.calculate_cost("qwen3-embedding-4b", tokens=1_000_000)
        assert cost == pytest.approx(0.13)

    def test_audio_model_cost(self, tmp_path):
        tracker = UsageTracker(os.path.join(str(tmp_path), "usage.json"))
        # 1 MB of audio
        cost = tracker.calculate_cost("whisper-large-v3", audio_bytes=1024 * 1024)
        assert cost == pytest.approx(0.096)

    def test_unknown_model_uses_default(self, tmp_path):
        tracker = UsageTracker(os.path.join(str(tmp_path), "usage.json"))
        cost = tracker.calculate_cost("unknown-model", tokens=1_000_000)
        assert cost == pytest.approx(5.0)  # Default pricing

    def test_zero_tokens_zero_cost(self, tmp_path):
        tracker = UsageTracker(os.path.join(str(tmp_path), "usage.json"))
        cost = tracker.calculate_cost("gpt-oss-120b", tokens=0)
        assert cost == 0.0

    def test_small_token_count(self, tmp_path):
        tracker = UsageTracker(os.path.join(str(tmp_path), "usage.json"))
        cost = tracker.calculate_cost("gpt-oss-120b", tokens=100)
        assert cost == pytest.approx(100 * 5.0 / 1_000_000)


class TestRecordUsage:
    """Test usage recording and persistence."""

    def test_record_basic_usage(self, tmp_path):
        usage_file = os.path.join(str(tmp_path), "usage.json")
        tracker = UsageTracker(usage_file)

        tracker.record_usage(
            key_id="key1",
            model="gpt-oss-120b",
            endpoint="chat",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )

        summary = tracker.get_usage_summary()
        assert summary['total_tokens'] == 30
        assert summary['requests'] == 1

    def test_auto_calculates_total_tokens(self, tmp_path):
        usage_file = os.path.join(str(tmp_path), "usage.json")
        tracker = UsageTracker(usage_file)

        tracker.record_usage(
            key_id="key1",
            model="gpt-oss-120b",
            endpoint="chat",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=0,  # Should be auto-calculated
        )

        summary = tracker.get_usage_summary()
        assert summary['total_tokens'] == 30

    def test_persistence(self, tmp_path):
        usage_file = os.path.join(str(tmp_path), "usage.json")
        tracker1 = UsageTracker(usage_file)

        for i in range(10):
            tracker1.record_usage(
                key_id="key1", model="gpt-oss-120b", endpoint="chat",
                total_tokens=100,
            )
        tracker1.flush()

        # Create a new tracker from the same file
        tracker2 = UsageTracker(usage_file)
        summary = tracker2.get_usage_summary()
        assert summary['requests'] == 10
        assert summary['total_tokens'] == 1000

    def test_flush(self, tmp_path):
        usage_file = os.path.join(str(tmp_path), "usage.json")
        tracker = UsageTracker(usage_file)

        tracker.record_usage(
            key_id="key1", model="gpt-oss-120b", endpoint="chat",
            total_tokens=100,
        )
        tracker.flush()

        # Verify file exists and has data
        tracker2 = UsageTracker(usage_file)
        assert tracker2.get_usage_summary()['requests'] == 1


class TestUsageSummary:
    """Test usage aggregation and filtering."""

    def test_filter_by_key(self, tmp_path):
        usage_file = os.path.join(str(tmp_path), "usage.json")
        tracker = UsageTracker(usage_file)

        tracker.record_usage(key_id="key1", model="gpt-oss-120b", endpoint="chat", total_tokens=100)
        tracker.record_usage(key_id="key2", model="gpt-oss-120b", endpoint="chat", total_tokens=200)

        summary = tracker.get_usage_summary(key_id="key1")
        assert summary['total_tokens'] == 100
        assert summary['requests'] == 1

    def test_filter_by_time(self, tmp_path):
        usage_file = os.path.join(str(tmp_path), "usage.json")
        tracker = UsageTracker(usage_file)

        # Record usage
        tracker.record_usage(key_id="key1", model="gpt-oss-120b", endpoint="chat", total_tokens=100)

        # Totals are kept per UTC day, so "the future" means after today ends
        future = time.time() + 2 * 86400
        summary = tracker.get_usage_summary(start_time=future)
        assert summary['requests'] == 0

    def test_by_model_breakdown(self, tmp_path):
        usage_file = os.path.join(str(tmp_path), "usage.json")
        tracker = UsageTracker(usage_file)

        tracker.record_usage(key_id="key1", model="gpt-oss-120b", endpoint="chat", total_tokens=100)
        tracker.record_usage(key_id="key1", model="gemma-3-27b", endpoint="chat", total_tokens=200)

        summary = tracker.get_usage_summary()
        assert "gpt-oss-120b" in summary['by_model']
        assert "gemma-3-27b" in summary['by_model']
        assert summary['by_model']['gpt-oss-120b']['tokens'] == 100
        assert summary['by_model']['gemma-3-27b']['tokens'] == 200

    def test_by_endpoint_breakdown(self, tmp_path):
        usage_file = os.path.join(str(tmp_path), "usage.json")
        tracker = UsageTracker(usage_file)

        tracker.record_usage(key_id="key1", model="gpt-oss-120b", endpoint="chat", total_tokens=100)
        tracker.record_usage(key_id="key1", model="qwen3-embedding-4b", endpoint="embeddings", total_tokens=50)

        summary = tracker.get_usage_summary()
        assert summary['by_endpoint']['chat']['requests'] == 1
        assert summary['by_endpoint']['embeddings']['requests'] == 1

    def test_usage_by_key(self, tmp_path):
        usage_file = os.path.join(str(tmp_path), "usage.json")
        tracker = UsageTracker(usage_file)

        tracker.record_usage(key_id="key1", model="gpt-oss-120b", endpoint="chat", total_tokens=100)
        tracker.record_usage(key_id="key1", model="gpt-oss-120b", endpoint="chat", total_tokens=200)
        tracker.record_usage(key_id="key2", model="gpt-oss-120b", endpoint="chat", total_tokens=50)

        by_key = tracker.get_usage_by_key()
        assert by_key['key1']['tokens'] == 300
        assert by_key['key1']['requests'] == 2
        assert by_key['key2']['tokens'] == 50

    def test_daily_breakdown(self, tmp_path):
        usage_file = os.path.join(str(tmp_path), "usage.json")
        tracker = UsageTracker(usage_file)

        tracker.record_usage(key_id="key1", model="gpt-oss-120b", endpoint="chat", total_tokens=100)

        daily = tracker.get_daily_breakdown(days=1)
        assert len(daily) >= 1
        assert daily[0]['tokens'] == 100


class TestTimeRanges:
    """Test time range calculation."""

    def test_today(self):
        start, end = get_time_range("today")
        assert start is not None
        assert end is not None
        assert start < end

    def test_week(self):
        start, end = get_time_range("week")
        assert end - start >= 6 * 86400  # At least 6 days

    def test_month(self):
        start, end = get_time_range("month")
        assert end - start >= 29 * 86400

    def test_all_time(self):
        start, end = get_time_range("all")
        assert start is None
        assert end is None

    def test_unknown_period(self):
        start, end = get_time_range("unknown")
        assert start is None
        assert end is None


class TestUsagePrivacyAndDurability:
    """Usage is kept as daily totals with a retention limit (audit F6)."""

    def test_requests_on_one_day_stored_as_one_row(self, tmp_path):
        usage_file = os.path.join(str(tmp_path), "usage.json")
        tracker = UsageTracker(usage_file)
        for tokens in (100, 200, 300):
            tracker.record_usage(key_id="key1", model="gpt-oss-120b", endpoint="chat",
                                 total_tokens=tokens)
        tracker.flush()

        with open(usage_file) as f:
            stored = json.load(f)
        assert 'records' not in stored
        assert len(stored['buckets']) == 1
        row = stored['buckets'][0]
        assert row['requests'] == 3
        assert row['total_tokens'] == 600
        # Only a date, never a time of day
        assert set(row) == {'date', 'key_id', 'model', 'endpoint', 'requests',
                            'prompt_tokens', 'completion_tokens', 'total_tokens',
                            'audio_bytes', 'cost_eur'}

    def test_legacy_per_request_file_is_migrated(self, tmp_path):
        usage_file = os.path.join(str(tmp_path), "usage.json")
        now = time.time()
        legacy = {'records': [
            {'timestamp': now, 'key_id': 'k', 'model': 'gpt-oss-120b', 'endpoint': 'chat',
             'prompt_tokens': 1, 'completion_tokens': 2, 'total_tokens': 3,
             'audio_bytes': 0, 'cost_eur': 0.1},
            {'timestamp': now + 1, 'key_id': 'k', 'model': 'gpt-oss-120b', 'endpoint': 'chat',
             'prompt_tokens': 1, 'completion_tokens': 2, 'total_tokens': 3,
             'audio_bytes': 0, 'cost_eur': 0.1},
        ]}
        with open(usage_file, 'w') as f:
            json.dump(legacy, f)

        tracker = UsageTracker(usage_file)
        assert tracker.get_usage_summary()['requests'] == 2
        assert tracker.get_usage_summary()['total_tokens'] == 6
        # The per-request timestamps are gone from disk after migration
        with open(usage_file) as f:
            stored = json.load(f)
        assert 'records' not in stored
        assert 'timestamp' not in json.dumps(stored)

    def test_totals_older_than_retention_are_deleted(self, tmp_path):
        usage_file = os.path.join(str(tmp_path), "usage.json")
        with open(usage_file, 'w') as f:
            json.dump({'buckets': [
                {'date': '2000-01-01', 'key_id': 'k', 'model': 'm', 'endpoint': 'chat',
                 'requests': 5, 'total_tokens': 50},
            ]}, f)
        tracker = UsageTracker(usage_file, retention_days=30)
        tracker.record_usage(key_id="k", model="m", endpoint="chat", total_tokens=1)
        tracker.flush()

        assert tracker.get_usage_summary()['requests'] == 1
        with open(usage_file) as f:
            assert '2000-01-01' not in f.read()

    def test_flush_is_atomic(self, tmp_path):
        usage_file = os.path.join(str(tmp_path), "usage.json")
        tracker = UsageTracker(usage_file)
        tracker.record_usage(key_id="k", model="m", endpoint="chat", total_tokens=1)
        tracker.flush()
        assert sorted(os.listdir(tmp_path)) == ["usage.json"]  # no leftover temp file

    def test_corrupt_file_is_kept_not_silently_discarded(self, tmp_path):
        usage_file = os.path.join(str(tmp_path), "usage.json")
        with open(usage_file, 'w') as f:
            f.write('{"buckets": [ truncated')
        tracker = UsageTracker(usage_file)
        assert tracker.get_usage_summary()['requests'] == 0
        backups = [n for n in os.listdir(tmp_path) if n.startswith("usage.json.corrupt-")]
        assert len(backups) == 1

    async def test_flush_async_writes_only_when_changed(self, tmp_path):
        usage_file = os.path.join(str(tmp_path), "usage.json")
        tracker = UsageTracker(usage_file)
        await tracker.flush_async()
        assert not os.path.exists(usage_file)  # nothing recorded, nothing written
        tracker.record_usage(key_id="k", model="m", endpoint="chat", total_tokens=1)
        await tracker.flush_async()
        assert UsageTracker(usage_file).get_usage_summary()['requests'] == 1
