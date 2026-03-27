# Privatemode Proxy — Agent Instructions

OpenAI-compatible API proxy that runs on Azure Confidential VMs (AMD SEV-SNP). Provides a web-accessible endpoint for end-to-end encrypted AI via [Privatemode](https://privatemode.ai) — no local software required. All memory is hardware-encrypted; Azure cannot access decrypted traffic, TLS keys, or API secrets.

## Quick Start

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env: set ADMIN_PASSWORD and PRIVATEMODE_API_KEY

# 2. Build the container
docker build -t privatemode-proxy:latest .

# 3. Run (HTTP mode for local dev)
docker run -d --name privatemode \
  -p 8080:8080 \
  --env-file .env \
  privatemode-proxy:latest

# 4. Health check
curl http://localhost:8080/health

# 5. Run tests
pip install -r requirements-test.txt
pytest
```

For production deployment on Azure Confidential VMs with TLS, see `README.md` (Step-by-step guide) and `docs/CONFIDENTIAL_COMPUTING_DEPLOYMENT.md`.

## Architecture

The container runs two processes managed by **supervisord**:

1. **privatemode-proxy** (port 8081) — Official Privatemode binary from `ghcr.io/edgelesssys/privatemode/privatemode-proxy`. Handles E2E encrypted communication with Privatemode's TEE servers.
2. **auth-proxy** (port 8080) — Python/aiohttp proxy that sits in front of the Privatemode binary. Handles TLS termination, API key authentication, rate limiting, usage tracking, and the admin web UI.

```
Client --> auth-proxy (:8080) --> privatemode-proxy (:8081) --> Privatemode API (TEE)
```

### Key Directories

| Directory | Purpose |
|-----------|---------|
| `auth-proxy/` | Python proxy server — core application code |
| `auth-proxy/static/` | Static assets for admin UI |
| `tests/` | pytest test suite (async, aiohttp-based) |
| `scripts/` | CLI tools — key management, doc scraping |
| `docs/` | Scraped Privatemode documentation + Azure deployment guide |
| `secrets/` | Gitignored — API keys, settings (examples provided) |
| `.github/workflows/` | CodeQL analysis |

## Key Files

| File | Description |
|------|-------------|
| `auth-proxy/server.py` | Main proxy server — request routing, TLS, HTTPS enforcement |
| `auth-proxy/admin.py` | Admin web UI — key management, usage dashboard, settings |
| `auth-proxy/config.py` | Centralized configuration from environment variables |
| `auth-proxy/key_manager.py` | API key CRUD, validation, hot-reload from JSON file |
| `auth-proxy/usage_tracker.py` | Token usage and cost tracking per key/model |
| `auth-proxy/utils.py` | Shared utilities |
| `Dockerfile` | Multi-stage build: extracts Privatemode binary, installs Python deps, runs as non-root |
| `supervisord.conf` | Process manager config — runs both proxies in one container |
| `scripts/manage_keys.py` | CLI for API key management |
| `scripts/scrape_docs.py` | Scrapes Privatemode documentation into `docs/` |
| `.env.example` | Environment variable template |
| `secrets/api_keys.json.example` | API keys file format reference |
| `pytest.ini` | Test config (async mode) |
| `requirements-test.txt` | Test dependencies (pytest, pytest-aiohttp, pytest-asyncio) |

## Development

### Running Tests

```bash
pip install -r requirements-test.txt
pytest                    # all tests
pytest tests/test_auth.py # single module
pytest -v                 # verbose
```

Tests use `pytest-aiohttp` for async HTTP testing. See `tests/conftest.py` for fixtures and `tests/helpers.py` for test utilities.

### API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/v1/chat/completions` | Bearer key | Chat completions |
| `POST` | `/v1/embeddings` | Bearer key | Text embeddings |
| `POST` | `/v1/audio/transcriptions` | Bearer key | Speech-to-text (Whisper) |
| `GET` | `/v1/models` | Bearer key | List available models |
| `GET` | `/health` | None | Health check |
| `GET` | `/admin` | Password | Admin web UI |

### Available Models

`gpt-oss-120b`, `gemma-3-27b`, `qwen3-coder-30b-a3b` (chat), `qwen3-embedding-4b` (embeddings), `whisper-large-v3` (audio).

### Environment Variables

See `.env.example` for the full list. Required: `ADMIN_PASSWORD`, `PRIVATEMODE_API_KEY`. Optional: `TLS_CERT_FILE`, `TLS_KEY_FILE`, `TRUST_PROXY`, rate limit settings.

## Security Model

### TEE Guarantees (AMD SEV-SNP)

- **All VM memory is hardware-encrypted** by the CPU with keys Azure cannot access
- **TLS terminates inside the TEE** — Azure never sees decrypted traffic
- **Privatemode API key** lives only in encrypted memory (passed via env var)
- **SSH keys** are generated locally and never uploaded to Azure
- **Let's Encrypt private keys** are generated on the VM and never leave the TEE

### Defense in Depth

1. **Hardware**: AMD SEV-SNP memory encryption
2. **OS**: Ubuntu with Secure Boot + vTPM
3. **Container**: Non-root user (`appuser`, UID 1000), minimal image
4. **Application**: HTTPS enforcement, per-key and per-IP rate limiting, Bearer token auth
5. **Key management**: Hot-reload key rotation, optional expiration dates, per-key rate limits

### What is NOT Encrypted from Azure

- Encrypted network traffic (before TLS termination)
- VM metadata (name, size, region)
- Disk contents (unless confidential disk encryption enabled)
- Resource usage metrics (CPU, memory, network)

### Zero-Retention

Prompts and responses are never logged or stored. Only token usage metadata is tracked for billing. The proxy reads the `usage` field from responses but ignores `choices` content entirely.
