# privatemode-proxy — Agent Reference

OpenAI-compatible API proxy for [Privatemode](https://privatemode.ai) end-to-end encrypted AI, deployed on Azure Confidential VMs with AMD SEV-SNP hardware memory encryption. This is the **Tier 3 AI processing endpoint** for the Open Paws ecosystem — the mandatory route for investigation data, witness testimony, and legal defense materials that must never be processed by AI providers with data retention. All VM memory is hardware-encrypted; Azure cannot access decrypted traffic, TLS private keys, or the Privatemode API key. 116 tests. 5 models in production. Desloppify score 85.5/100.

---

## Status and Change Implications

**Status: 🟢 Production**

This service is actively handling sensitive advocacy data. Changes carry real-world security consequences:

- **Security-critical path**: auth, TLS, rate limiting, and usage tracking code protects investigation data and activist identities. These modules require explicit security review on every PR.
- **Zero-retention invariant**: adding any logging of request or response *content* (the `choices` field) is a Tier 3 security incident — regardless of intent or scope.
- **Platform integration pending**: `open-paws-platform` Tier 3 queries should route here but the integration is not yet wired. Changes to the API surface may affect that upcoming integration.
- **Breaking the proxy silently fails safe**: if the proxy is unavailable, clients receive errors rather than falling back to a less-secure upstream. Do not change error handling in ways that could introduce silent fallback.

---

## Key Files

| File | Purpose |
|------|---------|
| `auth-proxy/server.py` | Main proxy — request routing, TLS termination, HTTPS enforcement, streaming |
| `auth-proxy/admin.py` | Admin web UI — key management, usage dashboard, settings (59 KB, largest file) |
| `auth-proxy/config.py` | Centralized configuration from environment variables — read this before adding any new env var |
| `auth-proxy/key_manager.py` | API key CRUD, validation, hot-reload from JSON — the auth boundary |
| `auth-proxy/usage_tracker.py` | Token usage and cost tracking per key/model — reads `usage` field only, never `choices` |
| `auth-proxy/utils.py` | Shared utilities |
| `Dockerfile` | Multi-stage: extracts official Privatemode binary from `ghcr.io/edgelesssys/privatemode/privatemode-proxy`, installs Python 3.12-slim, runs as non-root `appuser` (UID 1000) |
| `supervisord.conf` | Runs both processes in one container: `privatemode-proxy` on port 8081, `auth-proxy` on port 8080 |
| `.env.example` | All environment variables with documentation — canonical reference |
| `secrets/api_keys.json.example` | API keys file format |
| `tests/conftest.py` | pytest fixtures for async HTTP testing |
| `tests/helpers.py` | Test utilities |
| `docs/CONFIDENTIAL_COMPUTING_DEPLOYMENT.md` | Detailed Azure deployment guide |

---

## Architecture

Two processes, one container:

```
Client (HTTPS)
  --> auth-proxy [Python/aiohttp, :8080]
        TLS termination (inside AMD SEV-SNP encrypted memory)
        Bearer token auth via key_manager.py
        Rate limiting (per-key + per-IP, sliding window)
        Usage tracking (token counts only — content discarded)
        Admin web UI at /admin
  --> privatemode-proxy [official binary, :8081]
        E2E encrypted channel to Privatemode TEE
  --> Privatemode API (Trusted Execution Environment)
  --> AI model
```

The AMD SEV-SNP guarantee: TLS terminates inside hardware-encrypted memory. Azure's hypervisor cannot read decrypted traffic, TLS keys, or the Privatemode API key. This is enforced at the CPU level, not by software configuration.

**Runtime dependencies** (auth-proxy): `aiohttp==3.13.5`, `aiohttp-cors==0.8.1`, `cryptography`

**Test stack**: `pytest`, `pytest-aiohttp`, `pytest-asyncio` (async mode)

---

## Deploy Commands

### Local development (HTTP, no TLS)

```bash
cp .env.example .env
# Edit .env: set ADMIN_PASSWORD and PRIVATEMODE_API_KEY

docker build -t privatemode-proxy:latest .
docker run -d --name privatemode -p 8080:8080 --env-file .env privatemode-proxy:latest
curl http://localhost:8080/health
```

### Run tests

```bash
pip install -r requirements-test.txt
pytest                        # all 116 tests
pytest tests/test_auth.py     # single module
pytest -v                     # verbose
```

### Production (Azure Confidential VM with TLS)

Full step-by-step in `README.md` and `docs/CONFIDENTIAL_COMPUTING_DEPLOYMENT.md`. Key steps:
1. Create AMD SEV-SNP VM: `az vm create --security-type ConfidentialVM --enable-vtpm true`
2. Verify SEV-SNP active: `sudo dmesg | grep -i sev` — look for `Detected confidential virtualization sev-snp`
3. Get Let's Encrypt certificate with certbot
4. Mount certs and run container with `TLS_CERT_FILE` and `TLS_KEY_FILE` env vars
5. Verify attestation in logs: `level=INFO msg="Validate succeeded" validator.name=snp-0-GENOA`

### Quality gates (run before every PR)

```bash
desloppify scan --path .      # minimum score ≥85
semgrep --config semgrep-no-animal-violence.yaml .
pytest
```

---

## Architecture Decisions

**Why two processes in one container?**
The official Privatemode binary (`ghcr.io/edgelesssys/privatemode/privatemode-proxy`) handles the E2E encrypted channel but has no authentication layer. The Python auth-proxy adds API key management, rate limiting, TLS termination, usage tracking, and the admin UI. Running both in one container via supervisord keeps the deployment simple and ensures the auth layer cannot be bypassed by network-level access to port 8081 (which should never be exposed externally).

**Why supervisord and not separate containers?**
Keeping both processes in a single container means the Privatemode API key is never transmitted between containers over a network link. The auth-proxy passes the key to the binary via environment variable at startup, not at request time.

**Why aiohttp and not FastAPI or Flask?**
aiohttp supports full streaming proxy semantics needed for streaming completions without buffering the response. FastAPI and Flask have less direct support for streaming pass-through at the response level.

**Why JSON file for API keys instead of a database?**
Eliminates a database dependency, simplifies deployment, and supports hot-reload without container restart. The key_manager watches the file and reloads on change. For high-volume production, a database could be added — the key_manager interface is the abstraction point.

**Why zero-retention as a hard invariant rather than configurable?**
The use case is specifically Tier 3 data — investigation documentation, witness identities, legal defense materials. Making retention optional would mean a misconfiguration could expose that data. The invariant is intentionally non-configurable.

**Why AMD SEV-SNP specifically?**
AMD SEV-SNP provides hardware attestation (verifiable proof the workload is running in a genuine enclave) in addition to memory encryption. Intel TDX provides similar guarantees on Azure. SEV-SNP was chosen because it is the current default for Azure Confidential VMs and has the most mature tooling.

---

## Integration Points in the Open Paws Stack

| System | Current Status | Notes |
|--------|---------------|-------|
| `open-paws-platform` | Pending | Tier 3 AI queries should route here — integration not yet wired |
| `gary` (autonomous agent) | Not integrated | Investigation-related tasks should eventually route through this proxy |
| Open Paws admin tooling | Direct use | Admin panel accessible at `/admin` with password auth |

**Data classification**: All data processed through this proxy is treated as Tier 3 (highest sensitivity). The routing decision must be made by the calling system before the request arrives — the proxy does not classify data itself.

---

## Safe vs. Risky Changes

### Safe to modify without security review

- Admin UI layout, styling, and non-auth behavior in `admin.py`
- Usage tracking display logic in `usage_tracker.py`
- `scripts/` utilities (manage_keys.py, scrape_docs.py)
- `docs/` content
- Test additions in `tests/`
- `README.md` and `AGENTS.md`
- Environment variable defaults in `config.py` that do not affect security behavior

### Requires explicit security review in PR

- Any change to `auth-proxy/server.py` — especially request routing, TLS handling, HTTPS enforcement, and error responses
- Any change to `auth-proxy/key_manager.py` — the auth boundary
- Any change to logging behavior — the zero-retention invariant must be maintained
- `Dockerfile` base image changes or new capabilities
- `supervisord.conf` process configuration — especially port exposure
- Any new dependency in `auth-proxy/requirements.txt`
- Changes to rate limiting logic in `server.py` or `admin.py`

### Never change without explicit owner approval

- The zero-retention invariant (no logging of `choices` content)
- AMD SEV-SNP / TLS termination architecture
- The non-root container execution model
- Port exposure (8081 must never be exposed externally)

---

## TODOs

- [ ] Wire `open-paws-platform` Tier 3 queries to route through this proxy (integration pending — see `closed-decisions.md` 2026-03-25)
- [ ] Add `gary` agent routing for investigation-related tasks
- [ ] Deduplicate sliding-window rate limit logic (currently triplicated — noted in desloppify review)
- [ ] Fix global store reassignment vs mutation pattern flagged in quality review
- [ ] Add mutation testing to the test suite (currently coverage-based only)
- [ ] Consider confidential disk encryption flag for production deployments handling the most sensitive data
- [ ] Document the `TRUST_PROXY` flag more prominently for deployments behind nginx or a load balancer

---

## Seven Concerns — Status for This Repo

1. **Testing** — 116 tests, async aiohttp-based. Missing: mutation testing. Every new endpoint or auth behavior requires tests.
2. **Security** — AMD SEV-SNP + zero-retention + non-root container + TLS. This is the Tier 3 security boundary. Security changes require expert review.
3. **Privacy** — Zero-retention is the core invariant. Never add logging of request content. Implemented and enforced in `usage_tracker.py`.
4. **Cost optimization** — Per-key cost tracking in usage_tracker.py. Model routing optimization not yet implemented.
5. **Advocacy domain** — Admin UI labels and API key names should use movement terminology (campaign, investigation, etc.).
6. **Accessibility** — Admin UI should function on low-bandwidth connections for field operatives.
7. **Emotional safety** — Not directly applicable to the proxy layer.
