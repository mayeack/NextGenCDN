#!/usr/bin/env python3
"""
Generate realistic CDN telemetry data for the TA_next_gen_cdn Splunk add-on.

Produces ~50,000 events across 5 sourcetypes spanning the previous 24 hours,
with a baked-in demo scenario:
  Hours 24-8 ago: Normal operations (baseline)
  Hours  8-6 ago: LAX traffic spike (3x volume)
  Hours  6-4 ago: Cache degradation (hit ratio drops)
  Hours  4-3 ago: Origin strain (latency 5x, errors rise)
  Hours  4-2 ago: Bot attack targeting LAX
  Hours  3-1 ago: UX degradation in US-West
  Hours  1-0 ago: Recovery / mitigation
"""

import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "samples")

EDGE_LOCATIONS = [
    ("LAX", "us-west-1"),
    ("SFO", "us-west-2"),
    ("DFW", "us-central-1"),
    ("IAD", "us-east-1"),
    ("ORD", "us-central-1"),
    ("ATL", "us-east-2"),
    ("FRA", "eu-central-1"),
    ("LHR", "eu-west-1"),
    ("CDG", "eu-west-1"),
    ("AMS", "eu-central-1"),
    ("NRT", "ap-northeast-1"),
    ("SIN", "ap-southeast-1"),
    ("HKG", "ap-southeast-1"),
    ("SYD", "ap-southeast-1"),
    ("GRU", "sa-east-1"),
]

EDGE_SERVERS = {loc: [f"edge-{loc.lower()}-{i:02d}" for i in range(1, 4)]
                for loc, _ in EDGE_LOCATIONS}

ORIGIN_CLUSTERS = [
    ("origin-us-west", "pool-a"),
    ("origin-us-east", "pool-b"),
    ("origin-eu", "pool-c"),
    ("origin-ap", "pool-d"),
]

URLS = [
    "/video/stream/1234", "/video/stream/5678", "/video/stream/9012",
    "/api/v2/content", "/api/v2/search", "/api/v2/user/profile",
    "/images/hero-banner.webp", "/images/product/thumb-001.jpg",
    "/css/main.min.css", "/js/app.bundle.js", "/js/vendor.chunk.js",
    "/fonts/inter-var.woff2", "/api/v2/recommendations",
    "/static/manifest.json", "/favicon.ico",
]

COUNTRIES_CITIES = [
    ("USA", "Los Angeles", "Spectrum"), ("USA", "San Francisco", "Comcast"),
    ("USA", "Dallas", "AT&T"), ("USA", "New York", "Verizon"),
    ("USA", "Chicago", "Comcast"), ("USA", "Atlanta", "AT&T"),
    ("Germany", "Frankfurt", "Deutsche Telekom"), ("UK", "London", "BT"),
    ("France", "Paris", "Orange"), ("Netherlands", "Amsterdam", "KPN"),
    ("Japan", "Tokyo", "NTT"), ("Singapore", "Singapore", "Singtel"),
    ("Australia", "Sydney", "Telstra"), ("Brazil", "Sao Paulo", "Vivo"),
    ("India", "Mumbai", "Jio"), ("Canada", "Toronto", "Bell"),
    ("South Korea", "Seoul", "SK Broadband"),
]

ATTACK_TYPES = ["bot_scraping", "ddos", "credential_stuffing", "abnormal_request_rate"]
SEVERITIES = ["low", "medium", "high", "critical"]
MITIGATIONS = ["rate_limited", "blocked", "challenged", "captcha", "null_routed"]

HTTP_METHODS = ["GET", "GET", "GET", "GET", "GET", "POST", "HEAD", "OPTIONS"]


def _ts(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _rand_ip():
    return f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def _phase(hours_ago):
    """Return scenario phase parameters based on how many hours ago the event is."""
    if hours_ago >= 8:
        return "normal"
    elif hours_ago >= 6:
        return "spike"
    elif hours_ago >= 4:
        return "cache_degrade"
    elif hours_ago >= 3:
        return "origin_strain"
    elif hours_ago >= 1:
        return "ux_degrade"
    else:
        return "recovery"


def generate_edge_access(now, count=30000):
    """Generate CDN edge access log events."""
    events = []
    start = now - timedelta(hours=24)
    interval = timedelta(hours=24) / count

    for i in range(count):
        t = start + interval * i + timedelta(seconds=random.uniform(-2, 2))
        hours_ago = (now - t).total_seconds() / 3600
        phase = _phase(hours_ago)

        if phase == "spike" and random.random() < 0.55:
            loc, pop = "LAX", "us-west-1"
        elif phase in ("cache_degrade", "origin_strain", "ux_degrade") and random.random() < 0.40:
            loc, pop = "LAX", "us-west-1"
        else:
            loc, pop = random.choice(EDGE_LOCATIONS)

        server = random.choice(EDGE_SERVERS[loc])

        if phase == "cache_degrade" and loc == "LAX":
            cache_weights = [0.40, 0.50, 0.10]
        elif phase in ("origin_strain", "ux_degrade") and loc == "LAX":
            cache_weights = [0.35, 0.55, 0.10]
        elif phase == "normal":
            cache_weights = [0.88, 0.08, 0.04]
        elif phase == "recovery":
            cache_weights = [0.80, 0.14, 0.06]
        else:
            cache_weights = [0.85, 0.10, 0.05]

        cache_status = random.choices(["HIT", "MISS", "REVALIDATED"], weights=cache_weights)[0]

        base_rt = 35 if cache_status == "HIT" else 180 if cache_status == "MISS" else 90
        if phase in ("origin_strain", "ux_degrade") and loc in ("LAX", "SFO"):
            base_rt *= 3.5

        response_time = max(1, int(random.gauss(base_rt, base_rt * 0.3)))

        origin_lat = 2 if cache_status == "HIT" else max(1, int(random.gauss(45, 15)))
        if phase == "origin_strain" and cache_status == "MISS":
            origin_lat = max(5, int(random.gauss(250, 80)))

        if phase in ("origin_strain", "ux_degrade") and random.random() < 0.08:
            status = random.choice([500, 502, 503, 504])
        elif random.random() < 0.01:
            status = random.choice([301, 302, 304, 400, 403, 404])
        else:
            status = 200

        events.append({
            "timestamp": _ts(t),
            "edge_location": loc,
            "pop": pop,
            "edge_server_id": server,
            "request_id": f"req_{random.randint(100000, 999999)}",
            "client_ip": _rand_ip(),
            "http_method": random.choice(HTTP_METHODS),
            "url": random.choice(URLS),
            "status_code": status,
            "cache_status": cache_status,
            "response_time_ms": response_time,
            "bytes_served": random.randint(512, 5242880),
            "origin_latency_ms": origin_lat,
        })

    events.sort(key=lambda e: e["timestamp"])
    return events


def generate_edge_metrics(now, count=7200):
    """Generate edge server resource utilization metrics."""
    events = []
    all_servers = []
    for loc, pop in EDGE_LOCATIONS:
        for srv in EDGE_SERVERS[loc]:
            all_servers.append((loc, pop, srv))

    start = now - timedelta(hours=24)
    per_server = count // len(all_servers)
    interval = timedelta(hours=24) / per_server

    for loc, pop, srv in all_servers:
        for i in range(per_server):
            t = start + interval * i + timedelta(seconds=random.uniform(-1, 1))
            hours_ago = (now - t).total_seconds() / 3600
            phase = _phase(hours_ago)

            cpu_base = 35
            mem_base = 50
            net_out_base = 800
            conn_base = 1200

            if phase == "spike" and loc == "LAX":
                cpu_base, mem_base, net_out_base, conn_base = 72, 78, 2800, 4500
            elif phase in ("cache_degrade", "origin_strain") and loc == "LAX":
                cpu_base, mem_base, net_out_base, conn_base = 85, 85, 3200, 5200
            elif phase == "ux_degrade" and loc in ("LAX", "SFO"):
                cpu_base, mem_base, net_out_base, conn_base = 78, 80, 2600, 4000
            elif phase == "recovery" and loc == "LAX":
                cpu_base, mem_base, net_out_base, conn_base = 50, 60, 1200, 2000

            cache_hr = 0.95
            if phase == "cache_degrade" and loc == "LAX":
                cache_hr = 0.58
            elif phase == "origin_strain" and loc == "LAX":
                cache_hr = 0.52
            elif phase == "ux_degrade" and loc == "LAX":
                cache_hr = 0.60

            events.append({
                "timestamp": _ts(t),
                "edge_server_id": srv,
                "edge_location": loc,
                "pop": pop,
                "cpu_pct": round(min(99, max(1, random.gauss(cpu_base, 8))), 1),
                "memory_pct": round(min(99, max(10, random.gauss(mem_base, 6))), 1),
                "network_in_mbps": round(max(10, random.gauss(net_out_base * 0.3, 50)), 1),
                "network_out_mbps": round(max(10, random.gauss(net_out_base, 120)), 1),
                "cache_hit_ratio": round(min(1.0, max(0.0, random.gauss(cache_hr, 0.04))), 4),
                "active_connections": max(10, int(random.gauss(conn_base, conn_base * 0.15))),
            })

    events.sort(key=lambda e: e["timestamp"])
    return events


def generate_origin_performance(now, count=4800):
    """Generate origin cluster performance metrics."""
    events = []
    start = now - timedelta(hours=24)
    per_cluster = count // len(ORIGIN_CLUSTERS)
    interval = timedelta(hours=24) / per_cluster

    for cluster, pool in ORIGIN_CLUSTERS:
        for i in range(per_cluster):
            t = start + interval * i + timedelta(seconds=random.uniform(-1, 1))
            hours_ago = (now - t).total_seconds() / 3600
            phase = _phase(hours_ago)

            lat_base = 25
            err_base = 2
            rate_base = 500

            is_west = "us-west" in cluster
            if phase == "origin_strain" and is_west:
                lat_base, err_base, rate_base = 280, 45, 2800
            elif phase == "cache_degrade" and is_west:
                lat_base, err_base, rate_base = 120, 18, 1800
            elif phase == "ux_degrade" and is_west:
                lat_base, err_base, rate_base = 180, 30, 2200
            elif phase == "spike" and is_west:
                lat_base, err_base, rate_base = 55, 5, 1200
            elif phase == "recovery" and is_west:
                lat_base, err_base, rate_base = 45, 6, 800

            events.append({
                "timestamp": _ts(t),
                "origin_cluster": cluster,
                "origin_latency_ms": max(1, int(random.gauss(lat_base, lat_base * 0.25))),
                "origin_errors": max(0, int(random.gauss(err_base, err_base * 0.4))),
                "backend_pool": pool,
                "request_rate": max(10, int(random.gauss(rate_base, rate_base * 0.15))),
            })

    events.sort(key=lambda e: e["timestamp"])
    return events


def generate_security_events(now, count=3000):
    """Generate CDN security events with attack scenario."""
    events = []
    start = now - timedelta(hours=24)
    interval = timedelta(hours=24) / count

    attacker_ips = [_rand_ip() for _ in range(30)]
    bot_ips = [_rand_ip() for _ in range(50)]

    for i in range(count):
        t = start + interval * i + timedelta(seconds=random.uniform(-3, 3))
        hours_ago = (now - t).total_seconds() / 3600
        phase = _phase(hours_ago)

        if phase in ("origin_strain", "ux_degrade"):
            if random.random() < 0.45:
                attack = "bot_scraping"
                target = "us-west-1"
                src = random.choice(bot_ips)
                rate = max(50, int(random.gauss(850, 200)))
                sev = random.choices(SEVERITIES, weights=[0.1, 0.3, 0.4, 0.2])[0]
            elif random.random() < 0.6:
                attack = "ddos"
                target = random.choice(["us-west-1", "us-west-2"])
                src = random.choice(attacker_ips)
                rate = max(100, int(random.gauss(5000, 1500)))
                sev = random.choices(SEVERITIES, weights=[0.05, 0.15, 0.4, 0.4])[0]
            else:
                attack = random.choice(["credential_stuffing", "abnormal_request_rate"])
                target = random.choice([p for _, p in EDGE_LOCATIONS])
                src = _rand_ip()
                rate = max(10, int(random.gauss(300, 100)))
                sev = random.choices(SEVERITIES, weights=[0.2, 0.4, 0.3, 0.1])[0]
        elif phase == "recovery":
            attack = random.choice(ATTACK_TYPES)
            target = random.choice([p for _, p in EDGE_LOCATIONS])
            src = random.choice(attacker_ips + bot_ips) if random.random() < 0.3 else _rand_ip()
            rate = max(5, int(random.gauss(80, 30)))
            sev = random.choices(SEVERITIES, weights=[0.5, 0.3, 0.15, 0.05])[0]
        else:
            attack = random.choice(ATTACK_TYPES)
            target = random.choice([p for _, p in EDGE_LOCATIONS])
            src = _rand_ip()
            rate = max(5, int(random.gauss(150, 60)))
            sev = random.choices(SEVERITIES, weights=[0.35, 0.35, 0.2, 0.1])[0]

        mit = "null_routed" if attack == "ddos" and sev == "critical" else random.choice(MITIGATIONS)

        events.append({
            "timestamp": _ts(t),
            "attack_type": attack,
            "source_ip": src,
            "target_pop": target,
            "request_rate": rate,
            "mitigation_action": mit,
            "severity": sev,
        })

    events.sort(key=lambda e: e["timestamp"])
    return events


def generate_user_experience(now, count=5000):
    """Generate real user monitoring telemetry."""
    events = []
    start = now - timedelta(hours=24)
    interval = timedelta(hours=24) / count

    us_west_pops = ["us-west-1", "us-west-2"]
    all_pops = [p for _, p in EDGE_LOCATIONS]

    for i in range(count):
        t = start + interval * i + timedelta(seconds=random.uniform(-3, 3))
        hours_ago = (now - t).total_seconds() / 3600
        phase = _phase(hours_ago)

        if phase in ("ux_degrade", "origin_strain") and random.random() < 0.50:
            country, city, isp = random.choice(COUNTRIES_CITIES[:6])
            cdn_pop = random.choice(us_west_pops)
        else:
            country, city, isp = random.choice(COUNTRIES_CITIES)
            cdn_pop = random.choice(all_pops)

        pl_base = 1200
        api_base = 85
        buf_base = 0.1

        is_us_west = cdn_pop in us_west_pops
        if phase == "ux_degrade" and is_us_west:
            pl_base, api_base, buf_base = 4200, 380, 0.7
        elif phase == "origin_strain" and is_us_west:
            pl_base, api_base, buf_base = 3200, 290, 0.55
        elif phase == "cache_degrade" and is_us_west:
            pl_base, api_base, buf_base = 2200, 180, 0.35
        elif phase == "spike" and is_us_west:
            pl_base, api_base, buf_base = 1600, 120, 0.2
        elif phase == "recovery" and is_us_west:
            pl_base, api_base, buf_base = 1500, 110, 0.15

        page_load = max(100, int(random.gauss(pl_base, pl_base * 0.25)))
        api_lat = max(5, int(random.gauss(api_base, api_base * 0.3)))
        buffer_events = max(0, int(random.expovariate(1.0 / max(0.01, buf_base))))

        events.append({
            "timestamp": _ts(t),
            "country": country,
            "city": city,
            "isp": isp,
            "page_load_ms": page_load,
            "video_buffer_events": buffer_events,
            "api_latency_ms": api_lat,
            "cdn_pop_used": cdn_pop,
        })

    events.sort(key=lambda e: e["timestamp"])
    return events


def write_jsonl(events, filename):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")
    return len(events)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    now = datetime.now(timezone.utc)
    random.seed(42)

    print(f"Generating CDN telemetry data as of {_ts(now)}")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    total = 0

    n = write_jsonl(generate_edge_access(now, 30000), "sample_cdn_logs.json")
    print(f"  cdn:edge:access        -> sample_cdn_logs.json           ({n:,} events)")
    total += n

    n = write_jsonl(generate_edge_metrics(now, 7200), "sample_edge_metrics.json")
    print(f"  cdn:edge:metrics       -> sample_edge_metrics.json       ({n:,} events)")
    total += n

    n = write_jsonl(generate_origin_performance(now, 4800), "sample_origin_performance.json")
    print(f"  cdn:origin:performance -> sample_origin_performance.json ({n:,} events)")
    total += n

    n = write_jsonl(generate_security_events(now, 3000), "sample_security_events.json")
    print(f"  cdn:security:events    -> sample_security_events.json    ({n:,} events)")
    total += n

    n = write_jsonl(generate_user_experience(now, 5000), "sample_user_experience.json")
    print(f"  cdn:user:experience    -> sample_user_experience.json    ({n:,} events)")
    total += n

    print(f"\nTotal: {total:,} events generated")


if __name__ == "__main__":
    main()
