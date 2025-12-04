# Confidential VM node pool support on AKS with AMD SEV-SNP confidential VMs

> **Source:** <https://learn.microsoft.com/en-us/azure/confidential-computing/confidential-node-pool-aks>

*Learn about confidential node pool support on AKS with AMD SEV-SNP confidential VMs*

[Azure Kubernetes Service (AKS)](/en-us/azure/aks/) makes it simple to deploy a managed Kubernetes cluster in Azure. In AKS, nodes of the same configuration are grouped together into node pools. These node pools contain the underlying VMs that run your applications.

AKS now supports confidential VM node pools with Azure confidential VMs. These confidential VMs are the [generally available DCasv5 and ECasv5 confidential VM-series](https://aka.ms/AMD-ACC-VMs-GA-Inspire-2022) utilizing 3rd Gen AMD EPYCTM processors with Secure Encrypted Virtualization-Secure Nested Paging ([SEV-SNP](https://www.amd.com/en/technologies/infinity-guard)) security features. To read more about this offering, [see the announcement](https://aka.ms/Ignite2022-CVM-Node-Pools-on-AKS-GA).

## Benefits

Confidential node pools leverage VMs with a hardware-based Trusted Execution Environment (TEE). AMD SEV-SNP confidential VMs deny the hypervisor and other host management code access to VM memory and state, and add defense in depth protections against operator access.

In addition to the hardened security profile, confidential node pools on AKS also enable:

* Lift and Shift with full AKS feature support - to enable a seamless lift-and-shift of Linux container workloads
* Heterogenous Node Pools - to store sensitive data in a VM-level TEE node pool with memory encryption keys generated from the chipset itself
* Cryptographically attest that your code will be executed on AMD SEV-SNP hardware with [an application to generate the hardware attestation report](https://github.com/Azure/confidential-computing-cvm-guest-attestation/blob/main/aks-linux-sample/cvm-attestation.yaml).

![Graphic of VM nodes in AKS with encrypted code and data in confidential VM node pools 1 and 2, on top of the hypervisor](media/confidential-vm-node-pools-on-aks/snp-on-aks-architecture-image.png)

Get started and add confidential node pools to existing AKS cluster with [this quick start guide](/en-us/azure/aks/use-cvm).

## Questions?

If you have questions about container offerings, please reach out to [acconaks@microsoft.com](mailto:acconaks@microsoft.com).

## Next steps

* [Deploy a confidential node pool in your AKS cluster](/en-us/azure/aks/use-cvm)
* Learn more about sizes and specs for [general purpose](/en-us/azure/virtual-machines/dcasv5-dcadsv5-series) and [memory-optimized](/en-us/azure/virtual-machines/ecasv5-ecadsv5-series) confidential VMs.
*Last scraped: 2025-12-04*
