import httpx
from fastapi import Request

# Known data center and bot cities (where ambiguous corporate IPs are treated as bots)
BOT_CITIES = {
    "council bluffs", # Google Cloud
    "four oaks",      # AWS / Infrastructure Hub
    "ashburn",        # AWS us-east-1
    "boardman",       # AWS
    "prineville",     # AWS
    "boydton",        # Microsoft / Facebook
    "coffeyville",    # Microsoft
    "des moines",     # Microsoft
    "santa clara",    # DigitalOcean / AWS
    "mountain view",  # Google HQ / Bots
}

# Obvious data center ISPs (blocked everywhere globally)
BOT_ISPS = [
    "amazon", "aws", "microsoft", "azure", "digitalocean", 
    "hetzner", "linode", "ovh", "cloudflare", "fastly", "akamai", 
    "alibaba", "tencent", "oracle", "hostinger", "datacamp", "choopa",
    "google cloud", "datacenter", "hosting", "server"
]

# Ambiguous ISPs (like Google, which could be Google Cloud bots OR real people using Google Fiber)
AMBIGUOUS_ISPS = ["google", "google llc"]

def is_bot_ip(geo_data: dict) -> bool:
    """Check if the geolocation data indicates a known bot or data center."""
    city = geo_data.get("city", "").lower()
    isp = geo_data.get("isp", "").lower()
    org = geo_data.get("org", "").lower()
    as_name = geo_data.get("as", "").lower()

    combined_isp_str = f"{isp} {org} {as_name}"

    # 1. Block obvious cloud/server providers globally (e.g., AWS, DigitalOcean)
    # This prevents an AWS bot in London from getting through
    for bot_isp in BOT_ISPS:
        if bot_isp in combined_isp_str:
            return True

    # 2. Hybrid Filter: Block ambiguous ISPs ONLY if they are in known data center cities
    # This ensures a real human using Google Fiber in Kansas City gets tracked, 
    # but a Google Cloud bot in Council Bluffs gets blocked!
    for amb_isp in AMBIGUOUS_ISPS:
        if amb_isp in combined_isp_str and city in BOT_CITIES:
            return True

    return False

def get_client_ip(request: Request) -> str:
    """Extract the real IP address, prioritizing proxy headers."""
    if "cf-connecting-ip" in request.headers:
        return request.headers["cf-connecting-ip"]
    elif "x-forwarded-for" in request.headers:
        # X-Forwarded-For can contain a list of IPs; the first one is the client
        return request.headers["x-forwarded-for"].split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

async def fetch_geolocation(ip_address: str):
    """Fetch geolocation data for an IP address using ip-api.com."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://ip-api.com/json/{ip_address}")
        response.raise_for_status()
        return response.json()
