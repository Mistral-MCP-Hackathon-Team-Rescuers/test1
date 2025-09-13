"""
MCP Server Template
"""

from mcp.server.fastmcp import FastMCP
from pydantic import Field

import mcp.types as types

# ===============================================================
# Shak db imports: --starts
import os, json, urllib.parse
import httpx
from pydantic import Field


from dotenv import load_dotenv
load_dotenv()  # will read .env file if present
PORT = int(os.getenv("PORT", 3000))

from mcp.server.fastmcp import FastMCP
# Shak db imports: --ends
# ===============================================================

mcp = FastMCP(
    "Echo Server", 
    port=PORT,
    host="0.0.0.0",
    stateless_http=True, 
    debug=True,
    )


@mcp.tool(
    title="Echo Tool",
    description="Echo the input text",
)
def echo(text: str = Field(description="The text to echo")) -> str:
    return text


@mcp.resource(
    uri="greeting://{name}",
    description="Get a personalized greeting",
    name="Greeting Resource",
)
def get_greeting(
    name: str,
) -> str:
    return f"Hello, {name}!"


@mcp.prompt("")
def greet_user(
    name: str = Field(description="The name of the person to greet"),
    style: str = Field(description="The style of the greeting", default="friendly"),
) -> str:
    """Generate a greeting prompt"""
    styles = {
        "friendly": "Please write a warm, friendly greeting",
        "formal": "Please write a formal, professional greeting",
        "casual": "Please write a casual, relaxed greeting",
    }

    return f"{styles.get(style, styles['friendly'])} for someone named {name}."


# ===============================================================
# ---Shak : Supabase REST config (env-driven) ---starts
# ===============================================================
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE"]  # server-side only
REST_BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Prefer": "count=exact",  # gives total in Content-Range
}

def _encode_filters(params: dict) -> dict:
    """Convert {'col':'val'} -> {'col':'eq.val'} for PostgREST."""
    out = {}
    for k, v in params.items():
        if isinstance(v, bool):
            v = "true" if v else "false"
        out[k] = f"eq.{v}"
    return out

@mcp.tool(
    title="Read Supabase Table",
    description="Read rows from a Supabase Postgres table via PostgREST with equality filters, ordering, and pagination.",
)
async def read_supabase_table(
    table: str = Field(description="Table name, e.g., 'public.kaggle_data' or 'kaggle_data'"),
    select_cols: str = Field(description="Columns to select, e.g., '*', 'id,name'", default="*"),
    filters_json: str = Field(description='Equality filters as JSON, e.g., {"country":"FR"}', default="{}"),
    order_by: str = Field(description="Column to order by (optional)", default=""),
    ascending: bool = Field(description="Ascending sort if true", default=True),
    limit: int = Field(description="Max rows (default 100)", default=100),
    offset: int = Field(description="Offset (default 0)", default=0),
) -> str:
    """
    Returns: JSON string: {"rows":[...], "count": <int or null>}
    """
    try:
        tbl = table.split(".", 1)[-1]  # strip schema if passed
        params = {
            "select": select_cols,
            "limit": str(max(1, limit)),
            "offset": str(max(0, offset)),
        }
        if order_by:
            params["order"] = f"{order_by}.{ 'asc' if ascending else 'desc' }"

        # add equality filters
        filters = json.loads(filters_json or "{}")
        params.update(_encode_filters(filters))

        url = f"{REST_BASE}/{urllib.parse.quote(tbl, safe='')}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params, headers=HEADERS)
        resp.raise_for_status()

        rows = resp.json()
        cr = resp.headers.get("content-range")  # e.g., "0-9/123"
        count = int(cr.split("/")[-1]) if cr and "/" in cr and cr.split("/")[-1].isdigit() else None
        return json.dumps({"rows": rows, "count": count})
    except Exception as e:
        return json.dumps({"error": str(e)})

# ===============================================================
# ---Shak : Supabase REST config (env-driven) ---ends
# ===============================================================


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
