# Verification of model integrity

Version: 1.30

On this page

Models deployed in Privatemode are stored on [dm-verity](https://docs.kernel.org/admin-guide/device-mapper/verity.html) protected disks.
This allows you to verify the integrity and content of a model before using it to process your data.

This guide describes how to reproduce the model disks deployed in Privatemode and obtain the expected root hashes.
See the [source code verification guide](/guides/verify-source) to learn how to verify that the hashes are enforced by the Privatemode deployment.

info

This is an optional workflow to build trust in Privatemode.
You can securely use Privatemode without performing these steps.

info

Some OS-specific settings, such as SELinux, can interfere with the disk setup.
To ensure reproducibility, we recommend running the verification on a fresh Ubuntu 24.04 system with [Docker engine](https://docs.docker.com/engine/install/ubuntu/) installed.

## Step 1: Inspect the Kubernetes deployment configuration[​](#step-1-inspect-the-kubernetes-deployment-configuration "Direct link to Step 1: Inspect the Kubernetes deployment configuration")

The repository contains several `storage-class-*.yaml` files defining [Kubernetes Storage Classes](https://kubernetes.io/docs/concepts/storage/storage-classes/) used to manage the storage of the model disks.
The following annotations are attached to each Storage Class and are needed to replicate the disk:

* `privatemode.edgeless.systems/disk_size_gb`: The size of the disk in gigabytes.
* `privatemode.edgeless.systems/model_source`: The URL of the model repository.
* `privatemode.edgeless.systems/commit_hash`: The commit hash of the model repository to download.
* `privatemode.edgeless.systems/root_hash`: The expected dm-verity root hash of the model disk.
* `privatemode.edgeless.systems/excluded_files`: A list of files or wildcards matching files in the model repository that are excluded from the final disk image to reduce size.
* `privatemode.edgeless.systems/build_version`: The Privatemode version used to create the disk image.

## Step 2: Build the disk image generator[​](#step-2-build-the-disk-image-generator "Direct link to Step 2: Build the disk image generator")

We provide a tool to create the model disk images that you can build from source:

1. Ensure your system meets the prerequisites:

   * Linux operating system (x86-64 architecture)
   * [Nix](https://nixos.org/)
     + To install Nix, we recommend the [Determinate Systems Nix installer](https://determinate.systems/posts/determinate-nix-installer/).
   * [Docker](https://docs.docker.com/engine/install/ubuntu/)
   * [jq](https://jqlang.org/download/)
2. Clone the source code repository at the version specified in the `privatemode.edgeless.systems/build_version` annotation of the Storage Class you want to verify:

   ```bash
   build_version=<the_version_from_the_annotation>  
   git clone --branch ${build_version} https://github.com/edgelesssys/privatemode-public  
   cd privatemode-public
   ```
3. Build the container image:

   ```bash
   nix build .#verity-disk-generator  
   docker load < result
   ```

## Step 3: Create a model disk image[​](#step-3-create-a-model-disk-image "Direct link to Step 3: Create a model disk image")

Using the disk information from [Step 1](#step-1-inspect-the-kubernetes-deployment-configuration) and the container you built in [Step 2](#step-2-build-the-disk-image-generator), you can now create a dm-verity protected replica of the model disk.

info

Depending on the repository, you may require a valid access token to download the model.
Follow the [Hugging Face documentation](https://huggingface.co/docs/hub/en/security-tokens) to generate your token.

Assuming you want to reproduce a model disk for `facebook/opt-125m` at commit `27dcfa74d334bc871f3234de431e71c6eeba5dd6`, with a disk size of 1 GB, and excluding files matching `example-file-*.txt`, which was built on version v1.24.0, run the following commands:

```bash
#!/usr/bin/env bash  
  
model_source="https://huggingface.co/facebook/opt-125m"  
commit_hash="27dcfa74d334bc871f3234de431e71c6eeba5dd6"  
disk_size_gb="1"  
excluded_files="example-file-*.txt"  
git_pat="your_git_pat" # leave empty if not required  
disk_image=model.disk  
build_version="v1.24.0"  
  
truncate -s ${disk_size_gb}G ${disk_image}  
touch repart.json  
  
docker run --rm -it \  
  --privileged \  
  -v "${PWD}/${disk_image}:/${disk_image}" \  
  -v "${PWD}/repart.json:/repart.json" \  
  -e GIT_PAT=${git_pat} \  
  -e EXCLUDE_GIT_FILES="${excluded_files}" \  
  "verity-disk-generator:${build_version}" \  
  "${disk_image}" "${model_source}" "${commit_hash}"
```

Retrieve the dm-verity root hash from the `repart.json` file:

```bash
jq -r '.[0].roothash' repart.json
```

This root hash should match the `privatemode.edgeless.systems/root_hash` annotation of the Storage Class you inspected in [Step 1](#step-1-inspect-the-kubernetes-deployment-configuration).

tip

Take a look at the [source code of Privatemode's disk-mounter](https://github.com/edgelesssys/privatemode-public/tree/main/disk-mounter) to learn how Privatemode verifies the integrity of a model at runtime.
Follow the [source code verification guide](/guides/verify-source) to learn how to verify and reproduce the binary of the disk-mounter.

* [Step 1: Inspect the Kubernetes deployment configuration](#step-1-inspect-the-kubernetes-deployment-configuration)
* [Step 2: Build the disk image generator](#step-2-build-the-disk-image-generator)
* [Step 3: Create a model disk image](#step-3-create-a-model-disk-image)