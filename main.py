from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import requests
import urllib.parse
import random

app = FastAPI()

# CORS for Base44
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SERPAPI_KEY = "3080492d50bea8ac9618746457b2a934ec075eb1e54335a0eedc2068e7a5100e"

# Curated retailer list
ALL_RETAILERS = [
    "zara.com",
    "hm.com",
    "sandro-paris.com",
    "thereformation.com",
    "anthropologie.com",
    "skims.com",
    "selfridges.com",
    "harrods.com"
]

def fetch_products_from_retailer(query: str, retailer: str, num=5):
    """Fetch products from a single retailer using SerpAPI"""
    search_query = f"site:{retailer} {query}" if query else f"site:{retailer}"
    params = {
        "engine": "google_shopping",
        "q": search_query,
        "api_key": SERPAPI_KEY,
        "num": num
    }
    try:
        resp = requests.get("https://serpapi.com/search.json", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"SerpAPI error for {retailer}: {e}")
        return []

    results = []
    for item in data.get("shopping_results", []):
        img = item.get("thumbnail") or (item.get("images")[0] if item.get("images") else None)
        if img and img.startswith("//"):
            img = "https:" + img
        img = img or "https://via.placeholder.com/300x400?text=No+Image"
        link = item.get("product_link") or item.get("link") or "#"

        results.append({
            "title": item.get("title") or "Untitled Product",
            "brand": item.get("source") or retailer,
            "price": item.get("price") or "",
            "link": link,
            "image_url": img
        })

    return results

@app.get("/recommend")
def recommend(
    style: str = Query(None),
    lifestyle: str = Query(None),
    budget: str = Query(None),
    brands: str = Query(None)
):
    """
    Returns dynamic, AI-personalized product recommendations.
    - Optional brands parameter: comma-separated brand domains
    - Optional style, lifestyle, budget parameters
    - Always returns shuffled results to show new content on each refresh/search
    """
    query_terms = []
    if style:
        query_terms.append(style)
    if lifestyle:
        query_terms.append(lifestyle)
    if budget:
        query_terms.append(f"under ${budget}")
    query = " ".join(query_terms).strip()

    # Determine which brands to use
    selected_brands = [b.strip() for b in brands.split(",")] if brands else ALL_RETAILERS

    all_products = []
    for retailer in selected_brands:
        all_products.extend(fetch_products_from_retailer(query, retailer, num=3))

    # Shuffle for randomness / freshness
    random.shuffle(all_products)
    selected_products = all_products[:10]  # limit to top 10 for Base44

    if not selected_products:
        selected_products = [{
            "title": "No products found",
            "brand": "",
            "price": "",
            "link": "#",
            "image_url": "https://via.placeholder.com/300x400?text=No+Products"
        }]

    return JSONResponse({"results": selected_products})
