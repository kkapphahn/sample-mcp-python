import json
import logging
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


class ToolProperty:
    def __init__(self, property_name: str, property_type: str, description: str):
        self.propertyName = property_name
        self.propertyType = property_type
        self.description = description

    def to_dict(self):
        return {
            "propertyName": self.propertyName,
            "propertyType": self.propertyType,
            "description": self.description,
        }


def props(*args: ToolProperty) -> str:
    return json.dumps([p.to_dict() for p in args])


# ---------------------------------------------------------------------------
# Tool: hello_mcp
# ---------------------------------------------------------------------------

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="hello_mcp",
    description="Returns a simple greeting. Use this to verify the MCP server is reachable.",
    toolProperties="[]",
)
def hello_mcp(context) -> str:
    logging.info("hello_mcp triggered")
    return "Hello from the sample MCP server running on Azure Functions!"


# ---------------------------------------------------------------------------
# Tool: get_weather
# ---------------------------------------------------------------------------

_WEATHER_PROPS = props(
    ToolProperty("city", "string", "The name of the city to get weather for."),
)

_MOCK_WEATHER = {
    "london":    {"temperature_c": 12, "condition": "Cloudy",  "humidity_pct": 78, "wind_kmh": 18},
    "tokyo":     {"temperature_c": 22, "condition": "Sunny",   "humidity_pct": 55, "wind_kmh": 10},
    "new york":  {"temperature_c": 8,  "condition": "Rainy",   "humidity_pct": 82, "wind_kmh": 25},
    "sydney":    {"temperature_c": 28, "condition": "Sunny",   "humidity_pct": 45, "wind_kmh": 14},
    "berlin":    {"temperature_c": 5,  "condition": "Snowy",   "humidity_pct": 90, "wind_kmh": 20},
    "seattle":   {"temperature_c": 10, "condition": "Drizzle", "humidity_pct": 85, "wind_kmh": 12},
    "paris":     {"temperature_c": 14, "condition": "Partly Cloudy", "humidity_pct": 65, "wind_kmh": 15},
    "dubai":     {"temperature_c": 38, "condition": "Sunny",   "humidity_pct": 30, "wind_kmh": 8},
}


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_weather",
    description="Returns current weather conditions for a given city. Uses mock data.",
    toolProperties=_WEATHER_PROPS,
)
def get_weather(context) -> str:
    logging.info("get_weather triggered")
    content = json.loads(context)
    city = content.get("arguments", content).get("city", "").strip().lower()

    weather = _MOCK_WEATHER.get(city)
    if weather:
        result = {
            "city": city.title(),
            "temperature_c": weather["temperature_c"],
            "temperature_f": round(weather["temperature_c"] * 9 / 5 + 32, 1),
            "condition": weather["condition"],
            "humidity_pct": weather["humidity_pct"],
            "wind_kmh": weather["wind_kmh"],
            "source": "mock data",
        }
    else:
        result = {
            "city": city.title() or "Unknown",
            "temperature_c": 20,
            "temperature_f": 68.0,
            "condition": "Clear",
            "humidity_pct": 60,
            "wind_kmh": 10,
            "source": "mock data (city not in database — returning default)",
        }

    return json.dumps(result)


# ---------------------------------------------------------------------------
# Tool: search_products
# ---------------------------------------------------------------------------

_SEARCH_PROPS = props(
    ToolProperty("query", "string", "Search term to find matching products."),
    ToolProperty("max_results", "string", "Maximum number of results to return (default 3, max 5)."),
)

_MOCK_PRODUCTS = [
    {"id": "P001", "name": "Wireless Noise-Cancelling Headphones", "category": "Electronics", "price_usd": 149.99, "rating": 4.7, "in_stock": True},
    {"id": "P002", "name": "Ergonomic Mechanical Keyboard",        "category": "Electronics", "price_usd": 89.99,  "rating": 4.5, "in_stock": True},
    {"id": "P003", "name": "USB-C 4-Port Hub",                     "category": "Electronics", "price_usd": 24.99,  "rating": 4.3, "in_stock": True},
    {"id": "P004", "name": "Standing Desk Converter",              "category": "Furniture",   "price_usd": 199.00, "rating": 4.6, "in_stock": False},
    {"id": "P005", "name": "Laptop Stand with Cooling Fan",        "category": "Electronics", "price_usd": 39.99,  "rating": 4.2, "in_stock": True},
    {"id": "P006", "name": "27-inch 4K Monitor",                   "category": "Electronics", "price_usd": 449.00, "rating": 4.8, "in_stock": True},
    {"id": "P007", "name": "Mesh Office Chair",                    "category": "Furniture",   "price_usd": 299.00, "rating": 4.4, "in_stock": True},
    {"id": "P008", "name": "Portable Phone Charger 20000mAh",      "category": "Electronics", "price_usd": 34.99,  "rating": 4.1, "in_stock": False},
    {"id": "P009", "name": "Smart LED Desk Lamp",                  "category": "Lighting",    "price_usd": 49.99,  "rating": 4.6, "in_stock": True},
    {"id": "P010", "name": "2m Braided USB-C Cable (3-pack)",      "category": "Electronics", "price_usd": 14.99,  "rating": 4.0, "in_stock": True},
]


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="search_products",
    description="Search a product catalog and return matching items. Uses mock data.",
    toolProperties=_SEARCH_PROPS,
)
def search_products(context) -> str:
    logging.info("search_products triggered")
    content = json.loads(context)
    args = content.get("arguments", content)
    query = args.get("query", "").strip().lower()
    try:
        max_results = min(int(args.get("max_results", 3)), 5)
    except (ValueError, TypeError):
        max_results = 3

    matches = [
        p for p in _MOCK_PRODUCTS
        if query in p["name"].lower() or query in p["category"].lower()
    ]

    if not matches:
        matches = _MOCK_PRODUCTS[:max_results]

    result = {
        "query": query,
        "total_matches": len(matches),
        "returned": min(len(matches), max_results),
        "products": matches[:max_results],
        "source": "mock data",
    }
    return json.dumps(result)


# ---------------------------------------------------------------------------
# Tool: get_order_status
# ---------------------------------------------------------------------------

_ORDER_PROPS = props(
    ToolProperty("order_id", "string", "The order ID to look up (e.g. ORD-1001)."),
)

_MOCK_ORDERS = {
    "ORD-1001": {"status": "Delivered",    "placed": "2026-02-10", "estimated_delivery": "2026-02-14", "delivered": "2026-02-13", "carrier": "FedEx",  "tracking": "FX123456789"},
    "ORD-1002": {"status": "In Transit",   "placed": "2026-02-15", "estimated_delivery": "2026-02-20", "delivered": None,          "carrier": "UPS",    "tracking": "1Z9999W99999999999"},
    "ORD-1003": {"status": "Processing",   "placed": "2026-02-18", "estimated_delivery": "2026-02-24", "delivered": None,          "carrier": None,     "tracking": None},
    "ORD-1004": {"status": "Shipped",      "placed": "2026-02-17", "estimated_delivery": "2026-02-22", "delivered": None,          "carrier": "USPS",   "tracking": "9400111899223445401090"},
    "ORD-1005": {"status": "Cancelled",    "placed": "2026-02-12", "estimated_delivery": None,          "delivered": None,          "carrier": None,     "tracking": None},
}


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_order_status",
    description="Look up the status and tracking information for an order by its ID. Uses mock data.",
    toolProperties=_ORDER_PROPS,
)
def get_order_status(context) -> str:
    logging.info("get_order_status triggered")
    content = json.loads(context)
    order_id = content.get("arguments", content).get("order_id", "").strip().upper()

    order = _MOCK_ORDERS.get(order_id)
    if order:
        result = {"order_id": order_id, **order, "source": "mock data"}
    else:
        result = {
            "order_id": order_id,
            "status": "Not Found",
            "message": f"No order found with ID '{order_id}'. Valid examples: ORD-1001 through ORD-1005.",
            "source": "mock data",
        }

    return json.dumps(result)
