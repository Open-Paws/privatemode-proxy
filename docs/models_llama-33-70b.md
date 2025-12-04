# Llama 3.3 70B

Version: 1.30

On this page

Deprecated

This model is deprecated and will be removed on **December 14th, 2025**. Please migrate to an alternative model.

The Meta [Llama 3.3 70B Instruct](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct) multilingual model is an instruction tuned generative model in 70B (text in/text out).
Privatemode provides a variant of this model that was quantized using [AutoAWQ](https://github.com/casper-hansen/AutoAWQ) from FP16 down to INT4 using GEMM kernels, with zero-point quantization and a group size of 128.

## Model ID[​](#model-id "Direct link to Model ID")

`llama-3.3-70b`

## Source[​](#source "Direct link to Source")

[Hugging face](https://huggingface.co/ibnzterrell/Meta-Llama-3.3-70B-Instruct-AWQ-INT4)

## Modality[​](#modality "Direct link to Modality")

* Input: text
* Output: text

## Features[​](#features "Direct link to Features")

* [Streaming](https://platform.openai.com/docs/api-reference/chat/streaming)
* [Tool calling](/guides/tool-calling)
* [Structured outputs](https://platform.openai.com/docs/guides/structured-outputs?api-mode=chat)

## Context limit[​](#context-limit "Direct link to Context limit")

* Context window: 70k tokens
* Max output length: [4028](https://llama.developer.meta.com/docs/models#llama-3.3-70b-instruct)

## Endpoints[​](#endpoints "Direct link to Endpoints")

* [`/v1/chat/completions`](/api/chat-completions)
* [`/v1/completions`](/api/legacy-completions)

* [Model ID](#model-id)
* [Source](#source)
* [Modality](#modality)
* [Features](#features)
* [Context limit](#context-limit)
* [Endpoints](#endpoints)