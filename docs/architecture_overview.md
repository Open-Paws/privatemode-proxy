# Overview

Version: 1.30

On this page

The architecture of the Privatemode API is designed to:

1. **Provide strict confidentiality** for your AI interactions.
2. **Make confidentiality and security transparently verifiable** from the client.

## Components[​](#components "Direct link to Components")

Various components on both the client and server sides are crucial for achieving these security features. They're explained in the following.

![Overview of the Privatemode architecture](/assets/images/architecture-8a2852e567efac45f1ed22fa1c545eb5.svg)

### Client[​](#client "Direct link to Client")

On the client side, a single component is essential.

**The Privatemode proxy** is run by the user and has two main responsibilities:

* Verifies the integrity and authenticity of the service before any inference communication begins.
* Encrypts all inference requests and decrypts AI responses.

As it handles all communication with the service, we also refer to it simply as the *client* or *client-software*.

### Server[​](#server "Direct link to Server")

The server architecture is designed to strictly isolate any Privatemode service from the rest of the infrastructure, preventing external access or unintended data leaks while ensuring confidential data processing.

**Confidential Computing Environments (CCE)** are set up to:

* Ensure strong isolation of all service components from the infrastructure and environment.
* Enforce runtime encryption of all data processed by the service.
* Provide provider-independent and transparent hash generation for integrity and authenticity verification.

The **Contrast Coordinator** runs within a CCE and serves as the central attestation and policy enforcement component. It ensures that only verified workloads operate within Privatemode and facilitates:

* Performing remote attestation for GenAI inference and secret service instances, validating their integrity before they process any requests.
* Enforcing security policies that ensure the integrity of the inference and secret service throughout their lifetime.
* Facilitating secure key exchange between the client and the GenAI inference service by providing authentication credentials, bound to the remote attestation, to the inference and secret service.

The **Secret Service** runs within a CCE and serves as the central key management component:

* Authenticates towards the client with the Coordinator-provided credentials.
* Accepts and stores encryption keys from the client.
* Releases keys only to successfully verified GenAI workers.

**AI workers** run within CCEs, securely process inference requests, and ensure that models never learn from inference data. Each AI worker consists of:

* **Attestation agent**: Attests the GPU and sets it to ready state when successful.
* **AI code** handles incoming requests and consists of:
  + **Encryption proxy**: Decrypts incoming requests and encrypts outgoing responses, independent of the CC-based runtime encryption.
  + **Disk mounter**: Securely mounts disks containing stored model weights as read-only devices while ensuring data integrity.
  + **Inference code**: [vLLM](https://github.com/vllm-project/vllm) is used to generate responses based on the incoming prompts.

## Architectural principles[​](#architectural-principles "Direct link to Architectural principles")

The Privatemode API is built for seamless integration while maintaining strict confidentiality in all data interactions. This is achieved through our core architectural principles.

### Seamless integration[​](#seamless-integration "Direct link to Seamless integration")

The Privatemode API is designed for seamless usage and easy integration, handling all the complexities of confidential computing behind the scenes. On the client side, the key component is the [Privatemode proxy](/guides/proxy-configuration), which manages remote attestation and end-to-end encryption.

### Verifiable security[​](#verifiable-security "Direct link to Verifiable security")

Remote attestation is a cornerstone of confidential computing, and it plays a critical role in Privatemode.

In the context of Privatemode, the client uses remote attestation to verify that all server-side software components are both trustworthy and in their intended state. By leveraging independent cryptographic certificates and hardware-enforced signatures, remote attestation ensures that the GenAI endpoint is genuinely confidential, securely isolated, and running valid, trusted AI code.

The public source code, combined with reproducible builds, ensures complete transparency in both the verification process and the security of our service for all API users.

Successful remote attestation is always the necessary precondition for any key exchange and prompt transfer.

To learn more about attestation in Privatemode, visit the dedicated [section](/architecture/attestation/overview).

### End-to-end encryption[​](#end-to-end-encryption "Direct link to End-to-end encryption")

By verifying the server side through remote attestation, the client ensures that prompt encryption keys are securely exchanged and stored. These keys are never shared with anyone except the Privatemode proxy on the client side and the AI worker running isolated within a CCE on the server side.

Using modern encryption schemes to secure all prompts and responses, this ensures a confidential channel between the user and the AI.

You can find more details in our [encryption](/architecture/encryption) section.

### Protection against learning[​](#protection-against-learning "Direct link to Protection against learning")

Some attacks, known as training data extraction attacks, allow user data to be extracted directly from a model through clever prompting if the user data was used for model training.

We can never access your prompts, thus we can't train our models on your data. As a result, our AI models will never retain any information from your prompts. This ensures that no other API user can extract your data. Since the source code is public, this is fully transparent and verifiable by anyone.

### Protection against the infrastructure[​](#protection-against-the-infrastructure "Direct link to Protection against the infrastructure")

The Privatemode API uses confidential computing to shield the *AI worker* that processes your prompts on the server side. Essentially, the AI worker is a virtual machine (VM) that has access to an AI accelerator like the Nvidia H100 and runs some *AI code*. The AI code loads an AI model onto the accelerator, pre-processes prompts, and feeds them to the AI model. Privatemode applies confidential computing to both VM and the AI accelerator and establishes a secure connection between the two.

With this approach, Privatemode shields the AI worker (and all data it processes) from the rest of the infrastructure. Here, "the infrastructure" includes the entire hardware and software stack that the AI worker runs on, as well as the people managing that stack.

Privatemode's server-side components run on Scaleway. Thus, Scaleway is "the infrastructure" and Privatemode's use of confidential computing ensures that Scaleway can't access any of your data.

### Protection against Edgeless Systems[​](#protection-against-edgeless-systems "Direct link to Protection against Edgeless Systems")

We, at Edgeless Systems, are your GenAI SaaS provider. Confidential computing ensures that GenAI endpoints operate in an isolated environment. Independent cryptographic certificates and key material are used to establish the CEE. This setup is verifiable by the client through remote attestation and guarantees that the endpoints are trustworthy and can't be manipulated by us.

The Privatemode API further ensures that all data exchanged with the AI is end-to-end encrypted. Prompts and responses remain private.

Public source code works hand-in-hand with confidential computing. Together, they establish a verifiable and confidential channel between you and the GenAI endpoint.

This design ensures that we can never access your data.

* [Components](#components)
  + [Client](#client)
  + [Server](#server)
* [Architectural principles](#architectural-principles)
  + [Seamless integration](#seamless-integration)
  + [Verifiable security](#verifiable-security)
  + [End-to-end encryption](#end-to-end-encryption)
  + [Protection against learning](#protection-against-learning)
  + [Protection against the infrastructure](#protection-against-the-infrastructure)
  + [Protection against Edgeless Systems](#protection-against-edgeless-systems)