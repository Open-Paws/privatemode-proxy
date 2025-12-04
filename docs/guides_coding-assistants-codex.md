# OpenAI Codex

Version: 1.30

On this page

Privatemode can serve as model provider in OpenAI's agentic AI coding tool [Codex](https://developers.openai.com/codex). Simply follow the steps below.

## Setting up the Privatemode proxy[​](#setting-up-the-privatemode-proxy "Direct link to Setting up the Privatemode proxy")

Follow the [quickstart guide](/quickstart) to run the Privatemode proxy. Usually, it's advisable to enable prompt caching via `--sharedPromptCache`.

## Configuring Codex[​](#configuring-codex "Direct link to Configuring Codex")

After installation, you can find Codex' configuration file at `~/.codex/config.toml`. Add the following to your configuration file, to define a profile for Privatemode:

```bash
[model_providers.privatemode]  
name = "Privatemode"  
base_url = "http://localhost:8080/v1"  
  
[profiles.privatemode]  
model_provider = "privatemode"  
model = "gpt-oss-120b"
```

See the official [Codex docs](https://developers.openai.com/codex/local-config/) for details on available
configuration options.

## Starting Codex with Privatemode[​](#starting-codex-with-privatemode "Direct link to Starting Codex with Privatemode")

Once you've added the profile for Privatemode to the configuration file, you can start Codex as follows:

```bash
codex --profile privatemode
```

You will be greeted with a screen like the following. You are now ready to "vibe code" confidentially 🥳

![Screenshot of Codex + Privatemode](/assets/images/codex_privatemode-86c56558c92ff30677b45322a77c9ec6.jpg)

* [Setting up the Privatemode proxy](#setting-up-the-privatemode-proxy)
* [Configuring Codex](#configuring-codex)
* [Starting Codex with Privatemode](#starting-codex-with-privatemode)