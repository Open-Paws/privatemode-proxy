# Visual Studio Code

Version: 1.30

On this page

Privatemode works with AI coding extensions in Visual Studio Code. The officially supported extensions are [GitHub Copilot Chat](https://marketplace.visualstudio.com/items?itemName=GitHub.copilot-chat), [Continue](https://marketplace.visualstudio.com/items?itemName=Continue.continue), and [Cline](https://marketplace.visualstudio.com/items?itemName=saoudrizwan.claude-dev). We recommend using the Privatemode GitHub Copilot extension for AI chat, editing, and agent mode and the Continue extension for tab completions.

## Setting up the Privatemode proxy[​](#setting-up-the-privatemode-proxy "Direct link to Setting up the Privatemode proxy")

Follow the [quickstart guide](/quickstart) to run the Privatemode proxy. Usually, it's advisable to [enable prompt caching](/guides/proxy-configuration#prompt-caching) via `--sharedPromptCache`.

## Configuring GitHub Copilot Chat[​](#configuring-github-copilot-chat "Direct link to Configuring GitHub Copilot Chat")

You can use Privatemode via GitHub Copilot with the [Privatemode VS Code extension](https://marketplace.visualstudio.com/items?itemName=edgeless-systems.privatemode-vscode). It integrates the confidential coding models into GitHub Copilot for Chat.

1. Install the [GitHub Copilot Chat](https://marketplace.visualstudio.com/items?itemName=GitHub.copilot-chat) extension from the VS Code Marketplace.
2. Install the [Privatemode VS Code](https://marketplace.visualstudio.com/items?itemName=edgeless-systems.privatemode-vscode) extension.
3. Choose gpt-oss or Qwen3-Coder as described in the extension.

See the extension’s Marketplace page for details.

warning

GitHub Copilot doesn't allow changing the tab completion model. For privacy‑preserving inline completions, [use the **Continue** extension](#configuring-continue) and disable Copilot tab completions as described in the Privatemode extension.

note

If you’re using a GitHub Copilot Business or Enterprise plan, the Manage Models option may not appear. To enable it, switch temporarily to a Pro or Free plan. This limitation is being addressed by Microsoft.

## Configuring Continue[​](#configuring-continue "Direct link to Configuring Continue")

We recommend using Continue for tab completions using Qwen3-Coder.

1. Install the [Continue](https://marketplace.visualstudio.com/items?itemName=Continue.continue) extension from the VS Code Marketplace.
2. Edit `~/.continue/config.yaml` and add a Privatemode entry under `model`:

   ```bash
   name: Local Assistant  
   version: 1.0.0  
   schema: v1  
   model:  
     - name: Privatemode QwenCoder  
       provider: vllm  
       model: qwen3-coder-30b-a3b  
       apiKey: dummy  
       apiBase: http://localhost:8080/v1  
       defaultCompletionOptions:  
         maxTokens: 20  
       roles:  
         - autocomplete
   ```

![Continue model selector](/assets/images/continue-70590eb0f78a7071ead84199ecba4222.png)

You can now select "Privatemode QwenCoder" as the autocomplete model in the model selector of the extension and use Continue's code completions with the Privatemode AI backend.

Refer to the [Continue documentation](https://docs.continue.dev/reference) for additional configuration options.

note

If you want to use Continue also for editing and chat, create a separate configuration with a different model and increase `maxTokens`, e.g., to `4096`.

## Configuring Cline[​](#configuring-cline "Direct link to Configuring Cline")

1. Install the [Cline](https://marketplace.visualstudio.com/items?itemName=saoudrizwan.claude-dev) extension from the VS Code Marketplace.
2. Open the extension settings and select **Use your own API key**.

   ![Cline VS Code initial screen](/assets/images/cline_select-a5f94259a568a3782be76d89c5cd8561.png)
3. Enter the following details in the UI:

---

* **API Provider**: OpenAI Compatible
* **Base URL: http**://localhost:8080/v1
* **API Key**: null
* **Model ID**: gpt-oss-120b
* **Context Window Size**: 124000

---

![Cline model selector](/assets/images/cline_config-9b68fd1d3ea6d729e378b339f7b27061.png)

More details on Cline’s provider configuration are available in the [Cline docs](https://docs.cline.bot/provider-config/openai-compatible).

* [Setting up the Privatemode proxy](#setting-up-the-privatemode-proxy)
* [Configuring GitHub Copilot Chat](#configuring-github-copilot-chat)
* [Configuring Continue](#configuring-continue)
* [Configuring Cline](#configuring-cline)