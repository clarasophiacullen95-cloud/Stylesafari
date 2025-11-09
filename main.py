from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import requests

app = FastAPI()

# Allow Base44 frontend to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SERPAPI_KEY = "933af515d0770a50fc3cbe4a34ccb10e"
BACKEND_BASE = "https://stylesafari-2.onrender.com"

# ---------- Shopify fetch ----------
def fetch_shopify_products(shop_domain, limit=50):
    url = f"https://{shop_domain}/products.json?limit={limit}"
    r = requests.get(url, headers={"User-Agent": "ai-shopper/1.0"})
    if r.status_code != 200:
        return []

    data = r.json()
    products = []
    for p in data.get("products", []):
        # Image
        img = None
        if p.get("images") and len(p["images"]) > 0:
            img = p["images"][0].get("src")
            if img:
                if img.startswith("//"):
                    img = "https:" + img
                elif img.startswith("/"):
                    img = f"https://{shop_domain}{img}"
        img = img or "https://via.placeholder.com/300x400?text=No+Image"

        # Link
        handle = p.get("handle")
        if not handle:
            continue
        link = f"https://{shop_domain}/products/{handle.strip()}"

        products.append({
            "title": p.get("title"),
            "vendor": p.get("vendor"),
            "price": p.get("variants")[0].get("price") if p.get("variants") else None,
            "link": link,
            "image_url": f"{BACKEND_BASE}/image-proxy?url={img}"
        })
    return products

# ---------- SerpAPI fetch ----------
def serpapi_search(query, num=10):
    params = {
        "engine": "google_shopping",
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": num
    }
    r = requests.get("https://serpapi.com/search.json", params=params)
    r.raise_for_status()
    data = r.json()
    results = []

    for item in data.get("shopping_results", []):
        img = item.get("thumbnail") or (item.get("images")[0] if item.get("images") else None)
        if img and img.startswith("//"):
            img = "https:" + img
        img = img or "https://via.placeholder.com/300x400?text=No+Image"

        # Prefer product_link if exists, else fallback to item link
        link = item.get("product_link") or item.get("link") or None
        if link and not link.startswith("http"):
            link = None

        results.append({
            "title": item.get("title"),
            "brand": item.get("source"),
            "price": item.get("price"),
            "link": link,
            "image_url": f"{BACKEND_BASE}/image-proxy?url={img}"
        })
    return results

# ---------- Recommend endpoint ----------
@app.get("/recommend")
def recommend(style: str = Query(...), lifestyle: str = Query(...), budget: float = Query(...)):
    query = f"{style} {lifestyle} under ${budget}"

    # Fetch SerpAPI results (best-effort links)
    serp_results = serpapi_search(query, num=5)

    # Shopify sources (guaranteed valid product links)
    shopify_sources = [
        "reformation.myshopify.com",
        "farmrio.myshopify.com",
        "sandro-paris.myshopify.com"
    ]
    shopify_products = []
    for shop in shopify_sources:
        shopify_products.extend(fetch_shopify_products(shop))

    results = serp_results + shopify_products
    return {"results": results}

# ---------- Image proxy endpoint ----------
@app.get("/image-proxy")
def image_proxy(url: str):
    """Streams images via backend to bypass hotlinking."""
    r = requests.get(url, stream=True)
    content_type = r.headers.get("Content-Type", "image/jpeg")
    headers = {"Access-Control-Allow-Origin": "*"}
    return StreamingResponse(r.raw, media_type=content_type, headers=headers)
