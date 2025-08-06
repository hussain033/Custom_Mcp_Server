import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from fastmcp import FastMCP

load_dotenv()

ENDPOINT = os.getenv("AI_SEARCH_ENDPOINT")
API_KEY = os.getenv("AI_SEARCH_API_KEY")
if not ENDPOINT or not API_KEY:
    raise RuntimeError("Missing Azure Search credentials")

PRODUCTS = os.getenv("PRODUCTS", "").split(",")
product_list = [p.strip() for p in PRODUCTS if p.strip()]
if not product_list:
    raise RuntimeError("PRODUCTS env var must list at least one product")

INDEX_MAP = {}
for prod in product_list:
    env_key = f"AI_SEARCH_INDEX_NAME_{prod.lower()}"
    idx = os.getenv(env_key)
    if not idx:
        raise RuntimeError(f"Missing env var: {env_key}")
    INDEX_MAP[prod.lower()] = idx

# Pydantic response models
class SearchResult(BaseModel):
    title: str
    chunk: str

class SearchResponse(BaseModel):
    product: str
    results: List[SearchResult]

# Create FastAPI app
app = FastAPI(title="Azure Search MCP Server", version="1.0")

@app.get("/keyword_search")
async def keyword_search_resource(product: str, query: str = "", top: int = 5) -> dict:
    idx = INDEX_MAP.get(product.lower())
    if not idx:
        return {"error": f"Unknown product '{product}'"}
    client = SearchClient(endpoint=ENDPOINT, index_name=idx, credential=AzureKeyCredential(API_KEY))
    results = client.search(query or "", top=top)#, select=["title", "chunk"])
    return {"product": product, "results": [{r['url'], r['chunk']} for r in results]}
    


@app.get("/", tags=["health"])
async def health():
    return {"status": "running", "products": product_list}

@app.get("/routes", tags=["debug"])
async def get_routes():
    return [{"path": route.path, "name": route.name} for route in app.routes]

# Wrap FastAPI with MCP
mcp = FastMCP.from_fastapi(app=app, name="azure-search-mcp")

if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=8000,
        path="/mcp",
        log_level="info"
    )