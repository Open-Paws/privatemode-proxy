# Models API

Version: 1.30

On this page

Use the Privatemode model API to get a list of currently available models. The API is compatible with the [OpenAI list models API](https://platform.openai.com/docs/api-reference/models/list).
To list models, send your requests to the [Privatemode proxy](/guides/proxy-configuration).

## List models[​](#list-models "Direct link to List models")

You can get a list of all available models using the `models` endpoint.

```bash
GET /v1/models
```

This endpoint lists all currently available models.

### Returns[​](#returns "Direct link to Returns")

The response is a list of [model objects](https://platform.openai.com/docs/api-reference/models/object).

**Example request**

```bash
#!/usr/bin/env bash  
  
curl localhost:8080/v1/models
```

**Example response**

```bash
{  
  "object": "list",  
  "data": [  
    {  
      "id": "gpt-oss-120b",  
      "object": "model",  
      "tasks": [  
        "generate",  
        "tool_calling"  
      ]  
    },  
    {  
      "id": "gemma-3-27b",  
      "object": "model",  
      "tasks": [  
        "generate",  
        "tool_calling",  
        "vision"  
      ]  
    },  
    {  
      "id": "qwen3-embedding-4b",  
      "object": "model",  
      "tasks": [  
        "embed"  
      ]  
    }  
  ]  
}
```

note

Starting with **v1.28.0**, shortened model IDs (without prefixes and suffixes) were introduced.
For backward compatibility, the original full model IDs are still supported for now.

As a result, the `/models` endpoint may return **both the shortened and full model IDs** for older models.
This duplication doesn't affect the behavior of any other endpoints.

### Supported model tasks[​](#supported-model-tasks "Direct link to Supported model tasks")

Response field `tasks` provides a lists of all tasks a model supports:

* `embed`: Create vector representations (embeddings) of input text.
* `generate`: Generate text completions or chat responses from prompts.
* `tool_calling`: Invoke function calls or tools (such as retrieval-augmented generation or plugins).

> Note that `tasks` isn't part of the OpenAI API spec.

* [List models](#list-models)
  + [Returns](#returns)
  + [Supported model tasks](#supported-model-tasks)