# habibi-boost

ProxRipper HTTP booster with validation pipeline.

## Pipeline

1. **Fetch** first 50k HTTP proxies from ProxRipper
2. **Filter** against persistent dead list (never deleted)
3. **Validate** - concurrent HTTP connect test (100 concurrent)
4. **Update dead list** - failed proxies added to persistent dead list (never deleted)
5. **Geolocate** working proxies via ip-api.com
5. **Output** - country-sorted proxy files + live_proxies.json

## Features

- **Dead list is permanent** - never deleted, only grows
- **Pre-filter** - skips known dead proxies before validation
- **Concurrent validation** - 100 concurrent HTTP connect tests
- **Auto geolocation** - ip-api.com batch API
- **Country-sorted output** - `country/{CC}/http.txt`

## Files

- `boost_aggregator.py` - main pipeline
- `data/dead_proxies.json` - persistent dead list (never deleted)
- `data/live_proxies.json` - working proxies with country
- `country/{CC}/http.txt` - country-sorted proxy lists
- `.github/workflows/boost.yml` - GitHub Actions (every 6 hours)

## Schedule

Runs every 6 hours via GitHub Actions. Manual trigger available via workflow_dispatch.