from fastapi import FastAPI
import requests
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SERPAPI_KEY = "your_serpapi_key_here"

def fetch_shopify_products(shop_domain, limit=50):
    url = f"https://{shop_domain}/products.json?limit={limit}"
    r = requests.get(url, headers={"User-Agent": "ai-shopper/1.0"})
    if r.status_code != 200:
        return []
    data = r.json()
    products = []
    for p in data.get("products", []):
        img = None
        if p.get("images") and len(p["images"]) > 0:
            img = p["images"][0].get("src")
            if img:
                if img.startswith("//"):
                    img = "https:" + img
                elif img.startswith("/"):
                    img = f"https://{shop_domain}{img}"
        img = img or "https://via.placeholder.com/300x400?text=No+Image"

        products.append({
    "title": p.get("title"),
    "vendor": p.get("vendor"),
    "price": p.get("variants")[0].get("price") if p.get("variants") else None,
    "link": f"https://{shop_domain}/products/{p['handle']}",  # <-- direct product link
    "image_url": f"{backend_base}/image-proxy?url={img}"
        })
    return products


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

        results.append({
    "title": item.get("title"),
    "brand": item.get("source"),
    "price": item.get("price"),
    # Prefer product-specific URL if available
    "link": item.get("product_link") or item.get("link"),
    "image_url": f"{backend_base}/image-proxy?url={img}"
        })
    return results


@app.get("/recommend")
def recommend(style: str, lifestyle: str, budget: float):
    # Example logic combining Shopify + SerpAPI results
    query = f"{style} {lifestyle} under ${budget}"
    serp_results = serpapi_search(query, num=5)

    shopify_sources = ["reformation.myshopify.com", "farmrio.myshopify.com", "sandro-paris.myshopify.com"]
    shopify_products = []
    for shop in shopify_sources:
        shopify_products.extend(fetch_shopify_products(shop))

    results = serp_results + shopify_products
    return {"results": results}
    from fastapi.responses import StreamingResponse

@app.get("/image-proxy")
def image_proxy(url: str):
    """Fetches the image and streams it through the backend to bypass hotlink restrictions."""
    r = requests.get(url, stream=True)
    content_type = r.headers.get("Content-Type", "image/jpeg")
    return StreamingResponse(r.raw, media_type=content_type)
