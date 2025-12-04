# Desktop app

Version: 1.30

On this page

The Privatemode desktop app is a demo application that makes it easy to chat with different models using the Privatemode API.
It bundles the [Privatemode proxy](/guides/proxy-configuration) with a visual chat interface to provide a
ChatGPT-like user experience.

![The Privatemode Desktop app interface](/assets/images/desktop-app-mac-a786fecfb918f1463da63efd7acc6e3f.png)

The app prioritizes your privacy and data security:

* Uses only the official Privatemode API for all AI interactions
* Stores chat history and access key locally on your device
* Sends no data to third-party services

## Getting started[​](#getting-started "Direct link to Getting started")

Ensure the following requirements are met:

* **Operating systems**:
  + Windows (x64)
  + MacOS (Apple Silicon)
  + Linux (x64; rpm, deb; experimental)
* **Privatemode access key**: Required for authentication
* **Active internet connection**: Required for API communication

1. [Download the desktop app](https://www.privatemode.ai/download-app) for your platform
2. Install and run it
3. Enter your access key
4. Start chatting

## Updates[​](#updates "Direct link to Updates")

Privatemode is constantly being improved. This affects the API (e.g., model updates) as well as the app.
To take advantage of all the latest features, it's recommended to always use the latest app version.
If a new version is available for you to download,

## File upload[​](#file-upload "Direct link to File upload")

Depending on the selected model, the app allows you to upload files and refer to it in your prompts.
You can attach files using the "Attach" button, or by drag-and-dropping the files into the chat input.

Common file types are supported:

* PDF
* Microsoft Office document types such as PowerPoint presentations or Excel sheets
* Many more

## Logging[​](#logging "Direct link to Logging")

The app stores logs in the user configuration directory:

* on Windows: `%AppData%/EdgelessSystems/privatemode`
* on Mac: `$HOME/Library/Application Support/EdgelessSystems/privatemode`

When sending a support ticket to [support@privatemode.ai](mailto:support@privatemode.ai), you may attach
the `log.txt` file to help understand the issue.

### Transparency log[​](#transparency-log "Direct link to Transparency log")

Like the [Privatemode proxy](/guides/proxy-configuration#automatically), the desktop app maintains a manifest
log for transparency and auditability. Your system's default user configuration directory contains this log file:

* on Windows: `%AppData%/EdgelessSystems/privatemode`
* on Mac: `$HOME/Library/Application Support/EdgelessSystems/privatemode`

### Limitations[​](#limitations "Direct link to Limitations")

* No support for images. Only text undergoes processing. This means photos of text pages in a PDF aren't supported.
* A chat may not exceed 70,000 words. This includes uploaded files, where it corresponds to about 120 A4 pages
  with single-spaced text and 12pt font size.

* [Getting started](#getting-started)
* [Updates](#updates)
* [File upload](#file-upload)
* [Logging](#logging)
  + [Transparency log](#transparency-log)
  + [Limitations](#limitations)