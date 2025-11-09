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
SERPAPI_KEY = "933af515d0770a50fc3cbe4a34ccb10e" 

# ---------- SerpAPI fetch ----------
def serpapi_search(query, num=10):
    params = {
        "engine": "google_shopping",
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": num
    }
    try:
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=10)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"SerpAPI request error: {e}")
        return []

    data = r.json()
    results = []

    for item in data.get("shopping_results", []):
        img = item.get("thumbnail") or (item.get("images")[0] if item.get("images") else None)
        if img and img.startswith("//"):
            img = "https:" + img
        img = img or "https://via.placeholder.com/300x400?text=No+Image"

        # Use product_link if exists; else fallback to search page
        link = item.get("product_link") or item.get("link") or "#"

        results.append({
            "title": item.get("title", "Untitled Product"),
            "brand": item.get("source", ""),
            "price": item.get("price"),
            "link": link,
            "image_url": f"{BACKEND_BASE}/image-proxy?url={img}"
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
    Filters can be implemented later if desired.
    """
    query = ""
    if style:
        query += f"{style} "
    if lifestyle:
        query += f"{lifestyle} "
    if budget:
        query += f"under ${budget}"
    query = query.strip() or "clothing"

    results = serpapi_search(query, num=20)
    return {"results": results}

# ---------- Image proxy endpoint ----------
@app.get("/image-proxy")
def image_proxy(url: str):
    """Streams images via backend to bypass hotlinking for Base44."""
    try:
        r = requests.get(url, stream=True, timeout=10)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "image/jpeg")
        headers = {"Access-Control-Allow-Origin": "*"}
        return StreamingResponse(r.raw, media_type=content_type, headers=headers)
    except requests.exceptions.RequestException as e:
        print(f"Image proxy error: {e}")
        # Return placeholder image if original fails
        placeholder = "https://via.placeholder.com/300x400?text=No+Image"
        r = requests.get(placeholder, stream=True)
        return StreamingResponse(r.raw, media_type="image/jpeg", headers={"Access-Control-Allow-Origin": "*"})
