# AI Shopper Backend

Combined backend for an AI-powered personal shopper. 
Pulls products from Shopify stores and SerpAPI, ranked by OpenAI embeddings.

## Setup

1. Install dependencies:

```
pip install -r requirements.txt
```

2. Set environment variables:

```
export OPENAI_API_KEY=your_openai_key
export SERPAPI_KEY=your_serpapi_key
```

3. Run locally:

```
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

4. Deploy to Render.com as a Web Service.
