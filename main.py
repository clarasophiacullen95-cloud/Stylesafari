from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import requests
import random

app = FastAPI()

# Allow Base44 to fetch
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
    """Fetch products from SerpAPI for a given retailer and query"""
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
    print(f"Query for {retailer}: {search_query} returned {len(results)} products")
    return results

@app.get("/recommend")
def recommend(
    style: str = Query(None),
    lifestyle: str = Query(None),
    budget: str = Query(None),
    brands: str = Query(None)
):
    """
    Returns dynamic product recommendations:
    - brands: comma-separated list of selected brands (default: all)
    - style/lifestyle/budget are optional search filters
    - Always returns products (shuffles to provide new content)
    """
    query_terms = []
    if style:
        query_terms.append(style)
    if lifestyle:
        query_terms.append(lifestyle)
    query = " ".join(query_terms).strip()

    selected_brands = [b.strip() for b in brands.split(",")] if brands else ALL_RETAILERS

    all_products = []
    for retailer in selected_brands:
        all_products.extend(fetch_products_from_retailer(query, retailer, num=3))

    # Apply budget filter server-side if provided
    if budget:
        filtered_products = []
        for p in all_products:
            try:
                price_num = float("".join(c for c in p["price"] if c.isdigit() or c=="."))
                if price_num <= float(budget):
                    filtered_products.append(p)
            except:
                filtered_products.append(p)
        all_products = filtered_products

    # Shuffle and pick top 10
    random.shuffle(all_products)
    selected_products = all_products[:10]

    # Fallback if nothing found: fetch one product from each brand
    if not selected_products:
        fallback_products = []
        for retailer in selected_brands:
            fallback_products.extend(fetch_products_from_retailer("", retailer, num=1))
        random.shuffle(fallback_products)
        selected_products = fallback_products[:10]

    return JSONResponse({"results": selected_products})
