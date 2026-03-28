# Overview

Version: 1.30

On this page

Attestation in Privatemode is a cornerstone of the API's security architecture, ensuring that all AI workloads are executed in a trusted environment. The attestation process verifies the integrity and authenticity of AI workers and the underlying infrastructure before any data processing or transfer begins. By leveraging attestation, the Privatemode API ensures that only verified and trusted code can operate, safeguarding both the confidentiality and integrity of your data.

info

If confidential computing and concepts like remote attestation are new to you, check out our [Confidential Computing Wiki](https://www.edgeless.systems/wiki) to learn more. In a nutshell, confidential computing is a technology that keeps data encrypted in memory—even during processing—and allows you to verify the integrity of workloads. This is ultimately enforced through special hardware extensions in modern processors and accelerators.

## Attestation flow in Privatemode[​](#attestation-flow-in-privatemode "Direct link to Attestation flow in Privatemode")

The attestation process in Privatemode is designed to provide end-to-end security across the entire service supply chain.
To verify software running on CPUs, Privatemode relies on [Contrast](https://docs.edgeless.systems/contrast/).
To understand how Contrast establishes trust in a given deployment, please review the [attestation in Contrast](https://docs.edgeless.systems/contrast/architecture/attestation).

Privatemode automates all necessary attestation steps.
The attestation verification logic—normally handled by the Contrast [CLI](https://docs.edgeless.systems/contrast/architecture/attestation#verifier-coordinator-and-cli) is embedded in the [Privatemode proxy](/guides/proxy-configuration).
In the following, "client" refers to the Privatemode proxy.

Contrast relies on a manifest to define the attestation evidence that must be enforced.
The Contrast service responsible for enforcing this evidence is the [Coordinator](https://docs.edgeless.systems/contrast/components/overview#the-coordinator).
Both the client and the Coordinator must be configured with the same [manifest](https://docs.edgeless.systems/contrast/components/overview#the-manifest) before attestation can proceed.

The steps to verify the Privatemode API are as follows:

1. **Client request:**

   * The client starts by requesting attestation evidence from the Privatemode backend.
   * It first verifies the identity and integrity of the Coordinator.
   * The client also ensures that its configured manifest matches the one enforced by the Coordinator.
   * Details of evidence validation can be found in the [Contrast documentation](https://docs.edgeless.systems/contrast/architecture/attestation#evidence-generation-and-appraisal).
2. **Service attestation and GPU verification:**

   * The [secret service](/architecture/server-side#secret-service) and [attestation-agent](/architecture/server-side#attestation-agent) contact the Coordinator to verify their attestation evidence.
   * If the Coordinator approves them, they're granted access to the [service mesh](/architecture/server-side#service-mesh).
   * The attestation-agent additionally verifies GPU attestation evidence for each AI worker.
   * GPUs require explicit activation:
     + If attestation is successful, the agent activates the GPU using the [NVIDIA Management Library (NVML)](https://docs.nvidia.com/deploy/nvml-api/group__nvmlDeviceQueries.html#group__nvmlDeviceQueries_1gebe1705165d701ffecc68f64364b8302).
     + Without activation, the GPUs remain inaccessible, ensuring that only attested GPUs can be used by Privatemode.
3. **Secret provisioning:**

   * Once verified, the client contacts the secret service and sets an encryption key for secure message exchange.
4. **Key distribution:**

   * The attestation-agent retrieves the encryption key from the secret service and delivers it to the GenAI worker.
   * The client encrypts the prompt before sending it to the worker.
   * This attestation-based key release ensures that only a verified GenAI worker can decrypt and process the data.
5. **Secure data processing:**

   * The GenAI worker executes the request inside a confidential VM, ensuring full isolation and security for the AI inference.
   * All processing happens within a trusted and attested environment.

## Chain of trust[​](#chain-of-trust "Direct link to Chain of trust")

In summary, there's a chain of trust based on cryptographic signatures that goes from the user to the GenAI backend via the attestation service.
This is illustrated in the following diagram. The client software corresponds to the Privatemode proxy.

* [Attestation flow in Privatemode](#attestation-flow-in-privatemode)
* [Chain of trust](#chain-of-trust)