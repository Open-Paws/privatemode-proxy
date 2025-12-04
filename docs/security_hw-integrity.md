# Hardware integrity status

Version: 1.30

On this page

Hardware vulnerabilities can potentially affect the security properties of confidential-computing technologies. This document lists recently published vulnerabilities and their effect on Privatemode.

In the current version, Privatemode builds on AMD SEV-SNP and the confidential-computing features of the Nvidia H100.

Edgeless Systems, the company behind Privatemode, works closely with hardware vendors to ensure the mitigation of any potential hardware vulnerabilities ahead of time.

## Mitigation status[​](#mitigation-status "Direct link to Mitigation status")

| Vulnerability | CVE | Affected hardware | Potential impact (unmitigated) | Privatemode mitigation status | Privatemode mitigation description |
| --- | --- | --- | --- | --- | --- |
| [Heracles](https://heracles-attack.github.io/) | - | AMD SEV-SNP | Reads from CVM memory for expert attacker with root-level access to host | Mitigated ✅ | Combination of: (1) firmware patch from AMD, (2) kernel patch from Edgeless Systems, (3) corresponding client-side verification of remote attestation |
| [BadRAM](https://badram.eu/) | CVE-2024-21944 | AMD SEV-SNP | Access to CVM memory for expert attacker with hardware access and root-level access to host | Mitigated ✅ | Firmware patch from AMD |
| [Battering RAM](https://batteringram.eu/) | - | AMD SEV-SNP | Access to CVM memory for expert attacker with hardware access and root-level access to host | Mitigated ✅ | Attack only works for DDR4 RAM. Privatemode only uses 4th Gen AMD EPYC CPUs, which require DDR5. This is verified on the client via remote attestation. |
| [RMPocalypse](https://rmpocalypse.github.io/) | CVE-2025-0033 | AMD SEV-SNP | Access to CVM memory for expert attacker with root-level access to host | Mitigated ✅ | Firmware patch from AMD |
| [TEE.fail](https://tee.fail) | - | AMD SEV-SNP | Inferred reads from CVM memory for expert attacker with specialized hardware and combined physical access and root-level access to host | In progress | In progress |

note

The presence of firmware patches on the server side is verified on the client via remote attestation.

* [Mitigation status](#mitigation-status)