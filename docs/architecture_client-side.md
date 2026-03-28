# Client

Version: 1.30

On this page

On the client side, the user interacts with the [Privatemode proxy](/guides/proxy-configuration), which effectively serves as the API endpoint for any inference requests to the LLM. Ideally, the proxy is deployed on the user's machine or within a secure and trusted network.

## Privatemode-proxy[​](#privatemode-proxy "Direct link to Privatemode-proxy")

The client-side Privatemode proxy acts as the trust anchor of the Privatemode API. Ensuring its integrity and authenticity during setup is crucial for maintaining the overall security of the system.

The Privatemode proxy performs three main tasks:

1. **Attesting the server side**:
   The Privatemode proxy verifies the [Contrast Coordinator](/architecture/server-side#contrast-coordinator) using remote attestation. This process indirectly confirms that the Coordinator

   * properly verifies all AI workers.
   * facilitates secure key exchanges.

   In essence, this step ensures the integrity and authenticity of Privatemode API's server side.
2. **Encrypting outgoing prompts and decrypting incoming responses**:
   Upon successful attestation, the Privatemode proxy exchanges a secret key with the AI worker via the [secret service](/architecture/server-side#secret-service). This key enables [end-to-end encryption](/architecture/encryption) between the Privatemode proxy and the confidential computing environment of the AI worker, ensuring private communication.
3. **Adding authorization to inference requests**:
   During [configuration](/guides/proxy-configuration), the Privatemode proxy is set up with an authorization token. This token is automatically added to all inference requests to authenticate and authorize them.

By performing these tasks, the Privatemode proxy ensures secure and trustworthy interactions between the client and the AI infrastructure.

* [Privatemode-proxy](#privatemode-proxy)