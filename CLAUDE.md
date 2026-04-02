# Privatemode Proxy — Agent Instructions

OpenAI-compatible API proxy that runs on Azure Confidential VMs (AMD SEV-SNP). Provides a web-accessible endpoint for end-to-end encrypted AI via [Privatemode](https://privatemode.ai) — no local software required. All memory is hardware-encrypted; Azure cannot access decrypted traffic, TLS keys, or API secrets.

5 models live: `gpt-oss-120b`, `gemma-3-27b`, `qwen3-coder-30b`, `qwen3-embedding-4b`, `whisper-large-v3`. 116 tests. This is the Tier 3 AI processing endpoint for sensitive advocacy data — investigation documentation, witness testimony, and legal defense materials must route here, not through cloud APIs.

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

## Organizational Context

**Layer:** 1–3 | **Lever:** Strengthen | **Integration:** Tier 3 AI processing (standalone — platform integration pending)

This is the zero-retention AI processing endpoint for sensitive advocacy data. Per the three-adversary threat model (`foundations/security.md`), Tier 3 data (investigation documentation, witness identities, legal defense) must never route through cloud AI providers with data retention. This proxy is the countermeasure.

**Relevant strategy documents:**
- `foundations/security.md` — three-tier security model and Tier 3 encryption requirements
- `closed-decisions.md` 2026-03-25 — Tier 3 encryption enforcement needs hardening
- `ecosystem/repos.md` — platform integration is pending (Tier 3 queries should route here)

**Current status:** 5 models live in production. Platform integration with `open-paws-platform` is planned — Tier 3 queries should route through this proxy. Integration is not yet wired.

## Development Standards

### 10-Point Review Checklist (ranked by AI violation frequency)

1. **DRY** — AI clones code at 4x the human rate. Search before writing anything new
2. **Deep modules** — Reject shallow wrappers and pass-through methods. Interface must be simpler than implementation
3. **Single responsibility** — Each function does one thing at one level of abstraction
4. **Error handling** — Never catch-all. AI suppresses errors and removes safety checks. Every catch block must handle specifically
5. **Information hiding** — Don't expose internal state. Mask API keys (last 4 chars only)
6. **Ubiquitous language** — Use movement terminology consistently. Never let AI invent synonyms for domain terms
7. **Design for change** — Abstraction layers and loose coupling
8. **Legacy velocity** — AI code churns 2x faster. Use characterization tests before modifying existing code
9. **Over-patterning** — Simplest structure that works. Three similar lines of code is better than a premature abstraction
10. **Test quality** — Every test must fail when the covered behavior breaks. Mutation score over coverage percentage

### Quality Gates

- **Desloppify:** `desloppify scan --path .` — minimum score ≥85
- **Speciesist language:** `semgrep --config semgrep-no-animal-violence.yaml` on all code/docs edits
- **Two-failure rule:** After two failed fixes on the same problem, stop and restart with a better approach

### Testing Methodology

- Spec-first test generation preferred
- Reject: snapshot trap, mock everything, happy path only, test-after-commit, coverage theater
- Three questions per test: (1) Does it fail if code is wrong? (2) Does it encode a domain rule? (3) Would mutation testing kill it?

### Plan-First Development

Read existing code → identify change → write spec → subtasks → plan-test-implement-verify each → comprehension check → commit per subtask

### Seven Concerns — Critical for This Repo

All 7 concerns apply. Highlighted critical ones:

- **Security** (critical) — This is the Tier 3 security boundary. Any change to the proxy that weakens encryption, adds logging of request content, or exposes keys is a Tier 3 security incident. Every PR must pass the security audit checklist.
- **Privacy** (critical) — Zero-retention is the core invariant. Never add logging that captures request content (`choices` field). Token usage metadata (the `usage` field) is the only permissible log.
- **Testing** (critical) — 116 tests. Every new endpoint or behavior must have corresponding tests. Security-critical code requires higher test assertion quality.
- **Cost optimization** — Usage tracker enables per-key cost attribution. Use this data to optimize model routing.
- **Advocacy domain** — API key names and admin UI labels should use movement terminology.
- **Accessibility** — Admin UI must work on low-bandwidth connections for field operatives.
- **Emotional safety** — Not directly applicable to the proxy layer.

### Advocacy Domain Language

Never introduce synonyms for:
- **Investigation** — covert documentation (all data processed here may be investigation data)
- **Witness** — person providing testimony (identity requires maximum protection)
- **Activist** — person engaged in advocacy work (not "user" in security contexts)

### Structured Coding Reference

For tool-specific AI coding instructions (Claude Code rules, Cursor MDC, Copilot, Windsurf, etc.), copy the corresponding directory from `structured-coding-with-ai` into this project root.
