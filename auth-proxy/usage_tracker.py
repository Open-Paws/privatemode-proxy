"""
Usage Tracker for API Key Token Consumption.

Tracks token usage per API key without storing any prompt/response content.
Calculates costs based on Privatemode pricing.

Privacy: usage is kept only as DAILY totals per (key, model, endpoint), never
as one row per request, and totals older than USAGE_RETENTION_DAYS are deleted.
A per-request timeline of who used the endpoint when is itself sensitive
metadata, and billing does not need it.
"""

import os
import json
import time
import asyncio
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from collections import defaultdict

from config import USAGE_FILE, USAGE_RETENTION_DAYS

# Privatemode pricing (EUR per unit)
PRICING = {
    # Chat models: EUR per 1M tokens
    'gpt-oss-120b': {'type': 'token', 'rate': 5.0, 'per': 1_000_000},
    'llama-3.3-70b': {'type': 'token', 'rate': 5.0, 'per': 1_000_000},
    'gemma-3-27b': {'type': 'token', 'rate': 5.0, 'per': 1_000_000},
    'qwen3-coder-30b-a3b': {'type': 'token', 'rate': 5.0, 'per': 1_000_000},
    # Embedding models: EUR per 1M tokens
    'multilingual-e5': {'type': 'token', 'rate': 0.13, 'per': 1_000_000},
    'qwen3-embedding-4b': {'type': 'token', 'rate': 0.13, 'per': 1_000_000},
    # Speech-to-text: EUR per MB
    'whisper-large-v3': {'type': 'audio', 'rate': 0.096, 'per': 1},  # per MB
}

# Default pricing for unknown models
DEFAULT_PRICING = {'type': 'token', 'rate': 5.0, 'per': 1_000_000}

# Model names come from clients; keep stored names bounded
MAX_MODEL_NAME_LENGTH = 100

# Counters kept per daily bucket
COUNTER_FIELDS = ('requests', 'prompt_tokens', 'completion_tokens',
                  'total_tokens', 'audio_bytes', 'cost_eur')

FILE_FORMAT_VERSION = 2


def _utc_date(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime('%Y-%m-%d')


def _day_bounds(date_str: str) -> tuple[float, float]:
    """Start and end timestamps (UTC) of the day a bucket covers."""
    start = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    return start.timestamp(), (start + timedelta(days=1)).timestamp()


class UsageTracker:
    """Thread-safe usage tracker with file persistence (daily totals only)."""

    def __init__(self, usage_file: str = None, retention_days: int = None):
        self.usage_file = usage_file or USAGE_FILE
        self.retention_days = retention_days or USAGE_RETENTION_DAYS
        self._lock = threading.Lock()
        # (date, key_id, model, endpoint) -> counters
        self._buckets: dict[tuple[str, str, str, str], dict] = {}
        self._dirty = False
        self._load()

    # ── persistence ──

    def _add(self, date: str, key_id: str, model: str, endpoint: str, counts: dict) -> None:
        bucket = self._buckets.setdefault(
            (date, key_id, model, endpoint), {field: 0 for field in COUNTER_FIELDS})
        for field in COUNTER_FIELDS:
            bucket[field] += counts.get(field, 0)

    def _load(self):
        """Load usage totals from file, migrating the old per-request format."""
        if not os.path.exists(self.usage_file):
            return
        try:
            with open(self.usage_file, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            # Keep the damaged file for inspection instead of silently
            # replacing the billing history with nothing.
            backup = f"{self.usage_file}.corrupt-{int(time.time())}"
            os.replace(self.usage_file, backup)
            print(f"Usage file unreadable ({type(e).__name__}); moved to {backup}", flush=True)
            return

        for bucket in data.get('buckets', []):
            self._add(bucket['date'], bucket['key_id'], bucket['model'],
                      bucket['endpoint'], bucket)

        # Old format: one record per request. Fold into daily totals and
        # rewrite the file, so the per-request timeline does not survive.
        legacy = data.get('records', [])
        for record in legacy:
            self._add(_utc_date(record['timestamp']), record['key_id'], record['model'],
                      record['endpoint'], {**record, 'requests': 1})
        if legacy:
            self._dirty = True

        if self._prune():
            self._dirty = True
        if self._dirty:
            self.flush()

    def _prune(self) -> bool:
        """Delete totals older than the retention period. Returns True if any were removed."""
        cutoff = _utc_date(time.time() - self.retention_days * 86400)
        expired = [key for key in self._buckets if key[0] < cutoff]
        for key in expired:
            del self._buckets[key]
        return bool(expired)

    def flush(self):
        """Write totals to disk atomically (temp file + rename)."""
        with self._lock:
            self._prune()
            snapshot = [
                {'date': date, 'key_id': key_id, 'model': model, 'endpoint': endpoint, **counts}
                for (date, key_id, model, endpoint), counts in sorted(self._buckets.items())
            ]
            self._dirty = False
        if not self.usage_file:
            return  # persistence disabled (no USAGE_FILE configured)
        payload = {'version': FILE_FORMAT_VERSION, 'granularity': 'day', 'buckets': snapshot}
        path = Path(self.usage_file)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + '.tmp')
            with open(tmp, 'w') as f:
                json.dump(payload, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except OSError as e:
            with self._lock:
                self._dirty = True  # try again on the next flush
            print(f"Failed to save usage data: {e}", flush=True)

    async def flush_async(self):
        """Flush from async code without blocking the event loop (no-op if nothing changed)."""
        if self._dirty:
            await asyncio.to_thread(self.flush)

    # ── recording ──

    def calculate_cost(self, model: str, tokens: int = 0, audio_bytes: int = 0) -> float:
        """Calculate cost in EUR based on model and usage."""
        pricing = PRICING.get(model, DEFAULT_PRICING)

        if pricing['type'] == 'audio':
            # Audio: cost per MB
            mb = audio_bytes / (1024 * 1024)
            return mb * pricing['rate']
        else:
            # Tokens: cost per million tokens
            return (tokens / pricing['per']) * pricing['rate']

    def record_usage(
        self,
        key_id: str,
        model: str,
        endpoint: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        audio_bytes: int = 0
    ):
        """Add one request to today's totals. Written to disk by flush()."""
        if total_tokens == 0 and prompt_tokens + completion_tokens > 0:
            total_tokens = prompt_tokens + completion_tokens

        model = (model or 'unknown')[:MAX_MODEL_NAME_LENGTH]
        cost = self.calculate_cost(model, total_tokens, audio_bytes)

        with self._lock:
            self._add(_utc_date(time.time()), key_id, model, endpoint, {
                'requests': 1,
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': total_tokens,
                'audio_bytes': audio_bytes,
                'cost_eur': cost,
            })
            self._dirty = True

    # ── queries ──

    def _select(self, key_id: Optional[str] = None, start_time: Optional[float] = None,
                end_time: Optional[float] = None) -> list[dict]:
        """
        Daily totals overlapping [start_time, end_time].

        Granularity is one UTC day: a day is included if any part of it falls
        inside the range.
        """
        with self._lock:
            items = [(key, dict(counts)) for key, counts in self._buckets.items()]
        rows = []
        for (date, bucket_key, model, endpoint), counts in items:
            if key_id and bucket_key != key_id:
                continue
            day_start, day_end = _day_bounds(date)
            if start_time and day_end <= start_time:
                continue
            if end_time and day_start > end_time:
                continue
            rows.append({'date': date, 'key_id': bucket_key, 'model': model,
                         'endpoint': endpoint, **counts})
        return rows

    def get_usage_summary(
        self,
        key_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> dict:
        """
        Get usage summary for a key or all keys within a time range.

        Returns:
            {
                'total_tokens': int,
                'total_cost_eur': float,
                'by_model': {model: {'tokens': int, 'cost': float}},
                'by_endpoint': {endpoint: {'tokens': int, 'requests': int, 'cost': float}},
                'requests': int
            }
        """
        rows = self._select(key_id, start_time, end_time)

        summary = {
            'total_tokens': 0,
            'total_audio_bytes': 0,
            'total_cost_eur': 0.0,
            'by_model': defaultdict(lambda: {'tokens': 0, 'audio_bytes': 0, 'cost': 0.0, 'requests': 0}),
            'by_endpoint': defaultdict(lambda: {'tokens': 0, 'requests': 0, 'cost': 0.0}),
            'requests': 0
        }

        for r in rows:
            summary['requests'] += r['requests']
            summary['total_tokens'] += r['total_tokens']
            summary['total_audio_bytes'] += r['audio_bytes']
            summary['total_cost_eur'] += r['cost_eur']

            by_model = summary['by_model'][r['model']]
            by_model['tokens'] += r['total_tokens']
            by_model['audio_bytes'] += r['audio_bytes']
            by_model['cost'] += r['cost_eur']
            by_model['requests'] += r['requests']

            by_endpoint = summary['by_endpoint'][r['endpoint']]
            by_endpoint['tokens'] += r['total_tokens']
            by_endpoint['requests'] += r['requests']
            by_endpoint['cost'] += r['cost_eur']

        # Convert defaultdicts to regular dicts
        summary['by_model'] = dict(summary['by_model'])
        summary['by_endpoint'] = dict(summary['by_endpoint'])

        return summary

    def get_usage_by_key(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> dict[str, dict]:
        """Get usage breakdown by key."""
        by_key = defaultdict(lambda: {'tokens': 0, 'audio_bytes': 0, 'cost_eur': 0.0, 'requests': 0})

        for r in self._select(start_time=start_time, end_time=end_time):
            totals = by_key[r['key_id']]
            totals['tokens'] += r['total_tokens']
            totals['audio_bytes'] += r['audio_bytes']
            totals['cost_eur'] += r['cost_eur']
            totals['requests'] += r['requests']

        return dict(by_key)

    def get_daily_breakdown(
        self,
        key_id: Optional[str] = None,
        days: int = 30
    ) -> list[dict]:
        """Get daily usage breakdown for the last N days."""
        start_time = time.time() - days * 86400
        daily = defaultdict(lambda: {'tokens': 0, 'cost_eur': 0.0, 'requests': 0})

        for r in self._select(key_id=key_id, start_time=start_time):
            daily[r['date']]['tokens'] += r['total_tokens']
            daily[r['date']]['cost_eur'] += r['cost_eur']
            daily[r['date']]['requests'] += r['requests']

        return [{'date': date_str, **daily[date_str]} for date_str in sorted(daily)]


# Time range helpers
def get_time_range(period: str) -> tuple[float, float]:
    """
    Get start and end timestamps for a time period (UTC, matching the daily totals).

    Args:
        period: 'today', 'yesterday', 'week', 'month', 'year', 'all'

    Returns:
        (start_timestamp, end_timestamp)
    """
    now = datetime.now(timezone.utc)
    end = now.timestamp()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == 'today':
        start = midnight
    elif period == 'yesterday':
        start = midnight - timedelta(days=1)
        end = midnight.timestamp() - 1
    elif period == 'week':
        start = now - timedelta(days=7)
    elif period == 'month':
        start = now - timedelta(days=30)
    elif period == 'year':
        start = now - timedelta(days=365)
    else:
        # 'all' and unknown periods: no bounds
        return None, None

    return start.timestamp(), end


# Global instance
_tracker: Optional[UsageTracker] = None


def get_tracker() -> UsageTracker:
    """Get or create the global usage tracker."""
    global _tracker
    if _tracker is None:
        _tracker = UsageTracker()
    return _tracker
