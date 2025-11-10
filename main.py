# main.py
import os
import sqlite3
import requests
import random
import json
import re
from typing import List, Optional
from fastapi import FastAPI, Query, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from urllib.parse import quote, unquote

# ---------- CONFIG via environment (set these on Render) ----------
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "3080492d50bea8ac9618746457b2a934ec075eb1e54335a0eedc2068e7a5100e")  # set your SerpAPI key
BACKEND_BASE = os.getenv("BACKEND_BASE", "https://stylesafari-2.onrender.com")  # your render URL
ADMIN_KEY = os.getenv("ADMIN_KEY", "stylesafari")  # protect refresh endpoint
DB_PATH = os.getenv("DB_PATH", "products.db")

# Curated brand domains (edit as needed)
CURATED_RETAILERS = [
    "zara.com",
    "hm.com",
    "sandro-paris.com",
    "thereformation.com",
    "anthropologie.com",
    "skims.com",
    "selfridges.com",
    "harrods.com"
]

# ---------- App ----------
app = FastAPI(title="AI-curated Product Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in prod if you want
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Database helpers ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        title TEXT,
        brand TEXT,
        price TEXT,
        price_num REAL,
        link TEXT,
        image_url TEXT,
        tags TEXT,
        retailer TEXT,
        source_json TEXT
    )""")
    conn.commit()
    conn.close()

def upsert_product(p):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Use product link as id if available, else title+brand hash
    pid = p.get("link") or (p.get("title", "") + "|" + p.get("brand", ""))
    pid = pid[:240]
    tags_json = json.dumps(p.get("tags", []))
    source_json = json.dumps(p.get("raw", {}))
    price_num = None
    try:
        price_num = float("".join(ch for ch in str(p.get("price","")) if ch.isdigit() or ch=="."))
    except:
        price_num = None
    c.execute("""
        INSERT OR REPLACE INTO products (id,title,brand,price,price_num,link,image_url,tags,retailer,source_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (pid, p.get("title"), p.get("brand"), p.get("price"), price_num, p.get("link"), p.get("image_url"), tags_json, p.get("retailer"), source_json))
    conn.commit()
    conn.close()

def query_products(brands: List[str], tags: List[str], budget: Optional[float], limit: int = 20):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Basic SQL to get candidates: filtered by brand if provided
    placeholders = ",".join("?" for _ in brands) if brands else ""
    if brands:
        q = f"SELECT * FROM products WHERE retailer IN ({placeholders})"
        params = brands
    else:
        q = "SELECT * FROM products"
        params = []

    c.execute(q, params)
    rows = c.fetchall()
    conn.close()

    candidates = []
    for r in rows:
        pid, title, brand, price, price_num, link, image_url, tags_json, retailer, source_json = r
        item_tags = json.loads(tags_json or "[]")
        # tag match: if any requested tag contained in item_tags -> keep
        if tags:
            matched = False
            for t in tags:
                if t.lower() in [x.lower() for x in item_tags]:
                    matched = True
                    break
            if not matched:
                continue
        # budget filter
        if budget and price_num:
            try:
                if price_num > budget:
                    continue
            except:
                pass
        candidates.append({
            "title": title,
            "brand": brand,
            "price": price,
            "link": link,
            "image_url": image_url,
            "retailer": retailer,
            "tags": item_tags
        })
    return candidates

# ---------- Utility: simple tag extraction ----------
STOPWORDS = set([
    "the","and","a","an","for","with","in","on","from","by","of","to","at","it","is","this","that","new"
])
NONALPHA = re.compile(r"[^a-z0-9\s]")

def extract_tags_from_title(title: str) -> List[str]:
    if not title:
        return []
    s = title.lower()
    s = NONALPHA.sub(" ", s)
    words = [w.strip() for w in s.split() if w and w not in STOPWORDS and len(w) >= 3]
    # return unique top words
    uniq = []
    for w in words:
        if w not in uniq:
            uniq.append(w)
    return uniq[:10]

# ---------- SerpAPI ingestion (site:retailer queries) ----------
def serpapi_fetch_for_retailer(retailer: str, query: Optional[str]=None, num=10):
    if not SERPAPI_KEY:
        print("No SERPAPI_KEY configured - skipping SerpAPI ingest")
        return []
    q = f"site:{retailer}"
    if query:
        q = f"{q} {query}"
    params = {
        "engine": "google_shopping",
        "q": q,
        "api_key": SERPAPI_KEY,
        "num": num
    }
    try:
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=12)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"SerpAPI error for {retailer}: {e}")
        return []

    out = []
    for item in data.get("shopping_results", []):
        img = item.get("thumbnail") or (item.get("images")[0] if item.get("images") else None)
        if img and img.startswith("//"):
            img = "https:" + img
        link = item.get("product_link") or item.get("link") or ""
        title = item.get("title") or ""
        brand = item.get("source") or retailer
        price = item.get("price") or ""
        tags = extract_tags_from_title(title)
        out.append({
            "title": title,
            "brand": brand,
            "price": price,
            "link": link,
            "image_url": img,
            "tags": tags,
            "retailer": retailer,
            "raw": item
        })
    return out

# ---------- Background-ish ingestion function (callable via /refresh) ----------
def ingest_all(retailers=CURATED_RETAILERS, query: Optional[str]=None):
    print("Starting ingestion for retailers:", retailers)
    count = 0
    for r in retailers:
        products = serpapi_fetch_for_retailer(r, query=query, num=12)
        for p in products:
            upsert_product(p)
            count += 1
    print(f"Ingestion complete: {count} products ingested")
    return count

# ---------- File upload handling ----------
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------- Endpoints ----------
@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/")
def root():
    return {"status": "ok", "message": "AI-curated product backend running"}

@app.get("/brands")
def get_brands():
    return {"brands": CURATED_RETAILERS}

@app.get("/refresh")
def refresh(admin_key: str = Query(...)):
    """Manual ingestion trigger (protect with ADMIN_KEY)."""
    if admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    count = ingest_all()
    return {"ingested_count": count}

@app.post("/upload")
def upload_image(file: UploadFile = File(...), title: Optional[str] = None):
    """
    Upload a user image. Returns a stable URL (served by backend) which Base44 can use.
    (Note: Render's filesystem is ephemeral; for persistence use S3/Cloud Storage)
    """
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", file.filename)
    path = os.path.join(UPLOAD_DIR, safe_name)
    with open(path, "wb") as f:
        f.write(file.file.read())
    # Return URL to uploaded file (served via /uploads/{name})
    url = f"{BACKEND_BASE}/uploads/{quote(safe_name)}"
    return {"url": url, "title": title or file.filename}

@app.get("/uploads/{name}")
def serve_upload(name: str):
    path = os.path.join(UPLOAD_DIR, unquote(name))
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path)

@app.get("/products")
def list_products(limit: int = 50):
    """Quick debug: list products from DB (not Base44 format)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT title,brand,price,link,image_url,retailer FROM products LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    out = []
    for r in rows:
        out.append({
            "title": r[0], "brand": r[1], "price": r[2], "link": r[3], "image_url": r[4], "retailer": r[5]
        })
    return {"count": len(out), "products": out}

@app.get("/recommend")
def recommend(
    style: str = Query(None),
    lifestyle: str = Query(None),
    budget: Optional[float] = Query(None),
    brands: str = Query(None),
    limit: int = Query(10)
):
    """
    Core endpoint for Base44.
    - style/lifestyle: keywords matched against extracted tags
    - brands: comma-separated retailer domains (from /brands)
    - budget: numeric (server-side filter)
    - limit: number of items to return
    """
    # Determine brand list to use
    selected_brands = [b.strip() for b in brands.split(",")] if brands else CURATED_RETAILERS

    # Build tags from style/lifestyle
    tag_keywords = []
    if style:
        tag_keywords.extend([w.lower() for w in re.sub(r"[^a-z0-9\s]"," ", style).split() if len(w) > 2])
    if lifestyle:
        tag_keywords.extend([w.lower() for w in re.sub(r"[^a-z0-9\s]"," ", lifestyle).split() if len(w) > 2])

    # Query DB
    candidates = query_products(selected_brands, tag_keywords, budget, limit=200)

    # If no candidates (strict match), relax search: ignore tags and just fetch brand items
    if not candidates:
        candidates = query_products(selected_brands, [], None, limit=200)

    # If still empty, as ultimate fallback ingest immediately (best-effort) then re-query
    if not candidates and SERPAPI_KEY:
        ingest_all(selected_brands, query=None)
        candidates = query_products(selected_brands, [], None, limit=200)

    # Shuffle and trim to limit
    random.shuffle(candidates)
    selected = candidates[:limit]

    # Ensure output format is exactly what Base44 expects
    results = []
    for p in selected:
        image_url = p.get("image_url") or "https://via.placeholder.com/300x400?text=No+Image"
        # If image_url is external, we can optionally proxy it via /image-proxy; here we'll proxy to avoid hotlink/cors issues
        encoded_img = quote(image_url, safe="")
        proxied = f"{BACKEND_BASE}/image-proxy?url={encoded_img}"
        results.append({
            "title": p.get("title"),
            "brand": p.get("brand"),
            "price": p.get("price"),
            "link": p.get("link"),
            "image_url": proxied,
            "retailer": p.get("retailer")
        })

    # If still empty, provide a friendly placeholder product
    if not results:
        results = [{
            "title": "No products found — here are curated picks",
            "brand": "",
            "price": "",
            "link": "#",
            "image_url": "https://via.placeholder.com/300x400?text=No+Products"
        }]

    return JSONResponse({"results": results})

@app.get("/image-proxy")
def image_proxy(url: str):
    """Streams images via backend to avoid hotlinking and CORS problems."""
    try:
        decoded = unquote(url)
        r = requests.get(decoded, stream=True, timeout=12, headers={"User-Agent":"ai-shopper/1.0"})
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "image/jpeg") or r.headers.get("Content-Type", "image/png") or "image/jpeg"
        return StreamingResponse(r.raw, media_type=content_type, headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e:
        print("Image proxy error:", e)
        # return placeholder
        placeholder = "https://via.placeholder.com/300x400?text=No+Image"
        r = requests.get(placeholder, stream=True, timeout=10)
        return StreamingResponse(r.raw, media_type="image/jpeg", headers={"Access-Control-Allow-Origin": "*"})
