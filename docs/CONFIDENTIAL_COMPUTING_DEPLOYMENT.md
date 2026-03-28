# Privatemode Auth Proxy: Confidential Computing Deployment Guide

## Executive Summary

This document outlines how to deploy the Privatemode Auth Proxy to Azure Confidential Computing infrastructure for 24/7 zero-trust operation, with end-to-end encrypted access back to user devices.

Your project is **already well-architected** for confidential computing deployment. The key additions needed are:
1. Attestation integration to prove TEE integrity
2. Secure Key Release (SKR) for secrets management
3. End-to-end encrypted channel for monitoring/access

---

## Recommended Deployment Architecture

### Option 1: Confidential Containers on Azure Container Instances (ACI) - **RECOMMENDED**

**Why this is best for your use case:**
- **Serverless**: No VM management, runs 24/7 automatically
- **Lift-and-shift**: Your existing Docker container works with minimal changes
- **Full attestation**: Hardware-backed proof of TEE integrity
- **Cost-effective**: Pay only for compute time
- **AMD SEV-SNP**: Memory encryption at hardware level

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    Azure Confidential Container Instance                  │
│                        (AMD SEV-SNP Hardware TEE)                        │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                     Container Group (Encrypted Memory)               │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │ │
│  │  │  SKR Sidecar     │  │ Privatemode Auth │  │  Attestation     │  │ │
│  │  │  Container       │◄─┤ Proxy Container  │──┤  Sidecar         │  │ │
│  │  │  (Key Release)   │  │  (Your App)      │  │  (MAA Client)    │  │ │
│  │  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  │ │
│  │           │                     │                     │            │ │
│  └───────────┼─────────────────────┼─────────────────────┼────────────┘ │
│              │                     │                     │              │
└──────────────┼─────────────────────┼─────────────────────┼──────────────┘
               │                     │                     │
               ▼                     ▼                     ▼
        ┌──────────────┐     ┌──────────────┐      ┌──────────────┐
        │  Azure Key   │     │  Privatemode │      │   Microsoft  │
        │  Vault (SKR) │     │     API      │      │    Azure     │
        │  + Managed   │     │  (Encrypted) │      │  Attestation │
        │     HSM      │     │              │      │    (MAA)     │
        └──────────────┘     └──────────────┘      └──────────────┘
```

### Option 2: Confidential VM with Docker

**When to use:**
- Need full VM control
- Require custom OS configurations
- Long-running workloads with persistent state

**VM Options:**
- DCasv5-series (AMD SEV-SNP, General Purpose)
- ECasv5-series (AMD SEV-SNP, Memory Optimized)

---

## Zero-Trust Security Architecture

### 1. Hardware-Level Protection (AMD SEV-SNP)

Your container runs in a Trusted Execution Environment where:
- **Memory is encrypted** with a per-VM key managed by AMD hardware
- **Azure operators cannot access** your container's memory or secrets
- **Hypervisor is untrusted** - cannot read TEE contents
- **Boot integrity** verified before container starts

### 2. Attestation Flow (Proving TEE Integrity)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │     │   TEE       │     │   Microsoft │     │  Azure Key  │
│   Device    │     │ Container   │     │   Azure     │     │   Vault     │
│             │     │             │     │ Attestation │     │    (SKR)    │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │                   │
       │  1. Request       │                   │                   │
       │  Connection       │                   │                   │
       │──────────────────>│                   │                   │
       │                   │                   │                   │
       │                   │ 2. Get AMD SEV-SNP│                   │
       │                   │    Hardware Report│                   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │ 3. JWT Token with │                   │
       │                   │    TEE Claims     │                   │
       │                   │<──────────────────│                   │
       │                   │                   │                   │
       │                   │ 4. Request Key    │                   │
       │                   │    with MAA Token │                   │
       │                   │───────────────────┼──────────────────>│
       │                   │                   │                   │
       │                   │ 5. Key Released   │                   │
       │                   │    (if TEE valid) │                   │
       │                   │<──────────────────┼───────────────────│
       │                   │                   │                   │
       │ 6. E2E Encrypted  │                   │                   │
       │    Channel Ready  │                   │                   │
       │<──────────────────│                   │                   │
       │                   │                   │                   │
```

### 3. End-to-End Encrypted Access to TEE

**For your requirement of secure access back to user devices:**

#### Option A: TLS with TEE-Bound Certificates (Recommended)

```python
# Attestation-bound TLS certificate flow
# 1. Generate private key INSIDE the TEE
# 2. Get attestation token proving TEE integrity
# 3. Bind certificate to attestation claims
# 4. Only TEE can use this certificate
```

The TEE generates its TLS private key internally - it never exists outside the encrypted memory. Users can verify they're connected to a genuine TEE by:

1. **Certificate contains attestation claims** embedded in the cert
2. **MAA signature** on the attestation token
3. **Client-side verification** of TEE properties before sending sensitive data

#### Option B: Secure Key Release for TLS Certificates

Store your TLS private key in Azure Key Vault with an SKR policy that only releases it to verified TEEs:

```json
{
    "version": "1.0.0",
    "anyOf": [
        {
            "authority": "https://sharedeus.eus.attest.azure.net",
            "allOf": [
                {
                    "claim": "x-ms-attestation-type",
                    "equals": "sevsnpvm"
                },
                {
                    "claim": "x-ms-compliance-status",
                    "equals": "azure-compliant-uvm"
                },
                {
                    "claim": "x-ms-sevsnpvm-hostdata",
                    "equals": "<YOUR_CONTAINER_POLICY_HASH>"
                }
            ]
        }
    ]
}
```

#### Option C: Client Attestation Verification

Users can verify the TEE before trusting it:

```python
# Client-side attestation verification
import requests

def verify_tee_connection(endpoint):
    # 1. Request attestation report from the TEE
    attestation = requests.get(f"{endpoint}/attestation")

    # 2. Verify with Microsoft Azure Attestation
    maa_response = requests.post(
        "https://sharedeus.eus.attest.azure.net/attest/SevSnpVm",
        json={"report": attestation.json()["raw_report"]}
    )

    # 3. Validate claims
    claims = decode_jwt(maa_response.json()["token"])

    assert claims["x-ms-attestation-type"] == "sevsnpvm"
    assert claims["x-ms-compliance-status"] == "azure-compliant-uvm"

    # 4. Now establish TLS connection with confidence
    return True
```

---

## Implementation Steps

### Phase 1: Prepare Container for Confidential Computing

**Minimal changes to your existing Dockerfile:**

```dockerfile
# Your existing Dockerfile works as-is
# Add attestation sidecar integration

FROM python:3.12-slim

# ... your existing setup ...

# Add attestation client library
RUN pip install azure-security-attestation azure-identity

# Add health endpoint that includes attestation status
# (Modify server.py to add /attestation endpoint)
```

### Phase 2: Create Confidential Computing Enforcement Policy

Generate a CCE policy that defines what can run in your container group:

```bash
# Install the confcom extension
az extension add --name confcom

# Generate policy from your ARM template
az confcom acipolicygen \
    --template-file deployment.json \
    --output-type rego
```

### Phase 3: Deploy to Azure Container Instances

**ARM Template for Confidential ACI:**

```json
{
    "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
    "resources": [
        {
            "type": "Microsoft.ContainerInstance/containerGroups",
            "apiVersion": "2023-05-01",
            "name": "privatemode-confidential",
            "location": "eastus",
            "properties": {
                "sku": "Confidential",
                "containers": [
                    {
                        "name": "privatemode-proxy",
                        "properties": {
                            "image": "yourregistry.azurecr.io/privatemode-auth-proxy:latest",
                            "ports": [{"port": 443, "protocol": "TCP"}],
                            "resources": {
                                "requests": {"cpu": 1, "memoryInGB": 2}
                            },
                            "environmentVariables": [
                                {"name": "ADMIN_PASSWORD", "secureValue": "[parameters('adminPassword')]"},
                                {"name": "MAA_ENDPOINT", "value": "https://sharedeus.eus.attest.azure.net"}
                            ]
                        }
                    },
                    {
                        "name": "skr-sidecar",
                        "properties": {
                            "image": "mcr.microsoft.com/aci/skr:2.3",
                            "ports": [{"port": 9000, "protocol": "TCP"}],
                            "resources": {
                                "requests": {"cpu": 0.5, "memoryInGB": 0.5}
                            },
                            "environmentVariables": [
                                {"name": "SkrSideCarArgs", "value": "..."}
                            ]
                        }
                    }
                ],
                "confidentialComputeProperties": {
                    "ccePolicy": "<BASE64_ENCODED_POLICY>"
                },
                "osType": "Linux",
                "ipAddress": {
                    "type": "Public",
                    "ports": [{"port": 443, "protocol": "TCP"}]
                }
            }
        }
    ]
}
```

### Phase 4: Add Attestation Endpoint to Your Proxy

**Add to `auth-proxy/server.py`:**

```python
import os
import json
import subprocess

@app.route('/attestation', methods=['GET'])
def get_attestation():
    """
    Returns attestation proof that this service runs in a genuine TEE.
    Clients can verify this with Microsoft Azure Attestation.
    """
    try:
        # Get raw AMD SEV-SNP report from hardware
        # In ACI, this comes from the attestation sidecar
        response = requests.get("http://localhost:9000/attest/raw")
        raw_report = response.json()

        # Get MAA token
        maa_endpoint = os.environ.get("MAA_ENDPOINT", "https://sharedeus.eus.attest.azure.net")
        maa_response = requests.post(
            f"{maa_endpoint}/attest/SevSnpVm?api-version=2022-08-01",
            json={"report": raw_report["report"]},
            headers={"Content-Type": "application/json"}
        )

        return jsonify({
            "tee_type": "AMD SEV-SNP",
            "attestation_token": maa_response.json()["token"],
            "verification_endpoint": maa_endpoint,
            "instructions": "Decode the JWT to verify TEE claims"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/attestation/verify', methods=['POST'])
def verify_client_nonce():
    """
    Client provides a nonce to be included in attestation.
    Proves freshness - attestation is for THIS connection.
    """
    nonce = request.json.get("nonce")
    # Include nonce in attestation report
    # Return signed attestation containing the nonce
    pass
```

### Phase 5: Secure Key Management with SKR

**Retrieve secrets only inside the TEE:**

```python
# secrets_manager.py
import os
from azure.identity import ManagedIdentityCredential
from azure.keyvault.keys import KeyClient
from azure.keyvault.keys.crypto import CryptographyClient

class ConfidentialSecretsManager:
    def __init__(self):
        self.credential = ManagedIdentityCredential()
        self.key_vault_url = os.environ.get("KEY_VAULT_URL")
        self.maa_endpoint = os.environ.get("MAA_ENDPOINT")

    async def get_tls_key(self):
        """
        Retrieves TLS private key from Key Vault using Secure Key Release.
        Key is only released if we're running in a valid TEE.
        """
        # 1. Get attestation token from hardware
        attestation_token = await self._get_attestation_token()

        # 2. Request key release from Azure Key Vault
        key_client = KeyClient(self.key_vault_url, self.credential)

        released_key = key_client.release_key(
            name="tls-private-key",
            target_attestation_token=attestation_token
        )

        return released_key.value

    async def _get_attestation_token(self):
        # Get from SKR sidecar
        response = await aiohttp.get("http://localhost:9000/attest/maa")
        return response.json()["token"]
```

---

## Monitoring in Zero-Trust Environment

### Secure Logging Options

Since you need visibility into what's happening inside the TEE:

#### Option 1: Encrypted Log Streaming

```python
# All logs encrypted before leaving TEE
import nacl.secret
import nacl.utils

class SecureLogger:
    def __init__(self, client_public_key):
        # Key exchange with client
        self.box = nacl.secret.SecretBox(shared_key)

    def log(self, message):
        encrypted = self.box.encrypt(message.encode())
        # Send to logging endpoint - only client can decrypt
        requests.post(LOG_ENDPOINT, data=encrypted)
```

#### Option 2: Attestation-Bound Admin Access

Your existing admin UI works, but add attestation verification:

```python
@app.route('/admin/login', methods=['POST'])
def admin_login():
    # Existing auth check
    if not verify_admin_password(request.form['password']):
        return "Unauthorized", 401

    # NEW: Include attestation in session
    session['attestation_time'] = time.time()
    session['attestation_token'] = get_current_attestation()

    # Client can verify they're connected to genuine TEE
    return jsonify({
        "session": session_id,
        "attestation": session['attestation_token']
    })
```

#### Option 3: Metrics via Azure Monitor (TEE-Compatible)

```python
# Azure Monitor integration works inside confidential containers
from opencensus.ext.azure import metrics_exporter

exporter = metrics_exporter.new_metrics_exporter(
    connection_string=os.environ.get("APPINSIGHTS_CONNECTION_STRING")
)

# Metrics are sent encrypted over TLS
# No secrets exposed - just operational metrics
```

---

## E2E Encryption Back to User Device

### Architecture for Secure Client Access

```
┌─────────────────┐                              ┌─────────────────────────┐
│   User Device   │                              │  Confidential Container │
│                 │                              │        (TEE)            │
│  ┌───────────┐  │     1. Get Attestation       │  ┌──────────────────┐  │
│  │  Client   │  │◄────────────────────────────►│  │ Attestation API  │  │
│  │   App     │  │                              │  └──────────────────┘  │
│  │           │  │     2. Verify TEE Claims     │                        │
│  │           │  │         (via MAA)            │                        │
│  │           │  │                              │                        │
│  │           │  │     3. TLS Handshake         │  ┌──────────────────┐  │
│  │           │  │◄────────────────────────────►│  │  TLS Termination │  │
│  │           │  │    (TEE-generated keys)      │  │  (Inside TEE)    │  │
│  │           │  │                              │  └──────────────────┘  │
│  │           │  │                              │                        │
│  │           │  │     4. E2E Encrypted         │  ┌──────────────────┐  │
│  │           │  │◄────────────────────────────►│  │ Privatemode Proxy│  │
│  │           │  │        API Calls             │  │    (Your App)    │  │
│  └───────────┘  │                              │  └──────────────────┘  │
│                 │                              │                        │
└─────────────────┘                              └─────────────────────────┘
```

### Client-Side Verification Code

```python
# client_sdk.py - for users of your service
import requests
import jwt

class ConfidentialPrivatemodeClient:
    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.verified = False

    def verify_tee(self):
        """Verify we're connecting to a genuine TEE before sending data."""
        # 1. Get attestation from server
        resp = requests.get(f"{self.endpoint}/attestation")
        attestation = resp.json()

        # 2. Decode and verify JWT token
        # (In production, verify signature with MAA public key)
        claims = jwt.decode(
            attestation["attestation_token"],
            options={"verify_signature": False}  # For demo; verify in production
        )

        # 3. Check required claims
        tee_info = claims.get("x-ms-isolation-tee", {})

        if tee_info.get("x-ms-attestation-type") != "sevsnpvm":
            raise SecurityError("Not running on AMD SEV-SNP hardware")

        if tee_info.get("x-ms-compliance-status") != "azure-compliant-uvm":
            raise SecurityError("TEE not Azure compliant")

        self.verified = True
        return claims

    def chat(self, messages, api_key):
        """Make API call only if TEE verified."""
        if not self.verified:
            self.verify_tee()

        return requests.post(
            f"{self.endpoint}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"messages": messages}
        )
```

---

## Cost Estimates

| Component | Monthly Estimate |
|-----------|-----------------|
| Confidential ACI (1 vCPU, 2GB) | ~$50-80 |
| Azure Key Vault Premium (SKR) | ~$5-10 |
| Azure Attestation | Free |
| Networking/Bandwidth | ~$10-20 |
| **Total** | **~$65-110/month** |

For 24/7 operation, Confidential ACI is cost-effective vs. maintaining a VM.

---

## Security Guarantees Summary

| Threat | Protection |
|--------|-----------|
| Cloud operator accessing data | AMD SEV-SNP memory encryption |
| Malicious Azure admin | Hardware-enforced isolation |
| Container escape | TEE boundary enforcement |
| Key theft | Secure Key Release (keys never leave TEE) |
| MITM attack | TLS with TEE-bound certificates |
| Replay attacks | Attestation with client nonce |
| Compromised client | Server-side attestation verification |

---

## Next Steps

1. **Immediate**: Add `/attestation` endpoint to your proxy
2. **Week 1**: Set up Azure Key Vault with SKR policy
3. **Week 2**: Generate CCE policy and test ACI deployment
4. **Week 3**: Implement client-side verification SDK
5. **Week 4**: Production deployment with monitoring

---

## References

- [Azure Confidential Containers on ACI](https://learn.microsoft.com/en-us/azure/container-instances/container-instances-confidential-overview)
- [Secure Key Release with AKV](https://learn.microsoft.com/en-us/azure/confidential-computing/concept-skr-attestation)
- [Microsoft Azure Attestation](https://learn.microsoft.com/en-us/azure/attestation/overview)
- [Confidential Sidecar Containers (GitHub)](https://github.com/microsoft/confidential-sidecar-containers)
