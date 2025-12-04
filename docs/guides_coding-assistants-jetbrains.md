# JetBrains IDEs

Version: 1.30

On this page

Privatemode works with AI coding plugins in JetBrains IDEs (IntelliJ IDEA, PyCharm, CLion, etc.). The officially supported plugin is the JetBrains AI Assistant.

## Setting up the Privatemode proxy[​](#setting-up-the-privatemode-proxy "Direct link to Setting up the Privatemode proxy")

Follow the [quickstart guide](/quickstart) to run the Privatemode proxy. Usually, it's advisable to enable prompt caching via `--sharedPromptCache`.

## Installing the AI assistant plugin[​](#installing-the-ai-assistant-plugin "Direct link to Installing the AI assistant plugin")

1. Open **Settings → Plugins → Marketplace**.
2. Search for **AI Assistant** and select **Install**.

![Install JetBrains AI Assistant plugin](/assets/images/jetbrains_install_ai_assistant-b0e5b0f9ab75e6122d33bbd99ec291c3.png)

## Configuring the AI assistant plugin[​](#configuring-the-ai-assistant-plugin "Direct link to Configuring the AI assistant plugin")

1. Open **Settings → Tools → AI Assistant → Models**.
2. Under **Provider**, select **OpenAI API**.
3. Set **URL** to your Privatemode proxy, e.g., `http://localhost:8080/v1`.
4. Click **Test Connection**. This will fetch the available models from Privatemode.

![Configure JetBrains AI Assistant plugin](/assets/images/jetbrains_configure_ai_assistant-21be1045527cc4330704e861c96d5ea1.png)

### Model selection[​](#model-selection "Direct link to Model selection")

* **Core features**: gpt-oss and Qwen‑Coder often provide the best performance.
* **Instant helpers** and **Completion model**: Qwen-Coder often provides the best performance.

### Optional: Offline mode[​](#optional-offline-mode "Direct link to Optional: Offline mode")

Enable **Offline mode** to prevent data from being sent to external services other than Privatemode.

* [Setting up the Privatemode proxy](#setting-up-the-privatemode-proxy)
* [Installing the AI assistant plugin](#installing-the-ai-assistant-plugin)
* [Configuring the AI assistant plugin](#configuring-the-ai-assistant-plugin)
  + [Model selection](#model-selection)
  + [Optional: Offline mode](#optional-offline-mode)