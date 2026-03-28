# Contrast integration

Version: 1.30

On this page

Privatemode is built on [Contrast](https://docs.edgeless.systems/contrast), which provides runtime, remote attestation, policy mechanism, and service mesh functionality for confidential container environments.
The components of Privatemode, which all run within the Contrast runtime, and their integration with Contrast are described in the [server-side architecture](/architecture/server-side#contrast-integration).

Attestation in Privatemode follows the [Contrast attestation model](https://docs.edgeless.systems/contrast/architecture/attestation), ensuring that all confidential workloads are verified before execution.
This document explains how Privatemode integrates with Contrast's attestation, focusing on manifests, policies, and GPU attestation.

## Contrast manifest[​](#contrast-manifest "Direct link to Contrast manifest")

Contrast enforces a [manifest](https://docs.edgeless.systems/contrast/components/overview#the-manifest), which defines the configuration and attestation properties for the entire Privatemode Kubernetes deployment.

### How Privatemode uses the manifest[​](#how-privatemode-uses-the-manifest "Direct link to How Privatemode uses the manifest")

1. Fetching the expected manifest

   * The Privatemode proxy retrieves the latest manifest from a CDN.
2. Verifying the Coordinator and the enforced manifest

   * Privatemode communicates with the Coordinator via the [Contrast SDK](https://github.com/edgelesssys/contrast/tree/main/sdk), embedded in the Privatemode proxy.
   * The Privatemode proxy verifies the integrity of the Coordinator through remote attestation
   * The Privatemode proxy verifies that the Coordinator's manifest matches the expected one.
3. Worker attestation

   * The Coordinator validates each GenAI worker's attestation evidence against the manifest-defined properties.
   * Only verified workers are allowed to join the [service mesh](/architecture/server-side#service-mesh).

For details on how Contrast manifests work, see the [Contrast documentation](https://docs.edgeless.systems/contrast/architecture/attestation).

## Policies[​](#policies "Direct link to Policies")

In Contrast, runtime policies are a mechanism to enable the use of the untrusted Kubernetes API for orchestration while ensuring the confidentiality and integrity of confidential container environments.

For more details on policy enforcement, refer to the [Contrast documentation](https://docs.edgeless.systems/contrast/components/policies).

## GPU Attestation[​](#gpu-attestation "Direct link to GPU Attestation")

Contrast supports forwarding GPUs into confidential containers but doesn't provide native GPU attestation.
Privatemode extends Contrast with an attestation mechanism for GPUs, ensuring that only verified GPUs are used.

### How Privatemode implements GPU attestation[​](#how-privatemode-implements-gpu-attestation "Direct link to How Privatemode implements GPU attestation")

* The [attestation-agent](/architecture/server-side#attestation-agent) in Privatemode verifies GPU evidence before allowing use.
* The attestation logic runs on the CPU, meaning its integrity is enforced by Contrast.
* Only attested GPUs are activated; unattested GPUs remain inaccessible to workers.

The attestation logic is packaged in a dedicated container: `ghcr.io/edgelesssys/privatemode/attestation-agent`

## Persistent volume verification[​](#persistent-volume-verification "Direct link to Persistent volume verification")

To serve LLMs, the AI worker has to load the model weights of any model it serves.
To reduce the loading time of the model weights, they're stored on disks that are attached to the AI workers.
These disks could contain malicious data or be used to extract data from the user.
To prevent both scenarios the model weight disks are attached as read only disks with integrity protection through dm-verity.
Mounting the disk is done through a dedicated container, the disk-mounter.
It receives the root hash of the disk it should mount as an argument.
Because container images and arguments are verified by Contrast the mounting of the disk as a whole is protected by Contrast.
This ensure the disk can't be used for data extraction (because it's mounted read-only) and doesn't contain malicious data (through the dm-verity root hash).

## Summary[​](#summary "Direct link to Summary")

Privatemode integrates with Contrast in the following ways:

1. **Contrast runtime**: the [server-side components](/architecture/server-side) run inside confidential containers provided through the Contrast runtime.
2. **Manifest-based attestation**: the Privatemode proxy verifies the deployment integrity through the Contrast manifest.
3. **Policy enforcement**: policies define and restrict kubelet interactions with the confidential container environment.
4. **GPU attestation**: privatemode extends Contrast with GPU attestation.

* [Contrast manifest](#contrast-manifest)
  + [How Privatemode uses the manifest](#how-privatemode-uses-the-manifest)
* [Policies](#policies)
* [GPU Attestation](#gpu-attestation)
  + [How Privatemode implements GPU attestation](#how-privatemode-implements-gpu-attestation)
* [Persistent volume verification](#persistent-volume-verification)
* [Summary](#summary)