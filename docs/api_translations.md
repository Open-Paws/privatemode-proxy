# Translations API

Version: 1.30

On this page

Use the Privatemode translations API to translate audio files to English text.
The API is compatible with the [OpenAI translations API](https://platform.openai.com/docs/api-reference/audio/createTranslation).
To translate audio, send your requests to the [Privatemode proxy](/guides/proxy-configuration). Audio requests and responses are encrypted, both in transit and during processing.

## Generating translations[​](#generating-translations "Direct link to Generating translations")

Send a POST form request to the following endpoint on your proxy:

```bash
POST /v1/audio/translations
```

This endpoint generates an English translation of the provided audio file.

### Request body[​](#request-body "Direct link to Request body")

* `model` (string): The name of the model to use for translation, e.g., `whisper-large-v3`.
* `file` (file): The audio file to translate. Supported formats are `flac`, `mp3`, `mp4`, `mpeg`, `mpga`, `m4a`, `ogg`, `wav`, and `webm`.
* `language` (string, optional): The language of the audio in [ISO-639-1](https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes) (e.g., `de`) format. Not setting the correct language can lead to poor accuracy and performance.
* `prompt` (string, optional): An optional text to guide the model's style or continue a previous audio segment. The [prompt](https://platform.openai.com/docs/guides/speech-to-text#prompting) should match the audio language.
* For additional parameters see the [vLLM translations API documentation](https://docs.vllm.ai/en/stable/serving/openai_compatible_server.html#translations-api_1).

### Returns[​](#returns "Direct link to Returns")

The translated text.

## Examples[​](#examples "Direct link to Examples")

> Note: To run the examples below, start the Privatemode proxy with a pre-configured API key or add an authentication header to the requests.

**Example request**

```bash
#!/usr/bin/env bash  
  
curl localhost:8080/v1/audio/translations \  
  -H "Content-Type: multipart/form-data" \  
  -F 'model=whisper-large-v3' \  
  -F 'language=de' \  
  -F 'file=@hallo_welt.mp3'
```

**Example response**

```bash
{  
  "text": "Hello World."  
}
```

## Available translation models[​](#available-translation-models "Direct link to Available translation models")

To list the available translation models, call the [`/v1/models` endpoint](/api/models) or see the [models overview](/models/overview).

warning

Privatemode's serving backend only supports files up to 25 MB in size.
For larger files, consider splitting the audio into smaller segments, or try compressing the file to reduce its size.

* [Generating translations](#generating-translations)
  + [Request body](#request-body)
  + [Returns](#returns)
* [Examples](#examples)
* [Available translation models](#available-translation-models)