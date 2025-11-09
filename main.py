from fastapi import FastAPI, Query
import requests
import openai
import numpy as np
import os

app = FastAPI()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
SHOPIFY_STORES = [
    "farmrio.myshopify.com",
    "reformation.myshopify.com",
    "sandroparis.myshopify.com"
]
openai.api_key = OPENAI_API_KEY

def get_user_embedding(style, lifestyle, brands):
    text = f"{style} style for {lifestyle} lifestyle. Likes brands: {', '.join(brands)}"
    resp = openai.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return resp.data[0].embedding

def get_product_embedding(title):
    resp = openai.embeddings.create(
        model="text-embedding-3-small",
        input=title
    )
    return resp.data[0].embedding

def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def fetch_shopify_products(shop_domain, limit=50):
    url = f"https://{shop_domain}/products.json?limit={limit}"
    r = requests.get(url, headers={"User-Agent":"ai-shopper/1.0"})
    if r.status_code != 200:
        return []
    data = r.json()
    products = []
    for p in data.get("products", []):
        products.append({
            "title": p["title"],
            "vendor": p.get("vendor"),
            "price": p["variants"][0]["price"] if p.get("variants") else None,
            "link": f"https://{shop_domain}/products/{p['handle']}",
            "image": p["images"][0]["src"] if p.get("images") else None
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
        results.append({
            "title": item.get("title"),
            "brand": item.get("source"),
            "price": item.get("price"),
            "link": item.get("link"),
            "image": item.get("thumbnail")
        })
    return results

@app.get("/recommend")
def recommend(
    style: str = Query(...),
    lifestyle: str = Query(...),
    budget: float = Query(None)
):
    user_vec = get_user_embedding(style, lifestyle, [])

    products = []
    for shop in SHOPIFY_STORES:
        products.extend(fetch_shopify_products(shop))

    if len(products) < 10:
        query_text = f"{style} {lifestyle} clothing"
        products.extend(serpapi_search(query_text, num=10))

    for p in products:
        p_vec = get_product_embedding(p["title"])
        p["score"] = cosine_similarity(user_vec, p_vec)

    if budget:
        products = [p for p in products if p.get("price") and float(p["price"].replace("$","")) <= budget]

    ranked = sorted(products, key=lambda x: x["score"], reverse=True)
    return {"results": ranked[:10]}
