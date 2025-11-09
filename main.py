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
BACKEND_BASE = "https://stylesafari-2.onrender.com"  # Replace with your Render URL

SHOPIFY_STORES = [
    "reformation.myshopify.com",
    "farmrio.myshopify.com",
    "sandro-paris.myshopify.com"
]

# ---------- Shopify fetch ----------
def fetch_shopify_products(shop_domain, limit=50):
    url = f"https://{shop_domain}/products.json?limit={limit}"
    try:
        r = requests.get(url, headers={"User-Agent": "ai-shopper/1.0"}, timeout=10)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {shop_domain}: {e}")
        return []

    data = r.json()
    products = []

    for p in data.get("products", []):
        # Skip if handle missing
        handle = p.get("handle")
        if not handle:
            continue

        # Get price safely
        price = None
        variants = p.get("variants")
        if variants and len(variants) > 0:
            price = variants[0].get("price")

        # Image
        img = None
        images = p.get("images") or []
        if len(images) > 0:
            img = images[0].get("src", "")
            if img:
                if img.startswith("//"):
                    img = "https:" + img
                elif img.startswith("/"):
                    img = f"https://{shop_domain}{img}"
        img = img or "https://via.placeholder.com/300x400?text=No+Image"

        # Direct Shopify product link
        link = f"https://{shop_domain}/products/{handle.strip()}"

        products.append({
            "title": p.get("title", "Untitled Product"),
            "vendor": p.get("vendor", ""),
            "price": price,
            "link": link,
            "image_url": f"{BACKEND_BASE}/image-proxy?url={img}"
        })

    return products

# ---------- Recommend endpoint ----------
@app.get("/recommend")
def recommend(
    style: str = Query(None),
    lifestyle: str = Query(None),
    budget: float = Query(None)
):
    """
    Returns all Shopify products (filters can be added later if desired)
    """
    all_products = []
    for shop in SHOPIFY_STORES:
        all_products.extend(fetch_shopify_products(shop))

    return {"results": all_products}

# ---------- Image proxy endpoint ----------
@app.get("/image-proxy")
def image_proxy(url: str):
    """Streams images via backend to bypass hotlinking and allow Base44 to render images."""
    try:
        r = requests.get(url, stream=True, timeout=10)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "image/jpeg")
        headers = {"Access-Control-Allow-Origin": "*"}
        return StreamingResponse(r.raw, media_type=content_type, headers=headers)
    except requests.exceptions.RequestException as e:
        print(f"Image proxy error: {e}")
        # Return placeholder image if the original fails
        placeholder = "https://via.placeholder.com/300x400?text=No+Image"
        r = requests.get(placeholder, stream=True)
        return StreamingResponse(r.raw, media_type="image/jpeg", headers={"Access-Control-Allow-Origin": "*"})
