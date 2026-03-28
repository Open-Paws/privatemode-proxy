"""
Tests for proxy behavior: request forwarding, response handling, error cases.
"""

import json
import os
import sys
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'auth-proxy'))

from server import (
    detect_endpoint_type,
    extract_model_from_request,
    extract_usage_from_response,
)


class TestDetectEndpointType:
    """Test endpoint detection from request path."""

    def test_chat_completions(self):
        assert detect_endpoint_type("/v1/chat/completions") == "chat"

    def test_embeddings(self):
        assert detect_endpoint_type("/v1/embeddings") == "embeddings"

    def test_audio_transcriptions(self):
        assert detect_endpoint_type("/v1/audio/transcriptions") == "transcriptions"

    def test_completions(self):
        assert detect_endpoint_type("/v1/completions") == "completions"

    def test_unknown(self):
        assert detect_endpoint_type("/v1/models") == "other"

    def test_nested_chat_path(self):
        assert detect_endpoint_type("/api/v2/chat/completions") == "chat"


class TestExtractModelFromRequest:
    """Test model extraction from request body."""

    def test_valid_json_with_model(self):
        body = json.dumps({"model": "gpt-oss-120b", "messages": []}).encode()
        assert extract_model_from_request(body) == "gpt-oss-120b"

    def test_no_model_field(self):
        body = json.dumps({"messages": []}).encode()
        assert extract_model_from_request(body) == "unknown"

    def test_invalid_json(self):
        body = b"not json"
        assert extract_model_from_request(body) == "unknown"

    def test_empty_body(self):
        assert extract_model_from_request(b"") == "unknown"


class TestExtractUsageFromResponse:
    """Test usage/token extraction from response body."""

    def test_chat_completion_response(self):
        response = {
            "model": "gpt-oss-120b",
            "choices": [{"message": {"content": "Hello"}}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            }
        }
        body = json.dumps(response).encode()
        usage = extract_usage_from_response(body, "chat")

        assert usage['model'] == "gpt-oss-120b"
        assert usage['prompt_tokens'] == 10
        assert usage['completion_tokens'] == 20
        assert usage['total_tokens'] == 30

    def test_embedding_response(self):
        response = {
            "model": "qwen3-embedding-4b",
            "data": [{"embedding": [0.1, 0.2]}],
            "usage": {"total_tokens": 50}
        }
        body = json.dumps(response).encode()
        usage = extract_usage_from_response(body, "embeddings")

        assert usage['model'] == "qwen3-embedding-4b"
        assert usage['total_tokens'] == 50

    def test_no_usage_field(self):
        response = {"model": "gpt-oss-120b", "choices": []}
        body = json.dumps(response).encode()
        usage = extract_usage_from_response(body, "chat")

        assert usage['prompt_tokens'] == 0
        assert usage['total_tokens'] == 0

    def test_invalid_response_body(self):
        usage = extract_usage_from_response(b"not json", "chat")
        assert usage['model'] == 'unknown'
        assert usage['total_tokens'] == 0

    def test_empty_response(self):
        usage = extract_usage_from_response(b"", "chat")
        assert usage['model'] == 'unknown'
