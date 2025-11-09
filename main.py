from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow Base44 to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "ok", "message": "Backend connected successfully"}

@app.get("/recommend")
def recommend(style: str = None, lifestyle: str = None, budget: str = None):
    # Simulated products for testing (use real ones later)
    sample_products = [
        {
            "title": "Farm Rio Printed Maxi Dress",
            "price": "$250",
            "image_url": "https://images.farmrio.com.br/media/catalog/product/f/a/farmrio-maxi-dress.jpg",
            "link": "https://www.farmrio.com/products/maxi-dress"
        },
        {
            "title": "Reformation Linen Blazer",
            "price": "$298",
            "image_url": "https://www.thereformation.com/dw/image/v2/BBXV_PRD/on/demandware.static/-/Sites-ref-master-catalog/default/dweba86f5f/images/hi-res/1309747b2201_nico_blazer_buff.jpg",
            "link": "https://www.thereformation.com/products/nico-linen-blazer"
        },
        {
            "title": "Sandro Paris Tweed Jacket",
            "price": "$545",
            "image_url": "https://www.sandro-paris.com/dw/image/v2/BJHQ_PRD/on/demandware.static/-/Sites-masterCatalog/default/dw6e75ef75/images/hi-res/127571_2V28002-40_V_1.jpg",
            "link": "https://www.sandro-paris.com/en/tweed-jacket.html"
        }
    ]

    return {"results": sample_products}
