# Microsoft Defender for Cloud integration

> **Source:** <https://learn.microsoft.com/en-us/azure/confidential-computing/guest-attestation-defender-for-cloud>

*Learn how you can use Microsoft Defender for Cloud with your Azure confidential VMs with the guest attestation feature installed.*

Azure *confidential virtual machines (confidential VMs)* are integrated with [Microsoft Defender for Cloud](/en-us/azure/defender-for-cloud/defender-for-cloud-introduction). Defender for Cloud continuously checks that your confidential VM is set up correctly and provides relevant recommendations and alerts.

To use Defender for Cloud with your confidential VM, you must have the [*guest attestation* feature](guest-attestation-confidential-vms) installed on the VM. For more information, see the [sample application for guest attestation](guest-attestation-example) to learn how to install the feature extension.

## Recommendations

If there's a configuration problem with your confidential VM, Defender for Cloud recommends changes.

### Enable secure boot

**Secure Boot should be enabled on supported Windows/Linux virtual machines**

This low-severity recommendation means that your confidential VM supports secure boot, but this feature is currently disabled.

This recommendation only applies to confidential VMs.

### Install guest attestation extension

**Guest attestation extension should be installed on supported Windows/Linux virtual machines**

This low-severity recommendation shows that your confidential VM doesn't have the guest attestation extension installed. However, secure boot and vTPM are already enabled. When you install this extension, Defender for Cloud can attest and monitor the *boot integrity* of your VMs proactively. Boot integrity is validated through remote attestation.

When you enable boot integrity monitoring, Defender for Cloud issues an assessment with the status of the remote attestation.

This feature is supported for Windows and Linux single VMs and uniform scale sets.

## Alerts

Defender for Cloud also detects and alerts you to VM health problems.

### VM attestation failure

**Attestation failed your virtual machine**

This medium-severity alert means that attestation failed for your VM. Defender for Cloud periodically performs attestation on your VMs, and after the VM boots.

This alert is only available for VMs with vTPM enabled and the guest attestation extension installed. Secure boot must also be enabled for the attestation to succeed. If you need to disable secure boot, you can choose to suppress this alert to avoid false positives.

Reasons for attestation failure include:

* The attested information, which includes the boot log, deviates from a trusted baseline. This problem might indicate that untrusted modules have loaded and the OS might be compromised.
* The attestation quote can't be verified to originate from the vTPM of the attested VM. This problem might indicate that malware is present, which might indicate that traffic to the vTPM is being intercepted.

## Next steps

* [Learn more about the guest attestation feature](guest-attestation-confidential-vms)
* [Learn to use a sample application with the guest attestation APIs](guest-attestation-example)
* [Learn about Azure confidential VMs](confidential-vm-overview)
*Last scraped: 2025-12-04*
