# Privatemode Auth Proxy for Confidential Computing

An OpenAI-compatible API proxy for [Privatemode](https://privatemode.ai) that runs on Azure Confidential Computing. This gives you a web-accessible endpoint for end-to-end encrypted AI - no local software required.

## Why Use This?

### The Problem with Privatemode's Default Setup

Privatemode provides end-to-end encrypted AI, but their standard setup requires running a local proxy on your machine. This works great for local development, but breaks down when:

- **You're using hosted automation tools** like n8n, Zapier, Make, or Pipedream - you can't install software on their servers
- **You're building web apps** where users need AI access from their browsers
- **You're on mobile or a locked-down machine** where you can't run the local proxy
- **You want a team endpoint** instead of everyone running their own proxy

### The Solution: A Cloud Proxy in a Confidential VM

This project deploys Privatemode's proxy to a cloud server, but with a critical difference: it runs inside an **Azure Confidential VM** with AMD SEV-SNP hardware encryption. This means:

1. **Your prompts stay encrypted** - even Azure can't see them
2. **Works with any HTTP client** - n8n, Zapier, curl, browsers, anything
3. **One endpoint for your whole team** - manage access with API keys
4. **OpenAI-compatible API** - drop-in replacement, just change the base URL

### Example: Using with n8n

In n8n, you'd normally use the OpenAI node. To use Privatemode instead:

1. Deploy this proxy (instructions below)
2. In n8n, add an "OpenAI" credential
3. Set the base URL to `https://your-proxy-domain.com/v1`
4. Use an API key from your proxy's admin panel

That's it. All your n8n AI workflows now use end-to-end encrypted AI.

### Example: Using with Any OpenAI SDK

```python
from openai import OpenAI

# Just change the base_url and api_key
client = OpenAI(
    base_url="https://your-proxy-domain.com/v1",
    api_key="your-proxy-api-key"  # NOT your OpenAI key
)

# Everything else works exactly the same
response = client.chat.completions.create(
    model="gpt-oss-120b",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

## Why Confidential Computing?

When you run a normal VM in the cloud, the cloud provider has theoretical access to:
- Your VM's memory (where secrets and decrypted data live)
- Your disk contents
- Network traffic before/after TLS termination

**Azure Confidential VMs with AMD SEV-SNP change this.** The CPU encrypts all VM memory with keys that Azure cannot access. This means:
- Your TLS private keys are never visible to Azure
- API requests are decrypted only inside the protected memory
- Your Privatemode API key stays encrypted in memory

## How the Encryption Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Azure Confidential VM (AMD SEV-SNP)                  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    Hardware-Encrypted Memory                          │  │
│  │                    (Azure CANNOT access this)                         │  │
│  │                                                                       │  │
│  │   ┌────────────────┐         ┌──────────────────────┐                │  │
│  │   │   Auth Proxy   │────────▶│  Privatemode Proxy   │───────────────────▶ Privatemode API
│  │   │   (TLS Here)   │         │                      │                │  │  (E2E Encrypted)
│  │   └────────────────┘         └──────────────────────┘                │  │
│  │         ▲                                                             │  │
│  │         │ TLS decryption happens HERE,                               │  │
│  │         │ inside encrypted memory                                    │  │
│  └─────────│─────────────────────────────────────────────────────────────┘  │
└────────────│────────────────────────────────────────────────────────────────┘
             │
    ┌────────┴────────┐
    │     Client      │
    │  (Your API Key) │
    └─────────────────┘
```

**Key security properties:**
1. TLS terminates inside the TEE - Azure never sees decrypted traffic
2. Your Privatemode API key lives only in encrypted memory
3. SSH keys are generated locally - Azure never has the private key
4. Let's Encrypt certificates are generated on the VM - private key never leaves the TEE

## What is End-to-End Encrypted AI?

When you send a prompt through this proxy, it goes to Privatemode's servers which run inside a special secure environment called a **Trusted Execution Environment (TEE)**.

Think of a TEE like a locked box that even the server owner can't open. Your prompts and the AI's responses are encrypted inside this box - **nobody can see your data**, not even Privatemode themselves.

- Your prompts are never logged
- Your data is never used for training
- Fully GDPR compliant

## How Requests Flow Through the System

Here's what happens when your application makes an API request:

1. **Your app sends a request** to this proxy (e.g., `POST /v1/chat/completions`)
2. **The proxy validates your API key** and checks rate limits
3. **The request is forwarded** to Privatemode's encrypted servers
4. **The AI model processes your request** inside the secure TEE
5. **The response comes back** through the proxy to your app

The entire chain is encrypted. Your prompts never exist in plaintext outside of the TEE.

## How We Track Usage Without Breaking Privacy

You might wonder: if everything is encrypted, how do we track token usage?

The answer is that **we only read the usage metadata** from the response - specifically the `usage` field that contains token counts. We never read, store, or log the actual prompt or response content.

```json
{
  "choices": [...],           // We ignore this - your actual content
  "usage": {
    "prompt_tokens": 25,      // We read this for billing
    "completion_tokens": 150, // We read this for billing
    "total_tokens": 175       // We read this for billing
  }
}
```

This means we can tell you how many tokens you used and calculate costs, but we have no idea what you actually asked the AI or what it responded with. Your conversations remain completely private.

## Available API Endpoints

This proxy supports the same endpoints as the OpenAI API. All endpoints require authentication via the `Authorization: Bearer YOUR_KEY` header.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/chat/completions` | Chat with AI models |
| `POST` | `/v1/embeddings` | Generate text embeddings for search/RAG |
| `POST` | `/v1/audio/transcriptions` | Convert audio to text (Whisper) |
| `GET` | `/v1/models` | List available models |
| `GET` | `/health` | Health check (no auth required) |

## Available Models

| Model | Type | Description |
|-------|------|-------------|
| `gpt-oss-120b` | Chat | Large general-purpose model |
| `gemma-3-27b` | Chat | Google's Gemma 3 27B |
| `qwen3-coder-30b-a3b` | Chat | Optimized for code generation |
| `qwen3-embedding-4b` | Embeddings | For vector search, RAG, semantic similarity |
| `whisper-large-v3` | Audio | Speech-to-text transcription |

## Pricing

All prices are in Euros. Usage is tracked in the admin panel.

| Model Type | Price |
|------------|-------|
| Chat Models (gpt-oss-120b, gemma-3-27b, qwen3-coder) | €5.00 per 1M tokens |
| Text Embeddings (qwen3-embedding-4b) | €0.13 per 1M tokens |
| Speech to Text (whisper-large-v3) | €0.096 per megabyte |

## Features

- **End-to-End Encryption**: TLS termination inside the TEE
- **API Key Authentication**: Manage access with your own API keys
- **Admin Web UI**: Browser-based key management and usage monitoring
- **Rate Limiting**: Per-key and global rate limiting
- **Usage Tracking**: Token usage and cost tracking per API key
- **Hot Reload**: Zero-downtime key rotation
- **Non-root Container**: Runs as unprivileged user

---

## Deployment Guide

### Prerequisites

- Azure subscription with Confidential VM quota
- Azure CLI installed (`brew install azure-cli` on macOS)
- A domain name you control (for TLS certificates)
- SSH key pair (we'll generate this locally for security)

### Step 1: Generate SSH Keys Locally

**Important**: Generate SSH keys on your local machine, not in Azure. This ensures Azure never has access to your private key.

```bash
ssh-keygen -t ed25519 -f ~/.ssh/azure-privatemode -C "privatemode-cvm" -N ""
```

This creates:
- `~/.ssh/azure-privatemode` - Private key (keep this safe, never share)
- `~/.ssh/azure-privatemode.pub` - Public key (this goes to Azure)

### Step 2: Login to Azure

```bash
az login
az account show  # Verify your subscription
```

### Step 3: Create Resource Group

Choose a region that supports AMD SEV-SNP confidential VMs:
- `eastus`, `westus`, `westeurope`, `northeurope`

```bash
az group create --name privatemode-rg --location eastus
```

### Step 4: Create the Confidential VM

This creates a VM with AMD SEV-SNP memory encryption:

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

Note the `publicIpAddress` in the output - you'll need this for DNS.

**VM Size Options:**
| Size | vCPUs | RAM | Use Case |
|------|-------|-----|----------|
| Standard_DC2as_v5 | 2 | 8GB | Development/Testing |
| Standard_DC4as_v5 | 4 | 16GB | Light Production |
| Standard_DC8as_v5 | 8 | 32GB | Production |

### Step 5: Open Firewall Ports

```bash
az vm open-port --resource-group privatemode-rg --name privatemode-cvm --port 443 --priority 1010
az vm open-port --resource-group privatemode-rg --name privatemode-cvm --port 80 --priority 1020
```

Port 80 is needed temporarily for Let's Encrypt certificate verification.

### Step 6: Configure DNS

Add an A record pointing your domain to the VM's public IP:

| Type | Name | Value |
|------|------|-------|
| A | `privatemode` | `<your-vm-public-ip>` |

Wait for DNS propagation (check with `dig yourdomain.com`).

### Step 7: Verify AMD SEV-SNP is Active

SSH into the VM and verify confidential computing is enabled:

```bash
ssh -i ~/.ssh/azure-privatemode azureuser@<your-vm-ip>

# Check AMD SEV-SNP status
sudo dmesg | grep -i sev
```

You should see:
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

Install Certbot and get a Let's Encrypt certificate:

```bash
sudo apt-get install -y certbot
sudo certbot certonly --standalone --non-interactive \
  --agree-tos --email your@email.com \
  -d yourdomain.com
```

Copy certificates to a directory for Docker:

```bash
mkdir -p ~/privatemode/certs
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ~/privatemode/certs/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ~/privatemode/certs/key.pem
sudo chown -R $USER:$USER ~/privatemode/certs
```

### Step 10: Prepare Configuration

Create the secrets directory and API keys file:

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

Copy the project files to the VM:

```bash
# From your local machine
scp -i ~/.ssh/azure-privatemode -r Dockerfile supervisord.conf auth-proxy \
  azureuser@<your-vm-ip>:~/privatemode/
```

Build and run:

```bash
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

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PRIVATEMODE_API_KEY` | Yes | - | Your Privatemode API key |
| `ADMIN_PASSWORD` | Yes | - | Password for admin web UI |
| `API_KEYS_FILE` | No | `/app/secrets/api_keys.json` | Path to API keys JSON |
| `TLS_CERT_FILE` | No | - | Path to TLS certificate |
| `TLS_KEY_FILE` | No | - | Path to TLS private key |
| `FORCE_HTTPS` | No | `true` when TLS enabled | Reject non-HTTPS requests |
| `TRUST_PROXY` | No | `false` | Trust X-Forwarded-* headers |
| `RATE_LIMIT_REQUESTS` | No | `100` | Global rate limit (requests/window) |
| `RATE_LIMIT_WINDOW` | No | `60` | Rate limit window (seconds) |
| `IP_RATE_LIMIT_REQUESTS` | No | `1000` | Per-IP rate limit |
| `IP_RATE_LIMIT_WINDOW` | No | `60` | Per-IP rate limit window |

## Security Architecture

### What Azure Cannot Access

With AMD SEV-SNP enabled:

| Component | Protected? | Notes |
|-----------|------------|-------|
| VM Memory | Yes | Encrypted by CPU, Azure has no keys |
| TLS Private Key | Yes | Lives only in encrypted memory |
| Privatemode API Key | Yes | Passed via env, stays in encrypted memory |
| SSH Private Key | Yes | Generated locally, never uploaded to Azure |
| Decrypted API Traffic | Yes | TLS terminates inside TEE |
| OS Disk (optional) | Yes | Can enable confidential disk encryption |

### What Azure Can Access

| Component | Notes |
|-----------|-------|
| Encrypted network traffic | Before TLS termination |
| VM metadata | Name, size, region, etc. |
| Disk contents (if not using confidential disk) | At-rest encryption still applies |
| Resource usage | CPU, memory, network metrics |

### Defense in Depth

1. **Hardware Layer**: AMD SEV-SNP encrypts all memory
2. **OS Layer**: Ubuntu with secure boot and vTPM
3. **Container Layer**: Non-root execution, minimal image
4. **Application Layer**: HTTPS enforcement, rate limiting, auth

## Certificate Renewal

Let's Encrypt certificates expire after 90 days. Set up auto-renewal:

```bash
# Test renewal
sudo certbot renew --dry-run

# The certbot systemd timer handles automatic renewal
sudo systemctl status certbot.timer
```

After renewal, copy the new certificates and restart the container:

```bash
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ~/privatemode/certs/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ~/privatemode/certs/key.pem
sudo docker restart privatemode
```

## Monitoring

### Container Logs

```bash
sudo docker logs -f privatemode
```

### Verify SEV-SNP Attestation

The privatemode-proxy logs show attestation verification:

```
level=INFO msg="Validate succeeded" validator.name=snp-0-GENOA
```

This confirms the workload is running in a genuine AMD SEV-SNP enclave.

## Cleanup

To delete all Azure resources:

```bash
az group delete --name privatemode-rg --yes --no-wait
```

## Troubleshooting

### "HTTPS required" error
Use `https://` in your URL. HTTP is rejected by default.

### Container won't start
```bash
sudo docker logs privatemode
```

### SEV-SNP not detected
Ensure you used `--security-type ConfidentialVM` when creating the VM.

### Certificate errors
Verify certificate paths and that the files are readable:
```bash
ls -la ~/privatemode/certs/
```

### Rate limit exceeded
Check headers for reset time, or adjust limits in admin UI.

## Admin Panel

Access the admin panel at `https://yourdomain.com/admin` using your `ADMIN_PASSWORD`.

### API Keys Tab

- **Generate new API keys** with optional expiration dates and rate limits
- **View all keys** with their status (active, revoked, expired)
- **Revoke or delete keys** instantly
- **Set per-key rate limits** that override global defaults

### Settings Tab

- **Privatemode connection status** - verify your upstream API key is configured
- **Global rate limits** - configure requests per minute across all keys
- **Per-IP rate limits** - prevent abuse from individual IP addresses

### Usage & Costs Tab

- **Total spend** in Euros for any time period
- **Token usage** broken down by API key and by model
- **Request counts** to see which keys are most active

### Documentation Tab

- In-app documentation explaining how the encryption works
- Code examples for Python and cURL
- Model and pricing information

## File Structure

```
privatemode/
├── Dockerfile              # Multi-stage build
├── supervisord.conf        # Process manager config
├── README.md
├── auth-proxy/
│   ├── server.py           # Main proxy server
│   ├── admin.py            # Admin UI
│   ├── config.py           # Configuration
│   ├── key_manager.py      # Key management
│   ├── usage_tracker.py    # Usage tracking
│   └── utils.py            # Utilities
├── scripts/
│   └── manage_keys.py      # Key management CLI
├── secrets/                # Gitignored
│   └── api_keys.json       # API keys storage
└── docs/                   # Azure documentation
```

## License

MIT
