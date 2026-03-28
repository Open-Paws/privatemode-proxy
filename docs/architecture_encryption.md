# End-to-end prompt encryption

Version: 1.30

On this page

The Privatemode API uses end-to-end encryption to secure user data, ensuring that every component involved in processing an API call only handles encrypted information and can't access the original data. Prompts are encrypted on the client side, decrypted within runtime-encrypted workers, and re-encrypted before being returned to the client.

## Secure key exchange[​](#secure-key-exchange "Direct link to Secure key exchange")

Privatemode's key exchange protocol has two main goals:

1. Only initiate key exchange with verified and trusted AI workers.
2. Establish an end-to-end confidential channel on application level between the client and the AI workers.

### Workflow[​](#workflow "Direct link to Workflow")

1. **Key generation**: The client generates a symmetric key and securely stores it in the client's trusted environment.
2. **Secure key upload**: The client then interacts with the secret service to securely exchange encryption secrets. This involves the client verifying the Coordinator to ensure that it's interacting with a trusted and verified deployment. Once the Coordinator is verified, the client securely uploads the encryption key to the secret service.
3. **Key distribution to workers**: After the Coordinator verifies the AI workers through attestation, the secret service securely distributes the encryption keys to the appropriate AI workers. These workers use the keys to decrypt the prompts, process the data, and then re-encrypt the results before sending them back to the client.

The resulting flow is illustrated below:

## Encryption[​](#encryption "Direct link to Encryption")

The prompt and response encryption uses the exchanged symmetric key with [Authenticated Encryption](https://en.wikipedia.org/wiki/Authenticated_encryption) implemented through AES-GCM.

Prompts are encrypted by the client-side Privatemode proxy and decrypted by a server-side [encryption proxy](/architecture/server-side#encryption-proxy) hosted on the worker. Responses are handled accordingly where encryption is done by the server-side encryption proxy and decryption of the responses is performed by the client-side Privatemode proxy.

### Workflow[​](#workflow-1 "Direct link to Workflow")

1. **Request Encryption**: The client encrypts all request fields, except metadata required for routing and billing, like token length or model name, keeping them accessible to the service provider. The encrypted fields encode the key ID which maps to the used key.

   The following request fields aren't encrypted:

   * `model`
   * `stream_options`
   * `max_tokens`
   * `max_completion_tokens`
   * `n`
   * `stream`
2. **Request Decryption**: The server-side proxy decodes the encrypted fields with the key that maps to the encoded key ID. This doesn't affect the low-level runtime encryption provided by the [Confidential Computing Environment](/architecture/server-side#confidential-computing-environment).
3. **Prompt Processing**: The decrypted fields are securely transmitted to the inference server locally via a TCP socket.
4. **Response Encryption**: The response from the inference server is returned through the same socket. The server-side proxy then encrypts the response and sends it back to the client-side Privatemode proxy.

   The following response fields aren't encrypted:

   * `id`
   * `usage`

## Service provider isolation[​](#service-provider-isolation "Direct link to Service provider isolation")

The Coordinator and AI workers in Privatemode are designed to operate independently of us as the service provider, meaning that we've by no means access to your encryption keys. This security is reinforced during the remote attestation process, where the client not only verifies the Coordinator's integrity but also its identity. By inspecting the open-source code, clients can confirm that the Coordinator is configured to prevent any unauthorized access by the service provider, ensuring that all encryption keys remain secure and exclusively controlled by the client.

* [Secure key exchange](#secure-key-exchange)
  + [Workflow](#workflow)
* [Encryption](#encryption)
  + [Workflow](#workflow-1)
* [Service provider isolation](#service-provider-isolation)