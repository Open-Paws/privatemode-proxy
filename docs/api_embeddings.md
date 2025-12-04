# Embeddings API

Version: 1.30

On this page

Use the Privatemode embeddings API to convert text into multidimensional text embeddings. The API is compatible with the [OpenAI Embeddings API](https://platform.openai.com/docs/api-reference/embeddings/create).
To create embeddings, send your requests to the [Privatemode proxy](/guides/proxy-configuration). Embedding requests and responses are encrypted, both in transit and during processing.

## Generating embeddings[​](#generating-embeddings "Direct link to Generating embeddings")

Send a POST request to the following endpoint on your proxy:

```bash
POST /v1/embeddings
```

This endpoint returns vector embeddings for your provided text input.

### Request body[​](#request-body "Direct link to Request body")

* `input` (string or list of strings): The texts for which you want embeddings. The maximum length of the input depends on the model.
* `model` (string): The name of the embedding model, e.g., `qwen3-embedding-4b`.
* `dimensions` (int, optional) The number of dimensions of the output embedding vector. If not specified, the model’s default is used. **Note:** It depends on the embedding model whether a different value than the default is supported.
* `encoding_format` (string, optional): Set to `"float"` for a list of float values or `"base64"` for base64 encoded values.

info

Check [available models](/api/embeddings#available-embedding-models) for the model-specific input requirements

### Returns[​](#returns "Direct link to Returns")

Returns an embeddings response object compatible with [OpenAI's Embeddings API](https://platform.openai.com/docs/api-reference/embeddings/object):

* `data`: List of embedding objects (each with an `embedding` array and `index`).
* `object`: Always `"list"`.
* `model`: The model used.
* `usage`: Token usage statistics.

## Examples[​](#examples "Direct link to Examples")

> Note: To run the examples below, start the Privatemode proxy with a pre-configured API key or add an authentication header to the requests.

* Default
* Batch
* Python

**Example request**

```bash
#!/usr/bin/env bash  
  
curl localhost:8080/v1/embeddings \  
  -H "Content-Type: application/json" \  
  -d '{  
    "input": "The food was delicious and the waiter...",  
    "model": "qwen3-embedding-4b",  
    "encoding_format": "float"  
  }'
```

**Example response**

```bash
{  
  "id": "embd-b0f2e2ede7234a83aa5052128a239d9c",  
  "object": "list",  
  "created": 1747923707,  
  "model": "qwen3-embedding-4b",  
  "data": [  
    {  
      "index": 0,  
      "object": "embedding",  
      "embedding": [  
        0.0351, 0.0375, -0.0050, ... // truncated for brevity  
      ]  
    }  
  ],  
  "usage": {  
    "prompt_tokens": 13,  
    "total_tokens": 13,  
  }  
}
```

**Example request (batch input)**

```bash
#!/usr/bin/env bash  
  
curl localhost:8080/v1/embeddings \  
  -H "Content-Type: application/json" \  
  -d '{  
    "input": [  
      "The food was delicious and the waiter...",  
      "I would definitely come back again!"  
    ],  
    "model": "qwen3-embedding-4b"  
  }'
```

**Example response**

```bash
{  
  "id": "embd-584a54ff36c84996b6ce667339ea3f40",  
  "created": 1747924226,  
  "model": "qwen3-embedding-4b",  
  "object": "list",  
  "data": [  
    {  
      "object": "embedding",  
      "index": 0,  
      "embedding": [ 0.0351, ... ]  // truncated  
    },  
    {  
      "object": "embedding",  
      "index": 1,  
      "embedding": [ 0.0096, ... ]  // truncated  
    }  
  ],  
  "usage": {  
    "prompt_tokens": 22,  
    "total_tokens": 22  
  }  
}
```

**Example usage with OpenAI Python client**

```python
from openai import OpenAI  
  
# Use the OpenAI client to connect to the Privatemode proxy.  
client = OpenAI(  
    api_key="YOUR_API_KEY",  
    base_url="http://localhost:8080/v1",  
)  
  
# Find an embedding model to use.  
models = client.models.list()  
embed_models = [m for m in models.data if "embed" in m.tasks]  
model = embed_models[0].id  
  
# Create embeddings.  
print("Embedding model:", model)  
responses = client.embeddings.create(  
    input=[  
        "Hello my name is",  
        "Edgeless enables confidential and privacy-preserving AI",  
    ],  
    model=model,  
)  
  
[  
    print(f"dim: {len(r.embedding)}, embedding: {r.embedding[:3]}...")  
    for r in responses.data  
]
```

**Output**

```bash
Embedding model: qwen3-embedding-4b  
dim: 1024, embedding: [0.032440185546875, 0.004032135009765625, -0.01043701171875]...  
dim: 1024, embedding: [0.0236663818359375, 0.035919189453125, -0.0012216567993164062]...
```

## Available embedding models[​](#available-embedding-models "Direct link to Available embedding models")

To list the available embedding models, call the [`/v1/models` endpoint](/api/models) or see the [models overview](/models/overview).

* [Generating embeddings](#generating-embeddings)
  + [Request body](#request-body)
  + [Returns](#returns)
* [Examples](#examples)
* [Available embedding models](#available-embedding-models)