# Gemma 3 27B

Version: 1.30

On this page

Gemma is a family of lightweight, state-of-the-art open models from Google.
[Gemma 3 models](https://huggingface.co/blog/gemma3) are multimodal, handling text and image input and generating text output.
Privatemode provides a variant of this model that uses quantization from [LLM Compressor](https://github.com/vllm-project/llm-compressor) to reduce the model size from FP16 to FP8.

## Model ID[​](#model-id "Direct link to Model ID")

`gemma-3-27b`

## Source[​](#source "Direct link to Source")

[Hugging Face](https://huggingface.co/leon-se/gemma-3-27b-it-FP8-Dynamic)

## Modality[​](#modality "Direct link to Modality")

* Input: text, image
* Output: text

## Features[​](#features "Direct link to Features")

* [Streaming](https://platform.openai.com/docs/api-reference/chat/streaming)
* [Tool calling](/guides/tool-calling) (see [remarks](#remarks-and-limitations) below)
* [Structured outputs](https://platform.openai.com/docs/guides/structured-outputs?api-mode=chat)

## Context limit[​](#context-limit "Direct link to Context limit")

* Context window: 128k tokens

## Endpoints[​](#endpoints "Direct link to Endpoints")

* [`/v1/chat/completions`](/api/chat-completions)

## Example[​](#example "Direct link to Example")

* Image input

```python
from openai import OpenAI  
import base64  
import os  
  
# docker run --pull=always -p 8080:8080 ghcr.io/edgelesssys/privatemode/privatemode-proxy:latest  
# PRIVATEMODE_API_KEY=<> uv run --with openai gemma-vision.py  
  
api_key = os.environ.get("PRIVATEMODE_API_KEY") # insert  
api_base = "http://localhost:8080/v1"  
image_path = (  
    "" # insert  
)  
  
client = OpenAI(  
    api_key=api_key,  
    base_url=api_base,  
)  
  
def encode_image_to_base64(image_path):  
    with open(image_path, "rb") as image_file:  
        return base64.b64encode(image_file.read()).decode("utf-8")  
  
  
  
if not os.path.exists(image_path):  
    print(f"Error: Image file not found at {image_path}")  
    exit(1)  
  
base64_image = encode_image_to_base64(image_path)  
  
chat_response = client.chat.completions.create(  
    model="gemma-3-27b",  
    messages=  
        {  
            "role": "user",  
            "content": [  
                {"type": "text", "text": "What's in this image?"},  
                {  
                    "type": "image_url",  
                    "image_url": {"url": f"data:image/png;base64,{base64_image}"},  
                },  
            ],  
        }  
    ],  
)  
  
print("Chat completion output:", chat_response.choices[0].message.content)
```

## Remarks and limitations[​](#remarks-and-limitations "Direct link to Remarks and limitations")

* Gemma requires alternating `user`/`assistant` roles, so you can't use multiple user messages without assistant messages between them. For tool calling, the `user` role can use the `tool` role instead, i.e., `user` -> `assistant` (tool call) -> `tool` (result) -> `assistant`.
* Gemma doesn't support mixed text and tool call outputs. Make sure you don't ask it to generate both in the same response, but separate requests for tool use and text responses.

* [Model ID](#model-id)
* [Source](#source)
* [Modality](#modality)
* [Features](#features)
* [Context limit](#context-limit)
* [Endpoints](#endpoints)
* [Example](#example)
* [Remarks and limitations](#remarks-and-limitations)