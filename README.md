# privatemode-proxy

> **Status: 🟢 Production** — 5 models live, 116 tests, desloppify score 85.5/100
>
> Part of the [Open Paws](https://github.com/Open-Paws) animal advocacy technology ecosystem.
> This is the **Tier 3 AI processing endpoint** — the mandatory route for sensitive investigation data, witness testimony, and legal defense materials.

An OpenAI-compatible API proxy for [Privatemode](https://privatemode.ai) that runs inside an **Azure Confidential VM** with AMD SEV-SNP hardware encryption. Provides a web-accessible, zero-retention AI endpoint — no local software required on the client side.

---

## Why This Exists: AI Privacy for High-Risk Advocacy

Animal advocacy investigations involve data that is routinely targeted by state surveillance, corporate infiltration, and legal discovery. Undercover investigation documentation, witness identities, and legal defense strategy are all examples of **Tier 3 data** in the Open Paws security model — information that must never be processed by AI providers who retain input data.

Standard cloud AI APIs (OpenAI, Anthropic, Google) retain prompts for abuse monitoring, model training, or legal compliance. For activists and investigators, this creates three direct threats:

1. **State surveillance** — ag-gag law enforcement can subpoena AI provider logs to identify investigation targets and undercover personnel
2. **Industry infiltration** — corporate investigators can obtain AI conversation logs through legal channels to expose campaign strategy
3. **AI model bias** — even providers with retention policies can expose data through model training or telemetry

This proxy routes all requests through [Privatemode](https://privatemode.ai), whose servers run inside a **Trusted Execution Environment (TEE)** — a hardware-isolated enclave where even Privatemode's own infrastructure cannot read the data being processed. Combined with Azure Confidential Computing for the proxy itself, the entire path from client to AI model is end-to-end encrypted.

**The practical result:** An activist documenting a factory farm investigation can use AI tools with the same privacy guarantees as an encrypted messaging app. No logs. No retention. No exposure.

---

## How It Works

The proxy runs two processes in a single Docker container, managed by supervisord:

```
Client
  |
  | HTTPS (TLS terminates inside TEE — Azure cannot read)
  v
auth-proxy  (Python/aiohttp, port 8080)
  |  - TLS termination
  |  - Bearer token authentication
  |  - Per-key and per-IP rate limiting
  |  - Usage tracking (token counts only — content never logged)
  |  - Admin web UI
  v
privatemode-proxy  (official Privatemode binary, port 8081)
  |
  | E2E encrypted channel to Privatemode TEE
  v
Privatemode API  (Trusted Execution Environment)
  |
  v
AI model (gpt-oss-120b, gemma-3-27b, qwen3-coder-30b-a3b,
          qwen3-embedding-4b, whisper-large-v3)
```

The key security property: **TLS terminates inside the AMD SEV-SNP encrypted memory**. Azure's hypervisor and infrastructure staff cannot access the decrypted traffic, TLS private keys, or API secrets — the CPU hardware enforces this isolation.

### What Azure Confidential Computing Provides

A standard cloud VM gives the cloud provider theoretical access to VM memory (where secrets live), disk contents, and decrypted network traffic. Azure Confidential VMs with **AMD SEV-SNP** (Secure Encrypted Virtualization - Secure Nested Paging) change this:

- The CPU encrypts all VM memory using keys generated inside the CPU and never exported
- Azure's hypervisor, storage infrastructure, and personnel cannot read the encrypted memory
- TLS private keys, the Privatemode API key, and all decrypted request content exist only inside this encrypted memory space
- The vTPM and Secure Boot chain verify the boot environment before any sensitive keys are loaded

This is the same technology class used by confidential computing for healthcare data (HIPAA), financial processing, and enterprise secrets management — applied here to protect investigation data and activist identities.

### Zero-Retention Architecture

Prompts and responses are never written to disk or any log stream. The proxy reads only the `usage` field from Privatemode's responses (token counts for billing attribution) and discards the `choices` field entirely:

```json
{
  "choices": [...],          // ignored — your actual conversation content
  "usage": {
    "prompt_tokens": 25,     // recorded for cost tracking
    "completion_tokens": 150,
    "total_tokens": 175
  }
}
```

Usage data is stored as aggregate counts per API key. No conversation content, no request bodies, no IP-to-content associations are retained.

---

## OpenAI Compatibility

The proxy implements the OpenAI API surface. Any client that supports a custom `base_url` works without code changes:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://your-proxy-domain.com/v1",
    api_key="your-proxy-api-key"  # managed in the admin UI
)

response = client.chat.completions.create(
    model="gpt-oss-120b",
    messages=[{"role": "user", "content": "Summarize this investigation report."}]
)
```

This means existing integrations with n8n, Zapier, Make, Pipedream, LangChain, LlamaIndex, and any other OpenAI-compatible tooling work by changing only the `base_url` and API key — no other modifications required.

---

## API Endpoints

All endpoints require `Authorization: Bearer YOUR_KEY` except `/health`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/chat/completions` | Chat with AI models |
| `POST` | `/v1/embeddings` | Generate text embeddings (RAG, semantic search) |
| `POST` | `/v1/audio/transcriptions` | Speech-to-text via Whisper |
| `GET` | `/v1/models` | List available models |
| `GET` | `/health` | Health check (no auth required) |
| `GET` | `/admin` | Admin web UI (password auth) |

## Available Models

| Model ID | Type | Description |
|----------|------|-------------|
| `gpt-oss-120b` | Chat | Large general-purpose model |
| `gemma-3-27b` | Chat | Google's Gemma 3 27B |
| `qwen3-coder-30b-a3b` | Chat | Optimized for code generation |
| `qwen3-embedding-4b` | Embeddings | Vector search, RAG, semantic similarity |
| `whisper-large-v3` | Audio | Speech-to-text transcription |

## Pricing

Prices are in Euros. Usage is tracked per API key in the admin panel.

| Type | Price |
|------|-------|
| Chat models (`gpt-oss-120b`, `gemma-3-27b`, `qwen3-coder`) | €5.00 per 1M tokens |
| Embeddings (`qwen3-embedding-4b`) | €0.13 per 1M tokens |
| Speech-to-text (`whisper-large-v3`) | €0.096 per megabyte |

---

## Deployment Guide

### Prerequisites

- Azure subscription with Confidential VM quota
- Azure CLI installed (`brew install azure-cli` on macOS)
- A domain name you control (for TLS certificates)
- SSH key pair — **generate locally, never in Azure**

### Step 1: Generate SSH Keys Locally

```bash
ssh-keygen -t ed25519 -f ~/.ssh/azure-privatemode -C "privatemode-cvm" -N ""
```

This creates `~/.ssh/azure-privatemode` (private key, never share) and `~/.ssh/azure-privatemode.pub` (public key for Azure).

### Step 2: Login to Azure

```bash
az login
az account show  # verify your subscription
```

### Step 3: Create Resource Group

Choose a region with AMD SEV-SNP support: `eastus`, `westus`, `westeurope`, `northeurope`.

```bash
az group create --name privatemode-rg --location eastus
```

### Step 4: Create the Confidential VM

```bash
az vm create \
  --resource-group privatemode-rg \
  --name privatemode-cvm \
  --size Standard_DC2as_v5 \
  --image Canonical:ubuntu-24_04-lts:cvm:latest \
  --security-type ConfidentialVM \
  --os-disk-security-encryption-type VMGuestStateOnly \
  --enable-secure-boot true \
  --enable-vtpm true \
  --admin-username azureuser \
  --ssh-key-values ~/.ssh/azure-privatemode.pub \
  --public-ip-sku Standard
```

Note the `publicIpAddress` in the output — you need this for DNS.

**VM size options:**

| Size | vCPUs | RAM | Recommended for |
|------|-------|-----|-----------------|
| Standard_DC2as_v5 | 2 | 8 GB | Development / testing |
| Standard_DC4as_v5 | 4 | 16 GB | Light production |
| Standard_DC8as_v5 | 8 | 32 GB | Production |

### Step 5: Open Firewall Ports

```bash
az vm open-port --resource-group privatemode-rg --name privatemode-cvm --port 443 --priority 1010
az vm open-port --resource-group privatemode-rg --name privatemode-cvm --port 80 --priority 1020
```

Port 80 is needed temporarily for Let's Encrypt certificate verification only.

### Step 6: Configure DNS

Add an A record pointing your domain to the VM's public IP. Verify propagation with `dig yourdomain.com` before proceeding.

### Step 7: Verify AMD SEV-SNP

```bash
ssh -i ~/.ssh/azure-privatemode azureuser@<your-vm-ip>
sudo dmesg | grep -i sev
```

Expected output:
```
Memory Encryption Features active: AMD SEV
Detected confidential virtualization sev-snp
```

### Step 8: Install Docker

```bash
sudo apt-get update && sudo apt-get install -y docker.io
sudo systemctl enable docker && sudo systemctl start docker
sudo usermod -aG docker azureuser
```

### Step 9: Get TLS Certificate

```bash
sudo apt-get install -y certbot
sudo certbot certonly --standalone --non-interactive \
  --agree-tos --email your@email.com \
  -d yourdomain.com

mkdir -p ~/privatemode/certs
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ~/privatemode/certs/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ~/privatemode/certs/key.pem
sudo chown -R $USER:$USER ~/privatemode/certs
```

### Step 10: Prepare Configuration

```bash
mkdir -p ~/privatemode/secrets ~/privatemode/data

cat > ~/privatemode/secrets/api_keys.json << 'EOF'
{
  "keys": [
    {
      "key_id": "default",
      "api_key": "your-secure-api-key-here",
      "name": "Default Key",
      "created_at": "2024-01-01T00:00:00Z",
      "expires_at": null,
      "rate_limit": null,
      "enabled": true
    }
  ]
}
EOF
```

### Step 11: Deploy the Container

```bash
# From your local machine
scp -i ~/.ssh/azure-privatemode -r Dockerfile supervisord.conf auth-proxy \
  azureuser@<your-vm-ip>:~/privatemode/

# On the VM
cd ~/privatemode
sudo docker build -t privatemode-proxy:latest .

sudo docker run -d \
  --name privatemode \
  --restart unless-stopped \
  -p 443:8080 \
  -v ~/privatemode/certs:/app/certs:ro \
  -v ~/privatemode/secrets:/app/secrets \
  -v ~/privatemode/data:/app/data \
  -e TLS_CERT_FILE=/app/certs/cert.pem \
  -e TLS_KEY_FILE=/app/certs/key.pem \
  -e ADMIN_PASSWORD='your-secure-admin-password' \
  -e API_KEYS_FILE=/app/secrets/api_keys.json \
  -e PRIVATEMODE_API_KEY='your-privatemode-api-key' \
  privatemode-proxy:latest
```

### Step 12: Verify Deployment

```bash
# Health check
curl https://yourdomain.com/health

# Test with API key
curl -H "Authorization: Bearer your-api-key" \
  https://yourdomain.com/v1/models
```

Verify the attestation confirmation in container logs:

```bash
sudo docker logs -f privatemode
```

Look for: `level=INFO msg="Validate succeeded" validator.name=snp-0-GENOA`

This confirms the workload is running in a genuine AMD SEV-SNP enclave.

---

## Local Development

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env: set ADMIN_PASSWORD and PRIVATEMODE_API_KEY

# 2. Build the container
docker build -t privatemode-proxy:latest .

# 3. Run in HTTP mode (no TLS required for local dev)
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

---

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PRIVATEMODE_API_KEY` | Yes | — | Your Privatemode API key |
| `ADMIN_PASSWORD` | Yes | — | Password for admin web UI |
| `API_KEYS_FILE` | No | `/app/secrets/api_keys.json` | Path to API keys JSON |
| `TLS_CERT_FILE` | No | — | Path to TLS certificate (enables HTTPS when set) |
| `TLS_KEY_FILE` | No | — | Path to TLS private key |
| `FORCE_HTTPS` | No | `true` when TLS enabled | Reject non-HTTPS requests |
| `TRUST_PROXY` | No | `false` | Trust `X-Forwarded-*` headers from a reverse proxy |
| `RATE_LIMIT_REQUESTS` | No | `100` | Global rate limit (requests per window) |
| `RATE_LIMIT_WINDOW` | No | `60` | Rate limit window in seconds |
| `IP_RATE_LIMIT_REQUESTS` | No | `1000` | Per-IP rate limit |
| `IP_RATE_LIMIT_WINDOW` | No | `60` | Per-IP rate limit window in seconds |
| `PORT` | No | `8080` | Port to listen on |
| `UPSTREAM_URL` | No | `http://localhost:8081` | URL for Privatemode binary (supervisord sets this) |

---

## Security Model

### What Azure Cannot Access

With AMD SEV-SNP enabled, the following are protected by hardware-enforced memory encryption:

| Component | Protected | Notes |
|-----------|-----------|-------|
| VM memory | Yes | CPU-encrypted, Azure has no keys |
| TLS private key | Yes | Generated on VM, lives in encrypted memory only |
| Privatemode API key | Yes | Passed via env var, stays in encrypted memory |
| SSH private key | Yes | Generated locally, never uploaded to Azure |
| Decrypted API traffic | Yes | TLS terminates inside the TEE |
| OS disk (optional) | Yes | Enable with confidential disk encryption flag |

### What Azure Can Access

| Component | Notes |
|-----------|-------|
| Encrypted network traffic | Before TLS termination at the VM NIC |
| VM metadata | Name, size, region, resource group |
| Disk contents | If confidential disk encryption is not enabled |
| Resource metrics | CPU, memory, network usage aggregates |

### Defense in Depth Layers

1. **Hardware** — AMD SEV-SNP encrypts all VM memory at the CPU level
2. **OS** — Ubuntu with Secure Boot and vTPM verify boot integrity
3. **Container** — Non-root user (`appuser`, UID 1000), minimal Python 3.12-slim base
4. **Application** — HTTPS enforcement, Bearer token auth, per-key and per-IP rate limiting
5. **Key management** — Hot-reload key rotation, optional per-key expiration and rate limits

### Zero-Retention Invariant

This is a core security invariant, not a configuration option. The proxy must never write request content (the `choices` field) to any log, file, or external service. Only the `usage` field (token counts) is recorded for cost attribution per API key.

Any PR that adds logging of request or response content is a Tier 3 security incident.

---

## Admin Panel

Access at `https://yourdomain.com/admin` with your `ADMIN_PASSWORD`.

**API Keys tab** — generate keys with optional expiration and per-key rate limits, view key status, revoke or delete keys instantly.

**Settings tab** — verify Privatemode upstream connection, configure global and per-IP rate limits.

**Usage & Costs tab** — total spend in Euros for any period, token usage broken down by API key and model, request counts.

**Documentation tab** — in-app reference for encryption model, code examples, model and pricing reference.

---

## Certificate Renewal

Let's Encrypt certificates expire after 90 days. The certbot systemd timer handles automatic renewal:

```bash
sudo systemctl status certbot.timer
sudo certbot renew --dry-run  # test renewal

# After renewal, copy new certificates and restart
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ~/privatemode/certs/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ~/privatemode/certs/key.pem
sudo docker restart privatemode
```

---

## Troubleshooting

**"HTTPS required" error** — use `https://` in your URL. HTTP is rejected when TLS is enabled.

**Container won't start** — check logs: `sudo docker logs privatemode`

**SEV-SNP not detected** — verify you used `--security-type ConfidentialVM` when creating the VM.

**Certificate errors** — verify paths and file permissions: `ls -la ~/privatemode/certs/`

**Rate limit exceeded** — check response headers for reset time, or adjust limits in admin UI.

**Attestation failure in logs** — the VM may not have confidential computing enabled. Recreate with the correct flags.

---

## Cleanup

```bash
az group delete --name privatemode-rg --yes --no-wait
```

---

## Repository Structure

```
privatemode-proxy/
├── Dockerfile              # Multi-stage: extracts Privatemode binary, Python 3.12-slim, non-root
├── supervisord.conf        # Runs auth-proxy + privatemode-proxy in one container
├── .env.example            # Environment variable template
├── pytest.ini              # Test config (asyncio mode)
├── requirements-test.txt   # Test dependencies (pytest, pytest-aiohttp, pytest-asyncio)
├── auth-proxy/
│   ├── server.py           # Main proxy — request routing, TLS, HTTPS enforcement
│   ├── admin.py            # Admin web UI — key management, usage dashboard, settings
│   ├── config.py           # Centralized configuration from environment variables
│   ├── key_manager.py      # API key CRUD, validation, hot-reload from JSON
│   ├── usage_tracker.py    # Token usage and cost tracking per key/model
│   ├── utils.py            # Shared utilities
│   ├── requirements.txt    # Runtime dependencies (aiohttp, cryptography)
│   └── static/             # Admin UI static assets
├── tests/
│   ├── conftest.py         # pytest fixtures
│   ├── helpers.py          # Test utilities
│   ├── test_auth.py        # Authentication tests
│   ├── test_admin.py       # Admin UI tests
│   ├── test_endpoints.py   # API endpoint tests
│   ├── test_proxy.py       # Proxy forwarding tests
│   ├── test_rate_limiting.py
│   └── test_usage_tracker.py
├── scripts/
│   ├── manage_keys.py      # CLI for API key management
│   └── scrape_docs.py      # Scrapes Privatemode docs into docs/
├── docs/                   # Scraped Privatemode docs + Azure deployment guide
└── secrets/                # Gitignored — api_keys.json, settings.json
```

---

## Who Should Use This

This proxy is intended for:

- **Investigators and activists** who need AI assistance for investigation documentation, report drafting, or data analysis — where using a standard cloud AI API would expose sensitive content to data retention
- **Campaigns** that use automated AI workflows (n8n, Zapier, Make) and need those workflows to use zero-retention AI
- **Coalitions** building shared tooling where member organizations have strict data handling requirements
- **Developers** in the Open Paws stack building features that process Tier 3 data (investigation documentation, witness identity data, legal defense materials)

If you are processing data that could identify activists, document investigations, or support legal defense, route it through this proxy — not through any cloud AI provider with data retention.

---

## Contributing

1. Read the existing code before writing anything new
2. Write failing tests before implementing changes
3. Run quality gates before submitting a PR:
   ```bash
   desloppify scan --path .   # minimum score ≥85
   semgrep --config semgrep-no-animal-violence.yaml .
   pytest
   ```
4. Security changes (auth, TLS, rate limiting, logging) require explicit security review in the PR — tag them clearly
5. The zero-retention invariant is non-negotiable: no PR may add logging of request or response content

See `CLAUDE.md` for the full development guide, architecture decisions, and organizational context.

---

## License

MIT
