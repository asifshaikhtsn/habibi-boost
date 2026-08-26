import asyncio
import json
import re
import time
from collections import defaultdict
from pathlib import Path
from itertools import islice

import aiohttp

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DEAD_FILE = DATA_DIR / "dead_proxies.json"
LIVE_FILE = DATA_DIR / "live_proxies.json"
COUNTRY_DIR = ROOT / "country"

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
ADDRESS_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3}:\d{1,5})")
MAX_PROXIES = 50000
CONCURRENCY = 100
TIMEOUT = 10
PROXRIPPER_HTTP = "https://raw.githubusercontent.com/Mohammedcha/ProxRipper/main/full_proxies/http.txt"

DATA_DIR.mkdir(parents=True, exist_ok=True)
COUNTRY_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_dead_set():
    data = load_json(DEAD_FILE, {"dead": []})
    return set(data.get("dead", []))


def save_dead_set(dead_set):
    save_json(DEAD_FILE, {"dead": sorted(dead_set), "updated": time.time()})


async def fetch(url, timeout=30):
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as s:
            async with s.get(PROXRIPPER_HTTP, headers={"User-Agent": "Mozilla/5.0"}, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    return await resp.text()
    except Exception:
        pass
    return ""


async def test_proxy(proxy, semaphore):
    """Test if proxy is alive via HTTP request to httpbin.org/ip"""
    async with semaphore:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
                async with s.get(
                    "http://httpbin.org/ip",
                    proxy=f"http://{proxy}",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        return True
        except Exception:
            pass
    return False


async def geolocate_batch(ips):
    """Get country codes for IPs via ip-api.com"""
    result = {}
    batches = [ips[i:i+100] for i in range(0, len(ips), 100)]
    async with aiohttp.ClientSession() as s:
        for batch in batches:
            for attempt in range(3):
                try:
                    async with s.post(
                        "http://ip-api.com/batch",
                        json=batch,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            for entry in data:
                                if isinstance(entry, dict) and entry.get("status") == "success":
                                    result[entry["query"]] = entry.get("countryCode", "").upper()
                            break
                except Exception:
                    pass
                await asyncio.sleep(1)
    return result


async def main():
    print("[Boost] Starting ProxRipper HTTP booster...")
    
    # 1. Load dead set (persistent, never deleted)
    dead_set = set()
    if Path("data/dead_proxies.json").exists():
        data = json.loads(Path("data/dead_proxies.json").read_text())
        dead_set = set(data.get("dead", []))
    print(f"[Boost] Loaded dead list: {len(dead_set)} proxies")

    # 2. Fetch ProxRipper HTTP (first 50k)
    print("[Boost] Fetching ProxRipper HTTP (first 50k)...")
    text = ""
    async with aiohttp.ClientSession() as s:
        try:
            async with s.get(
                "https://raw.githubusercontent.com/Mohammedcha/ProxRipper/main/full_proxies/http.txt",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    text = await resp.text()
        except Exception as e:
            print(f"Fetch error: {e}")
            return

    # Parse first 50k proxies
    proxies = []
    for i, line in enumerate(text.splitlines()):
        if i >= 50000:
            break
        m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3}:\d{1,5})", line)
        if m:
            proxies.append(m.group(1))
    
    print(f"[Boost] Fetched {len(proxies)} proxies from ProxRipper")

    # 3. Filter out already dead proxies
    initial_count = len(proxies)
    filtered = [p for p in proxies if p not in dead_set]
    print(f"  After dead filter: {initial_count} -> {len(proxies)}")

    # 4. Validate proxies (concurrent)
    print("[Boost] Validating proxies (concurrent, this will take a few minutes)...")
    semaphore = asyncio.Semaphore(100)
    
    async def test_one(proxy):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
                async with s.get(
                    "http://httpbin.org/ip",
                    proxy=f"http://{proxy}",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        return True
        except Exception:
            pass
        return False

    semaphore = asyncio.Semaphore(100)
    
    async def test_one(proxy):
        async with semaphore:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
                    async with s.get(
                        "http://httpbin.org/ip",
                        proxy=f"http://{proxy}",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            return True
        except Exception:
            pass
        return False

    # Run validation
    print(f"[Boost] Validating {len(proxies)} proxies...")
    tasks = [test_one(p) for p in proxies]
    results = await asyncio.gather(*tasks)
    
    working = []
    dead_new = []
    for proxy, ok in zip(proxies, await asyncio.gather(*[test_one(p) for p in proxies])):
        if ok:
            working.append(proxy)
        else:
            dead.append(proxy)

    # Actually run validation properly
    semaphore = asyncio.Semaphore(100)
    async def test_one(proxy):
        async with semaphore:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
                    async with s.get(
                        "http://httpbin.org/ip",
                        proxy=f"http://{proxy}",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            return True
            except Exception:
                pass
            return False

    print(f"[Boost] Validating {len(proxies)} proxies...")
    tasks = [test_one(p) for p in proxies]
    results = await asyncio.gather(*tasks)
    
    working = [p for p, ok in zip(proxies, results) if ok]
    dead_new = [p for p, ok in zip(proxies, results) if not ok]
    
    print(f"  Working: {len(working)}, Dead: {len(dead_new)}")

    # 5. Update dead list (persistent, never deleted)
    dead_set.update(dead_new)
    Path("data/dead_proxies.json").write_text(json.dumps({"dead": sorted(dead_set), "updated": time.time()}))
    print(f"  Dead list updated: {len(dead_set)} total")

    # 6. Geolocate working proxies
    print(f"[Boost] Geolocating {len(working)} working proxies...")
    ips = list({p.split(":")[0] for p in working})
    country_map = {}
    async with aiohttp.ClientSession() as s:
        batches = [list(ips)[i:i+100] for i in range(0, len(ips), 100)]
        for batch in batches:
            for attempt in range(3):
                try:
                    async with aiohttp.ClientSession() as s:
                        async with s.post(
                            "http://ip-api.com/batch",
                            json=batch,
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                for entry in data:
                                    if isinstance(entry, dict) and entry.get("status") == "success":
                                        country_map[entry["query"]] = entry.get("countryCode", "").upper()
                                break
                except Exception:
                    pass
                await asyncio.sleep(1)

    # 7. Save live proxies with country
    live_data = []
    for p in working:
        ip = p.split(":")[0]
        country = country_map.get(ip, "")
        live_data.append({"proxy": p, "country": country})

    Path("data/live_proxies.json").write_text(json.dumps({
        "proxies": live_data,
        "updated": time.time()
    }))

    # 7. Sort by country and save
    country_dir = Path("country")
    country_dir.mkdir(exist_ok=True)
    
    by_country = defaultdict(list)
    for p in working:
        ip = p.split(":")[0]
        cc = country_map.get(ip, "XX")
        by_country[cc].append(p)

    for cc, proxies_list in by_country.items():
        cc_dir = Path("country") / cc
        cc_dir.mkdir(exist_ok=True)
        (Path("country") / cc / "http.txt").write_text("\n".join(proxies) + "\n")

    # Save live list
    json.dump({"proxies": live_data, "updated": time.time()}, open("data/live_proxies.json", "w"), indent=2)

    print(f"\n[Boost] DONE!")
    print(f"  Working: {len(working)}")
    print(f"  Dead (new): {len(dead_new)}")
    print(f"  Dead list total: {len(dead_set)}")
    print(f"  Countries: {len(set(c for c in country_map.values() if c))}")

if __name__ == "__main__":
    asyncio.run(main())