# Verification from source code

Version: 1.30

On this page

The Privatemode proxy uses [remote attestation](/architecture/attestation/overview) to verify the Privatemode deployment before using it.
This includes comparing cryptographic hashes of the deployment's code with reference values.
You can reproduce these reference values from the [public source code](https://github.com/edgelesssys/privatemode-public).
This proves the [security properties](/security) of Privatemode.

info

This is an optional workflow to build trust in Privatemode.
You can securely use Privatemode without performing these steps.

## Step 0: Build trust in Contrast[​](#step-0-build-trust-in-contrast "Direct link to Step 0: Build trust in Contrast")

[Privatemode uses Contrast](/architecture/attestation/contrast-integration), a tool to run confidential container deployments on Kubernetes.
The Contrast *Coordinator* as well as the application containers of Privatemode run in confidential computing environments (CCEs).
The Coordinator verifies the remote attestation statements of the application containers according to policies defined in the *manifest*.
The Privatemode proxy verifies the remote attestation statement of the Coordinator and checks that it enforces the expected manifest.
Thus, the Privatemode proxy effectively verifies the whole Privatemode deployment.

To trust Privatemode, you need to trust Contrast first.
Contrast is open source and you can reproducibly build it.
Check out the [documentation](https://docs.edgeless.systems/contrast) and the [source code](https://github.com/edgelesssys/contrast) to learn more.

The manifest contains

* reference values to verify the hardware-rooted attestation statement of the Coordinator
* and hashes of the policies that define the identities of the Pods that run the application containers.

The policies are generated from a Kubernetes deployment configuration.
The deployment configuration of Privatemode is part of the public source code, so you can reproduce the manifest as explained in the following steps.

## Step 1: Build container images to reproduce the image hashes from the source code[​](#step-1-build-container-images-to-reproduce-the-image-hashes-from-the-source-code "Direct link to Step 1: Build container images to reproduce the image hashes from the source code")

First, build all container images from source that are part of Privatemode's [Trusted Computing Base](https://www.edgeless.systems/wiki/what-is-confidential-computing/threat-model#trusted-computing-base) (TCB) to obtain their hashes.

1. Ensure your system meets the prerequisites:

   * Linux operating system (x86-64 architecture)
   * [Nix](https://nixos.org/)
     + To install Nix, we recommend the [Determinate Systems Nix installer](https://determinate.systems/posts/determinate-nix-installer/).
2. Clone the source code repository:

   ```bash
   git clone https://github.com/edgelesssys/privatemode-public  
   cd privatemode-public
   ```
3. Build the container images:

   ```bash
   scripts/calculate-image-digests.sh
   ```

The script builds the container images and writes their hashes to a file named `hashes-$host.json`, where `$host` is the hostname of your machine.

## Step 2: Inspect the Kubernetes deployment configuration[​](#step-2-inspect-the-kubernetes-deployment-configuration "Direct link to Step 2: Inspect the Kubernetes deployment configuration")

The repository contains the file `deployment.yaml` that defines the Kubernetes deployment configuration of Privatemode, which is enforced by Contrast.
Besides human-readable, auditable declarations, the file contains the hashes of container images and AI models used in the deployment:

* All container images are pinned by hashes. Verify that these match the hashes you obtained in step 1.
* The AI models are stored on dm-verity protected disks and mounted by the `disk-mounter` containers into the Pods. You can reproduce the hashes passed in the `--root-hash=` arguments as explained in the [model verification guide](/guides/verify-model).

## Step 3: Generate the Contrast manifest[​](#step-3-generate-the-contrast-manifest "Direct link to Step 3: Generate the Contrast manifest")

Run the following script to generate the manifest from the deployment configuration:

```bash
scripts/generate-manifest.sh
```

This creates the `manifest.json` file.

## Step 4: Compare the generated manifest with the manifest enforced by the Privatemode proxy[​](#step-4-compare-the-generated-manifest-with-the-manifest-enforced-by-the-privatemode-proxy "Direct link to Step 4: Compare the generated manifest with the manifest enforced by the Privatemode proxy")

To establish trust in the Privatemode proxy, you can compare its digest to the value you obtained in step 1.
You can get the digest with the following command:

```bash
docker inspect -f '{{.RepoDigests}}' ghcr.io/edgelesssys/privatemode/privatemode-proxy
```

Then open the `manifests` folder under the [proxy's workspace directory](/guides/proxy-configuration#automatically).
Verify that the manifest file referenced in the latest entry in `log.txt` matches the one you generated in step 3.

## Conclusion[​](#conclusion "Direct link to Conclusion")

You have now verified Privatemode's trust chain from the deployment's source code up to the Privatemode proxy's remote attestation verification.
This is the cryptographic proof of Privatemode's security claims.

* [Step 0: Build trust in Contrast](#step-0-build-trust-in-contrast)
* [Step 1: Build container images to reproduce the image hashes from the source code](#step-1-build-container-images-to-reproduce-the-image-hashes-from-the-source-code)
* [Step 2: Inspect the Kubernetes deployment configuration](#step-2-inspect-the-kubernetes-deployment-configuration)
* [Step 3: Generate the Contrast manifest](#step-3-generate-the-contrast-manifest)
* [Step 4: Compare the generated manifest with the manifest enforced by the Privatemode proxy](#step-4-compare-the-generated-manifest-with-the-manifest-enforced-by-the-privatemode-proxy)
* [Conclusion](#conclusion)