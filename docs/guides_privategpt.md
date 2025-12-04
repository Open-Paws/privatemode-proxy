# Privatemode as a secure backend for PrivateGPT

Version: 1.30

On this page

[PrivateGPT](https://privategpt.dev/) is an easy to use framework for securely running context-aware AI applications locally.
Combined with Privatemode, you can offload computationally intensive inference operations onto our servers, while ensuring that all your data stays private at all times.

Since Privatemode serves an OpenAI compatible API, it can interface with PrivateGPT running in [`openailike` mode](https://docs.privategpt.dev/manual/advanced-setup/llm-backends#using-openai-compatible-api).

## Set-up guide[​](#set-up-guide "Direct link to Set-up guide")

First, start your [Privatemode proxy](/guides/proxy-configuration):

```bash
docker run -p 8000:8000 ghcr.io/edgelesssys/privatemode/privatemode-proxy:latest --apiKey <your_api_key> --port 8000
```

Next, follow the [PrivateGPT installation instructions](https://docs.privategpt.dev/installation/getting-started/installation) to install the required dependencies.
Run the following command in the checked out PrivateGPT repository to install the dependencies required for the default configuration of the `openailike` mode:

```bash
poetry install --extras "ui embeddings-huggingface llms-openai-like vector-stores-qdrant"
```

Update the configuration to use one of the [available models](/models/overview) for inference in `settings-vllm.yaml`:

```bash
openai:  
    model: gpt-oss-120b
```

You can now run PrivateGPT using the `settings-vllm.yam` profile:

```bash
PGPT_PROFILES=vllm make run
```

Go to <http://localhost:8001/> to access the deployment through the Gradio UI.

* [Set-up guide](#set-up-guide)