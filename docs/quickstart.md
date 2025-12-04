# Quickstart

Version: 1.30

On this page

The Privatemode API provides a GenAI inference service designed with end-to-end encryption and privacy preservation at its core. Setting it up is a breeze. It shouldn't take more than 10 minutes of your time.

## 1. Install Docker[​](#1-install-docker "Direct link to 1. Install Docker")

Follow the [instructions to install Docker](https://docs.docker.com/engine/install/).

tip

On Windows, the easiest way is to run the proxy inside the Windows Subsystem for Linux (WSL) with the networking mode set to *mirrored*. Open "WSL Settings" and go to "Networking" to set the networking mode.

## 2. Run the proxy[​](#2-run-the-proxy "Direct link to 2. Run the proxy")

The Privatemode API comes with its own proxy. The Privatemode proxy takes care of client-side encryption and verifies the integrity and identity of the entire service using [remote attestation](https://www.edgeless.systems/wiki/what-is-confidential-computing/remote-attestation). Use the following command to run the proxy:

```bash
docker run -p 8080:8080 ghcr.io/edgelesssys/privatemode/privatemode-proxy:latest --apiKey <your-api-key>
```

tip

Instead of using Docker, you may [run the native binary on Linux](/guides/proxy-configuration#extract-a-static-binary).

This opens an endpoint on your host on port 8080.
This guide assumes that you run and use the proxy on your local machine.
Alternatively, you can run it on another machine and [configure TLS encryption](/guides/proxy-configuration#setting-up-tls).

## 3. Send prompts[​](#3-send-prompts "Direct link to 3. Send prompts")

Now you're all set to use the API. The proxy handles all the security (and confidential computing) intricacies for you. Start by sending your first prompt:

* Bash
* Python
* JavaScript

**Example request**

```bash
#!/usr/bin/env bash  
  
curl localhost:8080/v1/chat/completions \  
  -H "Content-Type: application/json" \  
  -d '{  
    "model": "gpt-oss-120b",  
    "messages": [  
      {  
        "role": "user",  
        "content": "Hello Privatemode!"  
      }  
    ]  
  }'
```

**Example response**

```bash
{  
    "id": "chat-c87bdd75d1394dcc886556de3db5d0c9",  
    "object": "chat.completion",  
    "created": 1727429032,  
    "model": "gpt-oss-120b",  
    "choices": [  
        {  
            "index": 0,  
            "message": {  
                "role": "assistant",  
                "content": "Hello. I'm here to help you in any way I can.",  
                "tool_calls": []  
            },  
            "logprobs": null,  
            "finish_reason": "stop",  
            "stop_reason": null  
        }  
    ],  
    "usage": {  
        "prompt_tokens": 34,  
        "total_tokens": 49,  
        "completion_tokens": 15  
    },  
    "prompt_logprobs": null  
}
```

**Example request**

```python
import openai  
  
client = openai.OpenAI(  
    api_key="placeholder",  # Already set in the proxy, but needs to be non-empty here  
    base_url="http://localhost:8080/v1",  # Adjust as necessary  
)  
  
response = client.chat.completions.create(  
    model="gpt-oss-120b",  
    messages=[  
        {"role": "user", "content": "Hello Privatemode!"},  
    ],  
)  
  
print(response.choices[0].message.content)
```

**Example response**

```bash
It's nice to meet you. Is there something I can help you with or would you like to chat?
```

**Example request**

```bash
import OpenAI from 'openai';  
  
const client = new OpenAI({  
  apiKey: 'placeholder', // Already set in the proxy, but needs to be non-empty here  
  baseURL: 'http://localhost:8080/v1', // Adjust as necessary  
});  
  
const response = await client.chat.completions.create({  
  model: 'gpt-oss-120b',  
  messages: [{ role: 'user', content: 'Hello Privatemode!' }],  
});  
  
console.log(response.choices[0].message.content);
```

**Example response**

```bash
It's nice to meet you. Is there something I can help you with or would you like to chat?
```

The code performs the following steps:

1. Construct a prompt request following the [OpenAI Chat API](https://platform.openai.com/docs/api-reference/chat) specification.
2. Send the prompt request to the Privatemode proxy. The proxy handles end-to-end encryption and verifies the integrity of the Privatemode backend that serves the endpoint.
3. Receive and print the response.

info

Privatemode doesn't use any OpenAI services. It only adheres to the same interface definitions to provide a great development experience and ensure easy code portability.

* [1. Install Docker](#1-install-docker)
* [2. Run the proxy](#2-run-the-proxy)
* [3. Send prompts](#3-send-prompts)