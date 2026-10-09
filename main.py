import asyncio
import json
import re
import importlib.util
import sys
from html import unescape
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Query
from scrapling.fetchers import StealthyFetcher

app = FastAPI(
    title="D&B Company Search API",
    description="Search companies in the D&B business directory",
    version="1.0.0",
)

BASE_URL = "https://www.dnb.com/business-directory/api/cleansematch"


def search_company(company_name: str, country_code: str = "TN"):
    params = {
        "countrycode": country_code.upper(),
        "location": "",
        "searchterm": company_name,
        "streetaddress": "",
    }

    url = f"{BASE_URL}?{urlencode(params)}"

    page = StealthyFetcher.fetch(
        url,
        headless=True,
        timeout=60000,
        wait=3000,
    )

    html = page.html_content

    # The endpoint returns JSON wrapped inside HTML.
    match = re.search(
        r"<p>\s*(\{.*\})\s*</p>",
        html,
        re.DOTALL,
    )

    json_text = unescape(match.group(1)) if match else html.strip()

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        if "challenge-platform" in html or "Just a moment" in html:
            raise HTTPException(
                status_code=503,
                detail="D&B returned a browser verification challenge.",
            )

        raise HTTPException(
            status_code=502,
            detail="D&B returned an unexpected response.",
        )

    return data


@app.get("/")
def home():
    return {
        "message": "D&B Company Search API",
        "usage": "/api/search?name=STE%20MCZEN%20TECHNOLOGIES",
        "docs": "/docs",
    }


@app.get("/api/search")
async def search(
    name: str = Query(..., min_length=2, max_length=200),
    country: str = Query("TN", min_length=2, max_length=2),
):
    try:
        # Run the synchronous browser fetch without blocking
        # FastAPI's asynchronous event loop.
        return await asyncio.to_thread(
            search_company,
            name.strip(),
            country,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Company search failed: {type(exc).__name__}",
        ) from exc

@app.get("/api/health")
def health():
    result = {
        "status": "ok",
        "python_version": sys.version,
        "scrapling_installed": (
            importlib.util.find_spec("scrapling") is not None
        ),
    }

    try:
        from scrapling.fetchers import StealthyFetcher
        result["scrapling_fetcher_import"] = "ok"
    except Exception as exc:
        result["scrapling_fetcher_import"] = "failed"
        result["import_error"] = f"{type(exc).__name__}: {exc}"

    return result
