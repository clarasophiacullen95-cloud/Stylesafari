# main.py
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import requests
import urllib.parse

app = FastAPI()

# ---------- CONFIG (you provided these) ----------
BACKEND_BASE = "https://stylesafari-2.onrender.com"
SERPAPI_KEY = "3080492d50bea8ac9618746457b2a934ec075eb1e54335a0eedc2068e7a5100e"

# ---------- CORS (allow Base44 in browser to fetch) ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your Base44 origin later if desired
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- SerpAPI fetch ----------
def serpapi_search(query: str, num: int = 20):
    params = {
        "engine": "google_shopping",
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": num
    }
    try:
        resp = requests.get("https://serpapi.com/search.json", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"SerpAPI request error: {e}")
        return []

    results = []
    for item in data.get("shopping_results", []):
        # safe image extraction
        img = item.get("thumbnail") or (item.get("images")[0] if item.get("images") else None)
        if img and img.startswith("//"):
            img = "https:" + img
        img = img or "https://via.placeholder.com/300x400?text=No+Image"

        # safe link extraction (product_link preferred)
        link = item.get("product_link") or item.get("link") or "#"

        # URL-encode image when building proxy URL
        encoded_img = urllib.parse.quote(img, safe="")

        results.append({
            "title": item.get("title") or "Untitled Product",
            "brand": item.get("source") or "",
            "price": item.get("price") or "",
            "link": link,
            "image_url": f"{BACKEND_BASE}/image-proxy?url={encoded_img}"
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
    Returns product recommendations (SerpAPI).
    - If no query params are provided, a default 'clothing' query is used.
    - Always returns {"results": [...] } (never null) so Base44 can consume it.
    """
    # Build a friendly query: prefer provided filters, else default to "clothing"
    parts = []
    if style:
        parts.append(style)
    if lifestyle:
        parts.append(lifestyle)
    if budget:
        parts.append(f"under ${budget}")
    query = " ".join(parts).strip() or "clothing"

    products = serpapi_search(query, num=20)

    # If SerpAPI returned nothing, return a friendly placeholder product
    if not products:
        products = [{
            "title": "No products found",
            "brand": "",
            "price": "",
            "link": "#",
            "image_url": "https://via.placeholder.com/300x400?text=No+Products"
        }]

    return JSONResponse({"results": products})

# ---------- Image proxy ----------
@app.get("/image-proxy")
def image_proxy(url: str):
    """Streams an external image through the backend to bypass hotlink/CORS issues."""
    try:
        decoded = urllib.parse.unquote(url)
        r = requests.get(decoded, stream=True, timeout=10)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "image/jpeg") or "image/jpeg"
        return StreamingResponse(r.raw, media_type=content_type, headers={"Access-Control-Allow-Origin": "*"})
    except requests.exceptions.RequestException as e:
        print(f"Image proxy error: {e}")
        # fallback placeholder image served through proxy
        placeholder = "https://via.placeholder.com/300x400?text=No+Image"
        r = requests.get(placeholder, stream=True, timeout=10)
        return StreamingResponse(r.raw, media_type="image/jpeg", headers={"Access-Control-Allow-Origin": "*"})

# ---------- Root route (friendly) ----------
@app.get("/")
def root():
    return {"message": "AI Shopper Backend running. Use /recommend for product data."}
