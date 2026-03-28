# Tool calling

Version: 1.30

On this page

With tool calling (also known as function calling), Privatemode enables LLMs to seamlessly **integrate with your data and execute actions while ensuring confidentiality**. By defining custom functions that the LLM can invoke as needed, you can automate complex workflows securely. Function execution occurs within your controlled environment, such that your sensitive data remains protected, ensuring privacy without compromising functionality.

The diagram below illustrates the information flow and function execution in tool calling.

Privatemode supports tool calling if the selected model allows it (e.g., gpt-oss-120b). You can find all models that support tool
calling in the section [Available models](/models/overview).
Tool calling follows the [vLLM Tool Calling specification](https://docs.vllm.ai/en/latest/features/tool_calling.html), with the key distinction that **function definitions, invocations, and results are encrypted to protect your data**.

## Encryption[​](#encryption "Direct link to Encryption")

Tool call definitions and responses are encrypted by encrypting the relevant fields in requests and responses:

* **Function definitions** are encrypted in the `tools` request field (see below), similar to the `messages` sent to the model.
* **Function calls** suggested by the LLM are returned in the `choices` response field and are thus encrypted.
* **Function call results** are returned to the model as separate messages and are thus encrypted too.

This ensures that your function definitions, function arguments, and returned results are kept confidential.

## Request parameters[​](#request-parameters "Direct link to Request parameters")

Privatemode supports the vLLM API and thus most parameters from the OpenAI API specification, such that code can be migrated.
The following list details support for the relevant request parameters:

* **`tools`**
  Used to specify which functions are available. It's an array of tool (function) definitions.
* **`tool_choice`**
  Used by the model to decide when to call tools. The supported options are `auto` (default) and `none`. If omitted, it defaults to `auto`.

  + **`auto`**: The model will call tools if it deems them necessary.
  + **`none`**: The model won't call any tools (all tool calls disabled).

  The option `required` is currently not supported but will become available once vLLM supports it.
* **`parallel_tool_calls`**
  Allow the model to make multiple tool calls in a single response. Not supported by all models.
* **`functions` and `function_call`**
  Deprecated in the OpenAI API and not supported by Privatemode; use `tools` and `tool_choice` instead.

> Depending on the used model, you may have to force the model to not call any tools when returning the function result, by explicitly setting `"tool_choice": "none"` or providing no tools at all (e.g., `"tools": null` or `"tools": []`).

### Example request[​](#example-request "Direct link to Example request")

```bash
#!/usr/bin/env bash  
  
curl localhost:8080/v1/chat/completions \  
  -H "Content-Type: application/json" \  
  -d '{  
    "model": "gpt-oss-120b",  
    "messages": [{ "role": "user", "content": "What is the weather in Berlin?" }],  
    "tools" : [{  
        "type": "function",  
        "function": {  
            "name": "get_weather",  
            "description": "Get the current weather in a given location",  
            "parameters": {  
                "type": "object",  
                "properties": {  
                    "location": {"type": "string", "description": "City and country, e.g., Berlin, Germany"},  
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}  
                },  
                "required": ["location", "unit"]  
            }  
        }  
    }],  
    "tool_choice": "auto"  
  }'
```

## Response parameters[​](#response-parameters "Direct link to Response parameters")

The model returns a response `message` with tool calls.

```bash
{  
    "role": "assistant",  
    "tool_calls": [{  
        "id": "call_12345xyz",  
        "type": "function",  
        "function": {  
            "name": "get_weather",  
            "arguments": "{\"location\":\"Berlin, Germany\",\"unit\":\"celsius\"}"  
        }  
    }]  
}
```

Here `tool_call_id` is used by the model to relate a tool call result to its request.

In subsequent requests, the client must provide both, function call and the result, in separate messages in the message history:

```bash
"messages": [  
    ... (message history)  
    {  
        "role": "assistant",  
        "tool_calls": [{  
            "id": "call_12345xyz",  
            "type": "function",  
            "function": {  
                "name": "get_weather",  
                "arguments": "{\"location\":\"Berlin, Germany\",\"unit\":\"celsius\"}"  
            }  
        }]  
    },  
    {  
        "role": "tool",  
        "tool_call_id": "call_12345xyz",  
        "content": "{\"location\": \"Berlin\",\"temperature\": \"21°C\",\"condition\": \"sunny\"}"  
    }  
]
```

> **Note**: For Llama 3.3, tool calling should be disabled when sending the result request, as the model may try to call the function
> again otherwise.

## Full example (Python)[​](#full-example-python "Direct link to Full example (Python)")

This Python example illustrates tool calling in Privatemode, allowing the model to fetch the current weather via a function call.

```python
import os  
import json  
from openai import OpenAI  
  
  
# Define the tool (function) that the model can call  
def get_weather(location: str, unit: str):  
    """  
    Returns a weather report for the given location.  
    """  
    return {"location": location, "temperature": "21°C", "condition": "sunny"}  
  
  
weather_func = {  
    "type": "function",  
    "function": {  
        "name": "get_weather",  
        "description": "Get the current weather in a given location",  
        "parameters": {  
            "type": "object",  
            "properties": {  
                "location": {  
                    "type": "string",  
                    "description": "City and state, e.g., 'Berlin, Germany'",  
                },  
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},  
            },  
            "required": ["location", "unit"],  
        },  
    },  
}  
  
# Make the request  
client = OpenAI(  
    api_key=os.environ.get("PRIVATE_MODE_API_KEY"), base_url="http://localhost:8080/v1"  
)  
  
messages = [{"role": "user", "content": "What's the weather like in New York?"}]  
response = client.chat.completions.create(  
    model="gpt-oss-120b",  
    messages=messages,  
    tools=[weather_func],  
    # default tool_choice is 'auto' if omitted  
    tool_choice="auto",  
)  
response_message = response.choices[0].message  
  
# Return the tool call in subsequent messages.  
messages.append(response_message)  
  
  
# The model responds with a function call which is executed by the client.  
tool_call = response_message.tool_calls[0]  
fn_name = tool_call.function.name  
fn_args = json.loads(tool_call.function.arguments)  
fn_result = (  
    get_weather(**fn_args) if fn_name == "get_weather" else f"Unknown tool {fn_name}!"  
)  
  
# Return the result to the model  
messages.append(  
    {"role": "tool", "tool_call_id": tool_call.id, "content": str(fn_result)}  
)  
  
# To avoid another tool call by the model in the next response, you may have to  
# disable tool calling by setting 'tool_choice' to "none" or removing 'tools'.  
response = client.chat.completions.create(  
    model="gpt-oss-120b",  
    messages=messages,  
    tools=None,  
)  
  
response_message = response.choices[0].message  
print(response_message.content)  
  
# Example output: "The weather in New York is 21°C and sunny."
```

* [Encryption](#encryption)
* [Request parameters](#request-parameters)
  + [Example request](#example-request)
* [Response parameters](#response-parameters)
* [Full example (Python)](#full-example-python)