# Security

Version: 1.30

On this page

This page provides an overview of Privatemode's security properties. If user privacy and data protection are non-negotiable for you, the Privatemode API is the right choice.

## Security properties[​](#security-properties "Direct link to Security properties")

The Privatemode API delivers robust security features:

* **Confidentiality**:
  By design, all your prompts and responses remain private, meaning they're accessible only to you. Privatemode leverages confidential computing to enforce end-to-end encryption from the application, through the inference process by the GenAI, and back to the user.
* **Integrity and authenticity of the GenAI service**:
  Strong isolation within hardware-enforced Confidential Computing Environments (CCEs), combined with integrity and authenticity verification of the entire API infrastructure and code, ensures a thorough protection against tampering or malicious manipulation.

You can find details on how these security goals are achieved in the [Architecture](/architecture/overview) section.

## Verifiability[​](#verifiability "Direct link to Verifiability")

Privatemode's security and services are designed to be transparently verifiable. This is ensured by:

1. **[Public source code](https://github.com/edgelesssys/privatemode-public) combined with reproducible builds**
2. **Provider-independent, hardware-enforced cryptographic hashes of the service–enabled by CCEs**

(1) allows API users to audit the service and generate reference values, while (2) enables verification against the actual provided service.

This approach is fundamentally different from other GenAI services, as it provides truly verifiable confidentiality.
See the [Verification from source code](/guides/verify-source) and [Verification of model integrity](/guides/verify-model) guides for more details.

## Key benefits[​](#key-benefits "Direct link to Key benefits")

Compared to other conventional GenAI APIs, the Privatemode API offers strong privacy and data protection without compromising on inference capabilities. Below, we detail which parties typically have access to your data when using other conventional GenAI services and how Privatemode is different.

### Different roles in resolving a GenAI API call[​](#different-roles-in-resolving-a-genai-api-call "Direct link to Different roles in resolving a GenAI API call")

![Sketch of entities](/assets/images/threat_model-327482aaea9453e954aac2e0a9e3e9e8.svg)

To help you understand who can typically access user data in conventional GenAI API services, we provide an overview of the usual parties involved in the supply chain and explain why they often have access to your data.

In most GenAI API services, the following four relevant entities are involved and have direct or indirect access to certain types of sensitive data:

* **The infrastructure provider**: Provides the compute infrastructure to run the model and inference code, such as AWS or CoreWeave.
* **The platform provider**: Supplies the software environment that runs the AI model, such as Hugging Face.
* **The model provider**: Develops and/or supplies the actual AI model, such as Mistral or Anthropic.
* **The service provider**: Integrates all components and offers the SaaS to the end user.

In many scenarios, one organization may have different roles at the same time. The following table gives three examples.

| API | Service provider | Platform provider | Model provider | Infrastructure provider |
| --- | --- | --- | --- | --- |
| [OpenAI GPT](https://platform.openai.com/docs/guides/text-generation) | OpenAI | OpenAI | OpenAI | Microsoft Azure |
| [HuggingFace](https://endpoints.huggingface.co/) | HuggingFace | HuggingFace | Cohere, Mistral, and others | AWS, GCP, and others |
| [Privatemode](https://privatemode.ai) | Edgeless Systems | [vLLM](https://github.com/vllm-project/vllm) | Meta | Scaleway |

In the case of the well-known OpenAI GPT API, OpenAI is the service provider, the platform provider, and the model provider, while Microsoft Azure provides the infrastructure.

HuggingFace offers an inference API, which allows the user to choose between AI models. The company HuggingFace acts both as the service provider and the platform provider.

The Privatemode API is provided by us (Edgeless Systems). The service runs on Scaleway and uses the open-source framework vLLM to serve a Meta AI model.

### Common privacy threats of conventional GenAI APIs[​](#common-privacy-threats-of-conventional-genai-apis "Direct link to Common privacy threats of conventional GenAI APIs")

Let's examine how these entities can access relevant data within widespread GenAI services like the OpenAI API and the HuggingFace API.

The *infrastructure provider* is highly privileged and controls hardware components and system software like the hypervisor. With this control, the infrastructure provider can typically access all data that's being processed. In the case of a GenAI API service, this includes the user data and the AI model.

On top of the infrastructure runs the software provided by the *platform provider*. This software has access to both the AI model and the user data. The software may leak data through implementation mistakes, logging interfaces, remote-access capabilities, or even backdoors.

The *service provider* typically has privileged access to the platform software and the software (e.g., a web frontend) that receives user data. Correspondingly, the service provider can access both the AI model and the user data. In particular, the service provider may decide to re-train or fine-tune the AI model using the user data. This is oftentimes a concern among users, as it may leak data to other users through the AI model's answer. For example, such a case [has been reported for ChatGPT](https://www.bloomberg.com/news/articles/2023-05-02/samsung-bans-chatgpt-and-other-generative-ai-use-by-staff-after-leak).

In the simplest case, the *model provider* only provides the raw weights (i.e., numbers) that make up the AI model. In this case, the model provider can't, directly or indirectly, access user data. However, in cases where the model provider provides additional software, leaks similar to those discussed for the platform provider may happen for user data.

### How the Privatemode API is different[​](#how-the-privatemode-api-is-different "Direct link to How the Privatemode API is different")

In contrast to other GenAI API services, the Privatemode API thoroughly protects against data access by these four parties when resolving an API call. No one can access your data—not the infrastructure provider, the platform provider, the model provider, or us as the service provider.

* [Security properties](#security-properties)
* [Verifiability](#verifiability)
* [Key benefits](#key-benefits)
  + [Different roles in resolving a GenAI API call](#different-roles-in-resolving-a-genai-api-call)
  + [Common privacy threats of conventional GenAI APIs](#common-privacy-threats-of-conventional-genai-apis)
  + [How the Privatemode API is different](#how-the-privatemode-api-is-different)