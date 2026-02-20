# Sample MCP Server on Azure Functions (Python)

A sample [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server built with Python and hosted on [Azure Functions Flex Consumption](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-plan). It demonstrates how to expose tools to AI clients such as VS Code Copilot and Azure AI Foundry agents using the **Streamable HTTP transport**.

---

## Contents

- [Architecture](#architecture)
- [Tools](#tools)
- [Streamable HTTP — Key Implementation Notes](#streamable-http--key-implementation-notes)
- [Prerequisites](#prerequisites)
- [Local Development](#local-development)
- [Deploy to Azure](#deploy-to-azure)
- [Testing](#testing)
- [Connect to VS Code Copilot](#connect-to-vs-code-copilot)
- [Connect to Azure AI Foundry](#connect-to-azure-ai-foundry)

---

## Architecture

```
MCP Client (VS Code Copilot / Foundry Agent)
        │
        │  POST /runtime/webhooks/mcp
        │  Headers: x-functions-key, Accept: application/json, text/event-stream
        │
        ▼
Azure Functions (Flex Consumption, Python 3.12)
   ├── mcpToolTrigger → hello_mcp
   ├── mcpToolTrigger → get_weather
   ├── mcpToolTrigger → search_products
   └── mcpToolTrigger → get_order_status
```

**Infrastructure:** Flex Consumption plan (FC1) · Python 3.12 · UserAssigned Managed Identity · keyless Storage (blob + queue) · Log Analytics + App Insights

---

## Tools

| Tool | Description | Arguments |
|---|---|---|
| `hello_mcp` | Connectivity check — returns a greeting | none |
| `get_weather` | Mock weather for a city | `city` (string) |
| `search_products` | Search a mock product catalog | `query` (string), `max_results` (string, optional) |
| `get_order_status` | Mock order tracking by order ID | `order_id` (string) |

**Mock data coverage:**
- `get_weather`: London, Tokyo, New York, Sydney, Berlin, Seattle, Paris, Dubai
- `get_order_status`: ORD-1001 (Delivered) → ORD-1005 (Cancelled)

---

## Streamable HTTP — Key Implementation Notes

This sample uses the **Streamable HTTP transport**, which is the current standard for MCP over HTTP. The older SSE transport (`/runtime/webhooks/mcp/sse`) is deprecated and should not be used in new projects.

### What makes this Streamable HTTP

| Setting | Value | Location |
|---|---|---|
| Endpoint path | `/runtime/webhooks/mcp` | Built into the MCP extension |
| Extension bundle | `[4.0.0, 5.0.0)` | `src/host.json` |
| Python SDK version | `azure-functions >= 1.24.0` | `src/requirements.txt` |
| Required request header | `Accept: application/json, text/event-stream` | All MCP client requests |

> **Important:** If the `Accept` header is missing, the server returns `-32000 Not Acceptable`. Every MCP client request must include `Accept: application/json, text/event-stream`.

### Trigger type

Each tool is registered using the `mcpToolTrigger` generic trigger:

```python
@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_weather",
    description="Returns current weather conditions for a given city.",
    toolProperties=_WEATHER_PROPS,   # JSON array of {propertyName, propertyType, description}
)
def get_weather(context) -> str:
    ...
```

### Argument parsing

When called by an MCP client, the `context` parameter is a JSON string shaped as:

```json
{
    "arguments": {
        "city": "Tokyo"
    }
}
```

Arguments are **always nested under `"arguments"`**. Parse them with:

```python
content = json.loads(context)
args = content.get("arguments", content)   # fallback allows flat direct test calls
city = args.get("city", "")
```

### host.json MCP metadata

```json
"extensions": {
    "mcp": {
        "serverName": "sample-mcp-python",
        "serverVersion": "1.0.0",
        "instructions": "Use these tools to look up weather, search products, and check order status."
    }
}
```

---

## Prerequisites

- [Python 3.12](https://www.python.org/downloads/)
- [Azure Functions Core Tools v4](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local)
- [Azure Developer CLI (azd)](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd)
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
- An Azure subscription

---

## Local Development

```bash
cd src
pip install -r requirements.txt
func host start
```

The local MCP endpoint will be available at:
```
http://localhost:7071/runtime/webhooks/mcp
```

No `x-functions-key` header is required locally (the MCP extension key is only enforced in Azure).

---

## Deploy to Azure

### 1. Login

```bash
azd auth login
```

### 2. Deploy (provisions infrastructure + deploys code)

```bash
azd up
```

You will be prompted for:
- Environment name (e.g. `sample-mcp-python`)
- Azure subscription
- Azure region (recommend `eastus` or `eastus2` for best quota availability)

### 3. Retrieve the MCP extension key

After deployment, retrieve your `mcp_extension` system key:

```bash
# Get function app name from azd environment
$funcAppName = (azd env get-values | Select-String "SERVICE_API_NAME").ToString().Split("=")[1].Trim('"')

az functionapp keys list `
    --name $funcAppName `
    --resource-group (azd env get-value AZURE_RESOURCE_GROUP) `
    --query "systemKeys.mcp_extension" -o tsv
```

---

## Testing

Use PowerShell to test the deployed server directly.

```powershell
$base = "https://<your-function-app>.azurewebsites.net/runtime/webhooks/mcp"
$h = @{
    "x-functions-key" = "<your-mcp_extension-key>"
    "Content-Type"    = "application/json"
    "Accept"          = "application/json, text/event-stream"
}

# 1. List available tools
Invoke-RestMethod -Uri $base -Method POST -Headers $h `
    -Body '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | ConvertTo-Json -Depth 10

# 2. Call hello_mcp
Invoke-RestMethod -Uri $base -Method POST -Headers $h `
    -Body '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"hello_mcp","arguments":{}}}' | ConvertTo-Json -Depth 10

# 3. Get weather for Tokyo
Invoke-RestMethod -Uri $base -Method POST -Headers $h `
    -Body '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_weather","arguments":{"city":"Tokyo"}}}' | ConvertTo-Json -Depth 10

# 4. Check order status
Invoke-RestMethod -Uri $base -Method POST -Headers $h `
    -Body '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_order_status","arguments":{"order_id":"ORD-1002"}}}' | ConvertTo-Json -Depth 10
```

> **Common error:** `-32000 Not Acceptable` means the `Accept: application/json, text/event-stream` header is missing.

---

## Connect to VS Code Copilot

A `.vscode/mcp.json` file is included. It configures VS Code Copilot as an MCP client pointing at this server.

### Local (during development)

In VS Code, open the MCP panel and start the `sample-mcp-python (local)` server. No key is required locally.

### Remote (deployed to Azure)

1. Open `.vscode/mcp.json`
2. Select the `sample-mcp-python (Azure)` server
3. When prompted, enter:
   - **Function app hostname:** `<your-function-app>.azurewebsites.net`
   - **MCP extension key:** `<your-mcp_extension-key>`
4. In a Copilot chat (Agent mode), test with: *"What's the weather in Paris?"*

---

## Connect to Azure AI Foundry

MCP tool support in Azure AI Foundry is currently in **preview**.

### Prerequisites

- An [Azure AI Foundry project](https://ai.azure.com) with a deployed model (e.g. `gpt-4o-mini`)
- Your deployed MCP server endpoint and `mcp_extension` key

### Step-by-step via the Foundry portal UI

1. Go to [ai.azure.com](https://ai.azure.com) and open your project

2. In the top nav click **Build** → then click **Create agent** (or open an existing agent)

3. Select your model deployment (e.g. `gpt-4o-mini`)

4. Update the **Instructions** field:
   ```
   You are a helpful assistant. Use the available MCP tools to answer
   questions about weather, products, and orders.
   ```

5. In the **Tools** section, click **Add** → **Model Context Protocol**

6. Fill in the connection form:

   | Field | Value |
   |---|---|
   | Server label | `sample-mcp-python` |
   | Server URL | `https://<your-function-app>.azurewebsites.net/runtime/webhooks/mcp` |
   | Authentication type | **Key-based** |
   | Credential name | `x-functions-key` |
   | Credential value | `<your-mcp_extension-key>` |

   Foundry automatically creates a **project connection** to store the credential securely.

7. Click **Save**

8. In the chat playground, send: *"What's the weather in Tokyo?"*

   The agent will call `get_weather({"city": "Tokyo"})` on your Azure Function and return the result. You will see a **"Request has been approved"** indicator in the response — this is the default `require_approval: always` behaviour for MCP tools in Foundry. You can change this to `never` via the SDK if needed.

### Tip — create the Foundry project in East US

If you see *"No models with sufficient capacity available in the current region"*, create your Foundry project in **East US** which consistently has the highest gpt-4o quota.

---

## Project Structure

```
sample-mcp-python/
├── azure.yaml                  # AZD service definition
├── .vscode/
│   └── mcp.json                # VS Code Copilot MCP client config
├── infra/
│   ├── main.bicep              # Main infrastructure: Flex Consumption, Storage, Identity, Monitoring
│   ├── main.parameters.json    # AZD parameter bindings
│   ├── abbreviations.json      # Resource name prefixes
│   └── app/
│       ├── api.bicep           # Function App + App Service Plan
│       ├── rbac.bicep          # Role assignments for keyless storage
│       ├── vnet.bicep          # Optional VNet integration
│       └── storage-PrivateEndpoint.bicep
└── src/
    ├── function_app.py         # MCP tools (mcpToolTrigger)
    ├── host.json               # Extension bundle + MCP server metadata
    ├── requirements.txt        # azure-functions >= 1.24.0
    └── local.settings.json     # Local dev settings (not committed)
```

---

## Related Resources

- [MCP spec — Streamable HTTP transport](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http)
- [Azure Functions MCP trigger (preview)](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-mcp)
- [Azure AI Foundry — MCP tool](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/tools/model-context-protocol?view=foundry)
- [MCP authentication in Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/mcp-authentication?view=foundry)
- [Azure Functions Flex Consumption plan](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-plan)
