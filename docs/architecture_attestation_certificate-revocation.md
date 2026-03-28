# Certificate revocation

Version: 1.30

On this page

Privatemode relies on certificates for verifying attestation reports of external components such as NVIDIA GPUs.
The certificate issuer (e.g., NVIDIA) is responsible for informing the verifiers (e.g., Privatemode) about revocation
of certificates. Attestation certificates of NVIDIA are revoked if the component they're issued for is found to
contain a vulnerability, for example.

In such a case, Privatemode can't use the affected component securely anymore. However, users might not be able
to tolerate an unexpected downtime because of the revocation of a certificate, and might want to ignore the revocation
for a specific grace period at the expense of security.

For this reason, Privatemode offers configuration options to delegate the decision about the security-availability trade-off
to the user.

## NVIDIA Certificates[​](#nvidia-certificates "Direct link to NVIDIA Certificates")

NVIDIA manages certificate revocation via their [OCSP service](https://docs.nvidia.com/attestation/technical-docs-ocsp/latest/ocsp_introduction.html).
For each of the NVIDIA components, namely GPU, driver, and VBIOS, NVIDIA issues a certificate which is verified during the
attestation process. Privatemode exposes three different certificate revocation states for each
of the components:

* **Good**: The certificate hasn't been revoked.
* **Unknown**: The OCSP service couldn't be reached or doesn't provide information about this certificate.
* **Revoked**: The certificate has been revoked.

The `privatemode-proxy` application offers two settings to configure how the OCSP service's responses should be handled
and exposes them via command-line flags:

* `nvidiaOCSPAllowUnknown`: Whether the "unknown" OCSP status (i.e., OCSP is unreachable or doesn't provide information
  about this certificate) should be tolerated. (Default: `true`)
* `nvidiaOCSPRevokedGracePeriod`: How long "revoked" OCSP responses should be accepted for after the revocation time, in
  hours. A value of `0` means that "revoked" OCSP responses aren't accepted at all. (Default: `48`)

For example, to only allow "good" OCSP responses, you can set `--nvidiaOCSPAllowUnknown=false --nvidiaOCSPRevokedGracePeriod=0`  
when launching the Privatemode proxy.

* [NVIDIA Certificates](#nvidia-certificates)