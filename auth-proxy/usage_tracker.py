"""
Usage Tracker for API Key Token Consumption.

Tracks token usage per API key without storing any prompt/response content.
Calculates costs based on Privatemode pricing.
"""

import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
from collections import defaultdict
import threading

from config import USAGE_FILE

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


@dataclass
class UsageRecord:
    """Single usage record."""
    timestamp: float
    key_id: str
    model: str
    endpoint: str  # 'chat', 'embeddings', 'transcriptions'
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    audio_bytes: int = 0  # for audio transcription
    cost_eur: float = 0.0


class UsageTracker:
    """Thread-safe usage tracker with file persistence."""

    def __init__(self, usage_file: str = None):
        self.usage_file = usage_file or USAGE_FILE
        self._lock = threading.Lock()
        self._records: list[dict] = []
        self._load()

    def _load(self):
        """Load usage data from file."""
        try:
            if os.path.exists(self.usage_file):
                with open(self.usage_file, 'r') as f:
                    data = json.load(f)
                    self._records = data.get('records', [])
        except (json.JSONDecodeError, IOError):
            self._records = []

    def _save(self):
        """Save usage data to file."""
        try:
            Path(self.usage_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self.usage_file, 'w') as f:
                json.dump({'records': self._records}, f)
        except IOError as e:
            print(f"Failed to save usage data: {e}")

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
        """Record a usage event."""
        if total_tokens == 0 and prompt_tokens + completion_tokens > 0:
            total_tokens = prompt_tokens + completion_tokens

        cost = self.calculate_cost(model, total_tokens, audio_bytes)

        record = UsageRecord(
            timestamp=time.time(),
            key_id=key_id,
            model=model,
            endpoint=endpoint,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            audio_bytes=audio_bytes,
            cost_eur=cost
        )

        with self._lock:
            self._records.append(asdict(record))
            # Save periodically (every 10 records) to avoid too many writes
            if len(self._records) % 10 == 0:
                self._save()

    def flush(self):
        """Force save to disk."""
        with self._lock:
            self._save()

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
        with self._lock:
            records = self._records.copy()

        # Filter records
        filtered = []
        for r in records:
            if key_id and r['key_id'] != key_id:
                continue
            if start_time and r['timestamp'] < start_time:
                continue
            if end_time and r['timestamp'] > end_time:
                continue
            filtered.append(r)

        # Aggregate
        summary = {
            'total_tokens': 0,
            'total_audio_bytes': 0,
            'total_cost_eur': 0.0,
            'by_model': defaultdict(lambda: {'tokens': 0, 'audio_bytes': 0, 'cost': 0.0, 'requests': 0}),
            'by_endpoint': defaultdict(lambda: {'tokens': 0, 'requests': 0, 'cost': 0.0}),
            'requests': len(filtered)
        }

        for r in filtered:
            summary['total_tokens'] += r['total_tokens']
            summary['total_audio_bytes'] += r['audio_bytes']
            summary['total_cost_eur'] += r['cost_eur']

            model = r['model']
            summary['by_model'][model]['tokens'] += r['total_tokens']
            summary['by_model'][model]['audio_bytes'] += r['audio_bytes']
            summary['by_model'][model]['cost'] += r['cost_eur']
            summary['by_model'][model]['requests'] += 1

            endpoint = r['endpoint']
            summary['by_endpoint'][endpoint]['tokens'] += r['total_tokens']
            summary['by_endpoint'][endpoint]['requests'] += 1
            summary['by_endpoint'][endpoint]['cost'] += r['cost_eur']

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
        with self._lock:
            records = self._records.copy()

        # Filter by time
        filtered = []
        for r in records:
            if start_time and r['timestamp'] < start_time:
                continue
            if end_time and r['timestamp'] > end_time:
                continue
            filtered.append(r)

        # Group by key
        by_key = defaultdict(lambda: {
            'tokens': 0,
            'audio_bytes': 0,
            'cost_eur': 0.0,
            'requests': 0
        })

        for r in filtered:
            key_id = r['key_id']
            by_key[key_id]['tokens'] += r['total_tokens']
            by_key[key_id]['audio_bytes'] += r['audio_bytes']
            by_key[key_id]['cost_eur'] += r['cost_eur']
            by_key[key_id]['requests'] += 1

        return dict(by_key)

    def get_daily_breakdown(
        self,
        key_id: Optional[str] = None,
        days: int = 30
    ) -> list[dict]:
        """Get daily usage breakdown for the last N days."""
        with self._lock:
            records = self._records.copy()

        # Calculate time range
        now = datetime.now()
        start_date = now - timedelta(days=days)
        start_time = start_date.timestamp()

        # Filter records
        filtered = []
        for r in records:
            if r['timestamp'] < start_time:
                continue
            if key_id and r['key_id'] != key_id:
                continue
            filtered.append(r)

        # Group by day
        daily = defaultdict(lambda: {'tokens': 0, 'cost_eur': 0.0, 'requests': 0})

        for r in filtered:
            day = datetime.fromtimestamp(r['timestamp']).strftime('%Y-%m-%d')
            daily[day]['tokens'] += r['total_tokens']
            daily[day]['cost_eur'] += r['cost_eur']
            daily[day]['requests'] += 1

        # Convert to sorted list
        result = []
        for date_str in sorted(daily.keys()):
            result.append({
                'date': date_str,
                **daily[date_str]
            })

        return result


# Time range helpers
def get_time_range(period: str) -> tuple[float, float]:
    """
    Get start and end timestamps for a time period.

    Args:
        period: 'today', 'yesterday', 'week', 'month', 'year', 'all'

    Returns:
        (start_timestamp, end_timestamp)
    """
    now = datetime.now()
    end = now.timestamp()

    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'yesterday':
        yesterday = now - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    elif period == 'week':
        start = now - timedelta(days=7)
    elif period == 'month':
        start = now - timedelta(days=30)
    elif period == 'year':
        start = now - timedelta(days=365)
    elif period == 'all':
        return None, None
    else:
        # Default to all time
        return None, None

    return start.timestamp() if hasattr(start, 'timestamp') else start, end


# Global instance
_tracker: Optional[UsageTracker] = None


def get_tracker() -> UsageTracker:
    """Get or create the global usage tracker."""
    global _tracker
    if _tracker is None:
        _tracker = UsageTracker()
    return _tracker
