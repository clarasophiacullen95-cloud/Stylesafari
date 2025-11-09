from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import requests
import urllib.parse

app = FastAPI()

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Base44 can fetch
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Config ----------
BACKEND_BASE = "https://stylesafari-2.onrender.com"  
SERPAPI_KEY = "3080492d50bea8ac9618746457b2a934ec075eb1e54335a0eedc2068e7a5100e"  

# ---------- SerpAPI fetch ----------
def serpapi_search(query, num=20):
    params = {
        "engine": "google_shopping",
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": num
    }
    try:
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.RequestException as e:
        print(f"SerpAPI request error: {e}")
        return []

    results = []
    for item in data.get("shopping_results", []):
        # Safe image
        img = item.get("thumbnail") or (item.get("images")[0] if item.get("images") else None)
        if img and img.startswith("//"):
            img = "https:" + img
        img = img or "https://via.placeholder.com/300x400?text=No+Image"

        # Safe link
        link = item.get("product_link") or item.get("link") or "#"

        results.append({
            "title": item.get("title") or "Untitled Product",
            "brand": item.get("source") or "",
            "price": item.get("price") or "",
            "link": link,
            "image_url": f"{BACKEND_BASE}/image-proxy?url={urllib.parse.quote(img)}"
        })

    return results

# ---------- Recommend endpoint ----------
@app.get("/recommend")
def recommend(
    style: str = Query(None),
    lifestyle: str = Query(None),
    budget: float = Query(None)
):
    """
    Returns AI-relevant products using SerpAPI.
    Always returns results array with safe fields for Base44.
    """
    query_parts = [style, lifestyle]
    query = " ".join(filter(None, query_parts))
    if budget:
        query += f" under ${budget}"
    query = query.strip() or "clothing"

    products = serpapi_search(query, num=20)

    # Ensure safe fallback
    if not products:
        products = [{
            "title": "No products found",
            "brand": "",
            "price": "",
            "link": "#",
            "image_url": "https://via.placeholder.com/300x400?text=No+Products"
        }]

    return {"results": products}

# ---------- Image proxy endpoint ----------
@app.get("/image-proxy")
def image_proxy(url: str):
    """Streams images to bypass hotlinking and ensure Base44 can render images."""
    try:
        decoded_url = urllib.parse.unquote(url)
        r = requests.get(decoded_url, stream=True, timeout=10)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "image/jpeg")
        return StreamingResponse(r.raw, media_type=content_type, headers={"Access-Control-Allow-Origin": "*"})
    except requests.exceptions.RequestException as e:
        print(f"Image proxy error: {e}")
        # Return placeholder image
        placeholder = "https://via.placeholder.com/300x400?text=No+Image"
        r = requests.get(placeholder, stream=True)
        return StreamingResponse(r.raw, media_type="image/jpeg", headers={"Access-Control-Allow-Origin": "*"})

# ---------- Root route ----------
@app.get("/")
def root():
    return {"message": "AI Shopper Backend is running. Use /recommend for product data."}
