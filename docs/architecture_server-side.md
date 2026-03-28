# Server

Version: 1.30

On this page

The server side of Privatemode hosts the inference service and processes prompts securely. Its architecture is designed to be highly scalable while never compromising confidentiality.

It consists of three main parts:

* The AI inference application itself, the **workers**
* The **Contrast** framework for running the workers in a Confidential Computing Environment (CCE)
* A key management service, the **secret service**

## Workers[​](#workers "Direct link to Workers")

Workers are central to the backend. They host an AI model and serve inference requests. The necessary inference code and model are provided externally by the [platform and model provider](/security) respectively.

The containerized inference code, in the following referred to as *AI code*, runs in a secure and isolated environment.

Each worker is a [confidential container](https://docs.edgeless.systems/contrast/basics/confidential-containers) running in Contrast's [runtime environment](https://docs.edgeless.systems/contrast/components/runtime) that isolates containers, more precisely Kubernetes Pods, in confidential VMs (CVM).
The runtime CVM is minimal, immutable, and verifiable through remote attestation.
It's also described in the [Contrast documentation](https://docs.edgeless.systems/contrast/components/runtime#pod-vm-image).

### Inference code[​](#inference-code "Direct link to Inference code")

The inference code is provided by an external party, such as HuggingFace TGI, vLLM, NVIDIA Triton, and is frequently updated. In case of Privatemode, the inference code is currently provided by vLLM. It's included in the remote attestation flow.

This code operates within a confidential computing environment that encrypts all data in memory. Within this secure environment, the inference code can access user data. To ensure that the inference code doesn't leak user data, the system relies on remote attestation, enabling the client to review and verify the code's integrity and behavior before execution.

This architecture ensures that (1) the infrastructure can't access user data or the inference code, and (2) the inference code doesn't leak user data to unprotected memory, the disk, or the network.

### Confidential computing environment[​](#confidential-computing-environment "Direct link to Confidential computing environment")

Confidential Computing Environments (CCEs) provide robust hardware-based security and workload isolation.

While encryption in transit (TLS) and at rest (disk encryption) have become widespread, confidential computing completes data protection. It secures data at runtime—ensuring encryption throughout its entire lifecycle.

In Privatemode, all workloads run inside AMD SEV-SNP based Confidential VMs (CVMs).

With SEV-SNP, the memory of virtual machines (VMs) is encrypted. The processor manages encryption keys and ensures they're not accessible by untrusted software. Because encryption is hardware-accelerated, performance penalties are minimal. This reduces the attack surface, shielding workloads from:

* Unauthorized Access: Even if a malicious actor compromises the server-side system including the hypervisor or other VMs, SEV-SNP's encryption makes your data unreadable.
* Sophisticated Memory Attacks: SEV-SNP goes beyond confidentiality by adding integrity protection. It ensures that the data your VM reads is the same data it previously wrote, preventing tampering attempts.

### Integrating AI accelerators into the CCE[​](#integrating-ai-accelerators-into-the-cce "Direct link to Integrating AI accelerators into the CCE")

The Privatemode API currently leverages NVIDIA's H100 AI accelerators to process large language models (LLMs). The H100’s [confidential computing capabilities](https://www.nvidia.com/en-us/data-center/solutions/confidential-computing/) enable GPUs to be assigned to CVMs running on CPUs. This integration extends CCEs to include GPU workloads.

By using H100s, Privatemode applies key confidential computing features—such as remote attestation and isolation—to LLM processing, ensuring secure inference.

### Encryption proxy[​](#encryption-proxy "Direct link to Encryption proxy")

Each worker implements an encryption proxy responsible for encrypting and decrypting requests and responses as they enter or leave the CVM for inference. This doesn't affect the low-level runtime encryption of the CVM itself but ensures end-to-end encryption at the application level. Inside the CVM, your data remains protected from external access.

For a detailed explanation of the end-to-end encryption workflow, refer to the [Encryption](/architecture/encryption) section.

## Contrast Integration[​](#contrast-integration "Direct link to Contrast Integration")

Privatemode leverages [Contrast](/architecture/attestation/contrast-integration) to implement attestation.

### Contrast Coordinator[​](#contrast-coordinator "Direct link to Contrast Coordinator")

The [Contrast Coordinator](https://docs.edgeless.systems/contrast/components/overview#the-coordinator) acts as an attestation service and ensures that only verified workloads and infrastructure components participate in Privatemode.
It performs remote attestation for workers, provides them with credentials for authentication within the service mesh, and enforces [security policies](/architecture/attestation/contrast-integration#policies).

### Service Mesh[​](#service-mesh "Direct link to Service Mesh")

The [Contrast service mesh](https://docs.edgeless.systems/contrast/components/service-mesh) determines which services have been verified by the Coordinator and are allowed to communicate within Privatemode.

### Attestation Agent[​](#attestation-agent "Direct link to Attestation Agent")

The attestation agent is a Privatemode-specific component that handles GPU attestation.
It's running inside each worker as a separate container and responsible for:

* Verifying GPUs before they can be assigned to a worker.

### Disk mounter[​](#disk-mounter "Direct link to Disk mounter")

The disk mounter is a Privatemode-specific component that handles mounting model weight disks as read-only devices through dm-verity.
It's running inside each worker as a separate container and is responsible for:

* Use dm-verity to setup a verity device. This continuously checks the integrity of disk during use.
* Mount the model weights disk as read only.

## Secret Service[​](#secret-service "Direct link to Secret Service")

The secret service is a Privatemode-specific component responsible for secure key management and distribution.
It runs inside a confidential container through the Contrast runtime.
It ensures that encryption keys are only released to verified GenAI workers after successful attestation.

Its primary role is to:

* Store and manage encryption keys for GenAI workers.
* Release keys only to successfully verified GenAI workers.

* [Workers](#workers)
  + [Inference code](#inference-code)
  + [Confidential computing environment](#confidential-computing-environment)
  + [Integrating AI accelerators into the CCE](#integrating-ai-accelerators-into-the-cce)
  + [Encryption proxy](#encryption-proxy)
* [Contrast Integration](#contrast-integration)
  + [Contrast Coordinator](#contrast-coordinator)
  + [Service Mesh](#service-mesh)
  + [Attestation Agent](#attestation-agent)
  + [Disk mounter](#disk-mounter)
* [Secret Service](#secret-service)