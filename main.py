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

# ---------- CONFIG ----------
BACKEND_BASE = "https://stylesafari-2.onrender.com" 

# List of Shopify stores (add more if needed)
SHOPIFY_STORES = [
    "reformation.myshopify.com",
    "farmrio.myshopify.com",
    "sandro-paris.myshopify.com"
    "zara.myshopify.com"
]

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

        # Direct product link
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

# ---------- Recommend endpoint ----------
@app.get("/recommend")
def recommend(style: str = Query(...), lifestyle: str = Query(...), budget: float = Query(...)):
    """
    Returns a combined list of products from Shopify stores.
    Filters can be added here if desired.
    """
    all_products = []
    for shop in SHOPIFY_STORES:
        all_products.extend(fetch_shopify_products(shop))

    return {"results": all_products}

# ---------- Image proxy endpoint ----------
@app.get("/image-proxy")
def image_proxy(url: str):
    """Streams images via backend to bypass hotlinking and allow Base44 to render images."""
    r = requests.get(url, stream=True)
    content_type = r.headers.get("Content-Type", "image/jpeg")
    headers = {"Access-Control-Allow-Origin": "*"}
    return StreamingResponse(r.raw, media_type=content_type, headers=headers)
