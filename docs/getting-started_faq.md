# FAQ

Version: 1.30

On this page

## Questions[​](#questions "Direct link to Questions")

1. [How's the Privatemode API different from other GenAI APIs?](#q1)
2. [Can you see my prompts and the corresponding responses?](#q2)
3. [You run your service on Scaleway. Can't they see my data?](#q3)
4. [You use the OpenAI API standard. Is any data transferred to OpenAI?](#q4)
5. [Which data is processed by Edgeless Systems?](#q5)
6. [Is privatemode.ai down?](#q6)

---

### How's the Privatemode API different from other GenAI APIs?[​](#q1 "Direct link to How's the Privatemode API different from other GenAI APIs?")

In contrast to other GenAI APIs, the Privatemode API offers **dependable privacy and security properties**. Your prompts and responses always stay hidden from any third party, even from us, Edgeless Systems.

With other GenAI APIs, data can be accessed by third parties at various points when interacting with the AI. For example:

* **Infrastructure providers** like Microsoft or AWS have privileged access and control over the underlying hardware and system software. This means they can potentially access your prompts and responses.
* **GenAI service providers** like OpenAI also have the ability to access your data.

With the Privatemode API, your prompts and responses remain confidential. By design, neither Scaleway as the infrastructure provider nor Edgeless Systems as your service provider can access or leak your prompts or responses.

To ensure this, the Privatemode API leverages confidential computing, a cutting-edge technology that provides runtime encryption and protection for data. The Privatemode API applies confidential computing end-to-end and make this verifiable from the outside. With the help of confidential computing-based remote attestation, it's possible to verify the integrity and authenticity of the software of the entire Privatemode software stack.

This makes the Privatemode API fundamentally different from other GenAI APIs. You fully own your prompts and responses.

Feel free to dive deeper into Privatemode's [security properties](/security).

---

### Can you see my prompts and the corresponding responses?[​](#q2 "Direct link to Can you see my prompts and the corresponding responses?")

No. By leveraging confidential computing and providing hardware-enforced [end-to-end encryption](/security), Privatemode ensures that Edgeless Systems can't access your prompts or responses.

---

### You run your service on Scaleway. Can't they see my data?[​](#q3 "Direct link to You run your service on Scaleway. Can't they see my data?")

This is important to us: by design, our infrastructure provider **can't access** any of your prompts or responses.

The Privatemode API is based on confidential computing, and this is where it truly shines. Thanks to its strong, hardware-enforced confidentiality, even the infrastructure provider that controls the hardware and system software can't access any of your data.

---

### You use the OpenAI API standard. Is any data transferred to OpenAI?[​](#q4 "Direct link to You use the OpenAI API standard. Is any data transferred to OpenAI?")

No. The Privatemode API doesn't use any OpenAI services. It only adheres to the common OpenAI interface definitions (prompt and response format) to provide a convenient development experience and ensure easy code portability.

---

### Which data is processed by Edgeless Systems?[​](#q5 "Direct link to Which data is processed by Edgeless Systems?")

Prompts and responses are always encrypted and inaccessible to third parties. For monitoring purposes, the following metadata information is stored for up to 90 days:

* IP
* timestamp
* API key
* token usage
* request metadata: path, method, status code
* response time

Token usage for each API key is permanently stored for billing purposes.

### Is privatemode.ai down?[​](#q6 "Direct link to Is privatemode.ai down?")

You can check the status of the Privatemode API on the [status page](https://status.privatemode.ai/).

* [Questions](#questions)
  + [How's the Privatemode API different from other GenAI APIs?](#q1)
  + [Can you see my prompts and the corresponding responses?](#q2)
  + [You run your service on Scaleway. Can't they see my data?](#q3)
  + [You use the OpenAI API standard. Is any data transferred to OpenAI?](#q4)
  + [Which data is processed by Edgeless Systems?](#q5)
  + [Is privatemode.ai down?](#q6)