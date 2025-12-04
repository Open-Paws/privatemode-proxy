# Release notes

Version: 1.30

On this page

## v1.30.0[​](#v1300 "Direct link to v1.30.0")

* Add tool calling support for [gemma-3-27b](/models/gemma-3-27b).
* Complete overhaul of the [desktop app](/guides/desktop-app)
  + New installer experience
  + Improved user interface and initial setup flow
  + Support for uploading multiple files in a single chat
  + Support for drag-and-drop file upload
  + Support for Linux platforms (rpm, deb)

## v1.29.0[​](#v1290 "Direct link to v1.29.0")

* New model preview [Qwen3-Embedding-4B](/models/qwen3-embedding-4b)
* Support adding extra environment variables in the privatemode-proxy Helm chart, e.g., to [configure an HTTP proxy](/guides/proxy-configuration#http-proxy-configuration).
* Add tool calling support for [gpt-oss-120b](/models/gpt-oss-120b).

## v1.28.0[​](#v1280 "Direct link to v1.28.0")

* Add short names for all models. The model name `latest` is deprecated and will be removed on November 10, 2025. Please ensure the correct use of [explicit model names](/models/overview).
* Upgrade vLLM to [v0.11.0](https://github.com/vllm-project/vllm/releases/tag/v0.11.0) for text generation models.
* Fix an issue where models generate endless whitespace for certain JSON schemas.
* Add an option to provide the [API key from a file](/guides/proxy-configuration#options) or mounted secret.

## v1.27.0[​](#v1270 "Direct link to v1.27.0")

* Enable tool calling for [Qwen3-Coder](/models/qwen3-coder-30b-a3b).
* Upgrade vLLM to [v0.10.2](https://github.com/vllm-project/vllm/releases/tag/v0.10.2) for the gpt-oss model.
* Various improvements to the desktop app.

## v1.26.0[​](#v1260 "Direct link to v1.26.0")

* Upgrade Contrast to [v1.13.0](https://github.com/edgelesssys/contrast/releases/tag/v1.13.0).
* Fix a bug that caused requests to `/v1/chat/completions` and `/v1/completions` with the option `stream: true` to sometimes not terminate correctly.

## v1.25.0[​](#v1250 "Direct link to v1.25.0")

* Upgrade from Qwen2.5-Coder to [Qwen3-Coder 30B-A3B](/models/overview) with 128k context window and improved performance. **Note:** The model ID has changed. The new ID is `qwen3-coder-30b-a3b`.
* Allow model selection in desktop app and increase file upload page limit to about 120 pages.

## v1.24.0[​](#v1240 "Direct link to v1.24.0")

* Enable cache salting in vLLM for [gpt-oss-120b](/models/overview).
* Increase context window for [gemma-3-27b and gpt-oss-120b](/models/overview) to 128k.
* Requests with non-HTTPS `image_url` fields are now rejected.
* Fix file upload in desktop app.
* Upgrade vLLM to [v0.10.1.1](https://github.com/vllm-project/vllm/releases/tag/v0.10.1.1).

## v1.23.0[​](#v1230 "Direct link to v1.23.0")

* New model [gpt-oss-120b](/models/overview) with reasoning.
* Improve the desktop app.
* Endpoints for inference requests now return 404 instead of 403 if the requested model doesn't exist.
* Upgrade Contrast to [v1.12.0](https://github.com/edgelesssys/contrast/releases/tag/v1.12.0).

## v1.22.0[​](#v1220 "Direct link to v1.22.0")

* New model [Qwen2.5-Coder 14B](/models/overview) suitable for [coding assistants](/guides/coding-assistants).
* Upgrade Contrast to [v1.11.0](https://github.com/edgelesssys/contrast/releases/tag/v1.11.0).
* Upgrade vLLM to [v0.10.0](https://github.com/vllm-project/vllm/releases/tag/v0.10.0).

## v1.21.0[​](#v1210 "Direct link to v1.21.0")

* Reject requests with multiple `Content-Type` headers. Please ensure that your requests only contain a single `Content-Type` header.
* Support transcription of audio files up to 25 MB with the [speech-to-text API](/api/speech-to-text). Previously, it was limited to 30 seconds.
* Add [translations API](/api/translations).
* Upgrade Contrast to [v1.10.0](https://github.com/edgelesssys/contrast/releases/tag/v1.10.0).
* Upgrade vLLM to [v0.9.2](https://github.com/vllm-project/vllm/releases/tag/v0.9.2).

## v1.20.0[​](#v1200 "Direct link to v1.20.0")

* Add a new [user portal](https://portal.privatemode.ai) for subscription and key management.
* Rename the app and API key to access key to reflect the new unified pricing. In case you have used the [JSON configuration file](/guides/desktop-app), please rename the field to `access_key`.

## v1.19.0[​](#v1190 "Direct link to v1.19.0")

* Improve Gemma image processing quality.
* Add an "About Privatemode AI" menu option to show the current app version on macOS.
* Fix macOS app version display in the "Get Info" dialog.
* Add documentation for supported models and API endpoints.
* New model [Whisper Large v3](/models/overview) with [speech-to-text API](/api/speech-to-text).

## v1.18.0[​](#v1180 "Direct link to v1.18.0")

* Fix endpoint override options in privatemode-proxy Helm chart.
* New model [Gemma 3 27B](/models/overview) with vision capabilities (supports image inputs in chat completion requests).
* The model name `latest` is deprecated and will be removed in a future release. Please use [explicit model names](/models/overview) instead.
* Upgrade Contrast to [v1.9.0](https://github.com/edgelesssys/contrast/releases/tag/v1.9.0).

## v1.17.0[​](#v1170 "Direct link to v1.17.0")

* File upload support in the desktop app (see [File upload](/guides/desktop-app#file-upload)).
* Added [prompt caching](/guides/proxy-configuration#prompt-caching) support for chat completion requests to reduce latency.
* Upgrade Contrast to [v1.8.1](https://github.com/edgelesssys/contrast/releases/tag/v1.8.1).
* Upgrade vLLM to [v0.9.0](https://github.com/vllm-project/vllm/releases/tag/v0.9.0).
* Added support for embeddings via the `intfloat/multilingual-e5-large-instruct` model with the OpenAI compatible [Embeddings API](/api/embeddings).
* Fixed a bug in the macOS app that caused the error "no secret for ID" if the app was kept open during standby.

## v1.16.0[​](#v1160 "Direct link to v1.16.0")

* Upgrade vLLM to [v0.8.5.post1](https://github.com/vllm-project/vllm/releases/tag/v0.8.5.post1).
* Fixed an issue in v1.13+ of the Privatemode proxy where non-JSON error responses weren't correctly forwarded to the user. Now all errors follow the OpenAI error format.

## v1.15.0[​](#v1150 "Direct link to v1.15.0")

* Upgrade vLLM to [v0.8.4](https://github.com/vllm-project/vllm/releases/tag/v0.8.4).
* Fixed an issue where responses returned a 200 OK code although an error occurred.

## v1.14.0[​](#v1140 "Direct link to v1.14.0")

* Fixed an issue in the macOS application where the configuration directory was inaccessible, which prevented log files from being saved and the optional configuration file from being loaded.
* Fixed an issue where large, non-streaming completions requests weren't processed correctly.

## v1.13.0[​](#v1130 "Direct link to v1.13.0")

warning

Streaming requests aren't working in this version. Please use the latest version.

* Upgrade Contrast to [v1.7.0](https://github.com/edgelesssys/contrast/releases/tag/v1.7.0).
  + As part of this upgrade, the `--coordinatorPolicyHash` flag for `Privatemode proxy` is **removed**. This value is now defined in the manifest.
* Add RunLLM integration to enable chatting with the Privatemode docs. When using this integration your queries are processed by RunLLM.
* Encrypt all JSON fields in chat completion requests and responses. Exceptions are made for metadata fields required for routing and billing.
  Previously, only the `messages` and `tools` fields of requests, and the `choices` field of responses were encrypted.
  Take a look at [the encryption workflow](/architecture/encryption#encryption) for more details.
* Fixed a bug where the privatmode-proxy would drop the `Allow-Origin` header leading to a CORS error when connecting it with a web-based Chat UI.
* Support running Privatemode proxy behind an [HTTP proxy](/guides/proxy-configuration#http-proxy).

## v1.12.0[​](#v1120 "Direct link to v1.12.0")

* Upgrade vLLM to [v0.8.2](https://github.com/vllm-project/vllm/releases/tag/v0.8.2).
* Adapt examples in [Quickstart](https://docs.privatemode.ai/quickstart) guide to use OpenAI SDKs to better promote OpenAI API compatibility.

## v1.11.0[​](#v1110 "Direct link to v1.11.0")

* Fixes a bug in the app where the update banner was always shown.
* Fixes a bug where users who are subscribed to both app and API may be charged twice. This hasn't affected any users.

## v1.10.0[​](#v1100 "Direct link to v1.10.0")

* Load app key from configuration file (see [Desktop app configuration](/guides/desktop-app)).
* Small redesign of the desktop app.
* Add an update banner in the desktop app when a newer version is available.
* Provide users with more detailed error messages if API key validation fails.
* Support for tool calling with an encrypted `tools` parameter (see [Tool calling](/guides/tool-calling)).
* Add [Verification from source code](/guides/verify-source) guide.
* Upgrade vLLM to [v0.7.3](https://github.com/vllm-project/vllm/releases/tag/v0.7.3).

## v1.9.0[​](#v190 "Direct link to v1.9.0")

* Upgrade vLLM to [v0.7.2](https://github.com/vllm-project/vllm/releases/tag/v0.7.2).
* Privatemode's source code is now available at [edgelesssys/privatemode-public](https://github.com/edgelesssys/privatemode-public). The repository contains code for all components that are part of Privatemode's [TCB](https://www.edgeless.systems/wiki/what-is-confidential-computing/threat-model#trusted-computing-base).

## v1.8.0[​](#v180 "Direct link to v1.8.0")

* Privatemode now runs on [Contrast](https://github.com/edgelesssys/contrast). This changes how the Privatemode proxy verifies the deployment. The changes to attestation are described in the documentation.
* Fixed an app issue where prompts sent before initialization would return errors. The app now waits for initialization to complete before responding.
* Fixed incorrect `Content-Type` header in `/v1/models` endpoints, changing from `text/plain` to `application/json` to resolve Web UI compatibility issues.
* Persist app logs (see [Logging](/guides/desktop-app#logging)).
* Add a system prompt with knowledge about Privatemode AI in the app. This allows users to ask basic questions about the security of the service.

## v1.7.0[​](#v170 "Direct link to v1.7.0")

* The deprecated model parameter `hugging-quants/Meta-Llama-3.1-70B-Instruct-AWQ-INT4` was removed. Make sure that you updated the model (see v1.5.0 release note).
* As part of the rename to `Privatemode` the domains used by the Privatemode proxy (previously continuum-proxy) are changed to `api.privatemode.ai`, `secret.privatemode.ai` and `contrast.privatemode.ai`.
* The `privatemode-proxy` flag `--asEndpoint` was renamed to `--ssEndpoint` (secret-service) to reflect the new architecture.
* The `privatemode-proxy` flag `--disableUpdate` was removed (see deprecation notice in v1.5).
* The secret-service (was attestation-service) is now available on port 443 (was 3000).
* Temporarily reduce context window size from 130.000 tokens to 70.000 tokens. This is done to increase capacity during an internal migration.
* The desktop app log directory was updated from `$CFG_DIR/EdgelessSystems/continuum` to `$CFG_DIR/EdgelessSystems/privatemode`. See [transparency log](/guides/desktop-app#transparency-log).
* The desktop app now opens external links from the chat in the browser.

## v1.6.0[​](#v160 "Direct link to v1.6.0")

* The product is renamed to `Privatemode`. Older proxy versions remain compatible with the API.
* The proxy container location has changed to `ghcr.io/edgelesssys/privatemode/privatemode-proxy`. See [proxy configuration](/guides/proxy-configuration).
* The manifest log directory has changed from `continuum-manifests` to `manifests`. See [proxy configuration](/guides/proxy-configuration#cli-flags).

## v1.5.0[​](#v150 "Direct link to v1.5.0")

warning

Please update the model parameter in your request body. The old parameter (`hugging-quants/Meta-Llama-3.1-70B-Instruct-AWQ-INT4`) is outdated and support will be dropped in the next minor release.
If you always want to use the latest model, please use the new model parameter (`latest`). For more information, see [Example Prompting](/api/chat-completions#example-prompting).

* Upgrade to the Llama 3.3 70B model (`ibnzterrell/Meta-Llama-3.3-70B-Instruct-AWQ-INT4` ) for improved quality.
* Upgrade vLLM to [v0.6.6](https://github.com/vllm-project/vllm/releases/tag/v0.6.6.post1).
* `disableUpdate` flag is deprecated. Providing a manifest file via `--manifestPath` will automatically disable the update behavior. Refer to [Manifest management](/guides/proxy-configuration#manifest-management) for more details.

## v1.4.0[​](#v140 "Direct link to v1.4.0")

* Major rewrite of the documentation
* Support token-based billing for Stripe
* Fixes a bug to return errors as type `text/event-stream` if requested by the client

## v1.3.1[​](#v131 "Direct link to v1.3.1")

* Improve stability for cases where the AMD Key Distribution Service is unavailable.

## v1.3.0[​](#v130 "Direct link to v1.3.0")

* Internal changes to license management.

## v1.2.2[​](#v122 "Direct link to v1.2.2")

* Fixes a bug for streaming requests that made optional parameters required if `stream_options: {"include_usage": true}` wasn't set

## v1.2.0[​](#v120 "Direct link to v1.2.0")

* Add `arm64` support for the `continuum-proxy`. Find information on how to use it in the [Continuum-proxy](/guides/proxy-configuration#extract-a-static-binary) section.
* Token tracking is now automatically enabled for streaming requests by transparently setting `include_usage` in the `stream_options`.

## v1.1.0[​](#v110 "Direct link to v1.1.0")

* Increase peak performance by more than 40% through improved request scheduling
* Increase performance by about 6% through vLLM upgrade to `v0.6.1`

* [v1.30.0](#v1300)
* [v1.29.0](#v1290)
* [v1.28.0](#v1280)
* [v1.27.0](#v1270)
* [v1.26.0](#v1260)
* [v1.25.0](#v1250)
* [v1.24.0](#v1240)
* [v1.23.0](#v1230)
* [v1.22.0](#v1220)
* [v1.21.0](#v1210)
* [v1.20.0](#v1200)
* [v1.19.0](#v1190)
* [v1.18.0](#v1180)
* [v1.17.0](#v1170)
* [v1.16.0](#v1160)
* [v1.15.0](#v1150)
* [v1.14.0](#v1140)
* [v1.13.0](#v1130)
* [v1.12.0](#v1120)
* [v1.11.0](#v1110)
* [v1.10.0](#v1100)
* [v1.9.0](#v190)
* [v1.8.0](#v180)
* [v1.7.0](#v170)
* [v1.6.0](#v160)
* [v1.5.0](#v150)
* [v1.4.0](#v140)
* [v1.3.1](#v131)
* [v1.3.0](#v130)
* [v1.2.2](#v122)
* [v1.2.0](#v120)
* [v1.1.0](#v110)