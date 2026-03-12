# TA_next_gen_cdn - Next-Gen CDN Observability

A Splunk Technology Add-on that simulates telemetry and dashboards for a next-generation CDN observability use case. Designed for demos, proof-of-concepts, and training.

## Quick Start

### 1. Regenerate sample data with current timestamps

```bash
python3 /opt/splunk/etc/apps/TA_next_gen_cdn/bin/gen_cdn_data.py
```

This creates 50,000 events spanning the previous 24 hours from now.

### 2. Restart Splunk

```bash
/opt/splunk/bin/splunk restart
```

This registers the app, creates the `cdn` index, and auto-ingests the sample data
(the monitor inputs in `inputs.conf` are enabled by default).

### 3. Fresh Install (clean re-ingestion)

If you need to reload from scratch, stop Splunk, clean the index, regenerate, and restart:

```bash
/opt/splunk/bin/splunk stop
/opt/splunk/bin/splunk clean eventdata -index cdn -f
python3 /opt/splunk/etc/apps/TA_next_gen_cdn/bin/gen_cdn_data.py
/opt/splunk/bin/splunk start
```

### Alternative: Load via oneshot

```bash
for f in sample_cdn_logs.json:cdn:edge:access \
         sample_edge_metrics.json:cdn:edge:metrics \
         sample_origin_performance.json:cdn:origin:performance \
         sample_security_events.json:cdn:security:events \
         sample_user_experience.json:cdn:user:experience; do
  FILE="${f%%:*}"; ST="${f#*:}"
  /opt/splunk/bin/splunk add oneshot \
    /opt/splunk/etc/apps/TA_next_gen_cdn/samples/$FILE \
    -index cdn -sourcetype "$ST" -auth admin:<password>
done
```

### 4. Open the dashboards

Navigate to the **Next-Gen CDN Observability** app in the Splunk UI, or access directly:

- `https://<splunk>:8000/en-US/app/TA_next_gen_cdn/cdn_operations_dashboard`
- `https://<splunk>:8000/en-US/app/TA_next_gen_cdn/cdn_security_dashboard`
- `https://<splunk>:8000/en-US/app/TA_next_gen_cdn/cdn_experience_dashboard`

## Sourcetypes

| Sourcetype | Description | Event Count |
|---|---|---|
| `cdn:edge:access` | Edge node access logs with cache status and response metrics | ~30,000 |
| `cdn:edge:metrics` | Edge server CPU, memory, network, and cache utilization | ~7,200 |
| `cdn:origin:performance` | Origin cluster latency, errors, and request rates | ~4,800 |
| `cdn:security:events` | Security telemetry: bot detection, DDoS, credential stuffing | ~3,000 |
| `cdn:user:experience` | Real user monitoring: page load, API latency, video buffering | ~5,000 |

All events use JSON format. Fields are extracted automatically via `KV_MODE = json`.

## Dashboards

### CDN Operations Dashboard
Operational health of CDN infrastructure: edge request volume by POP, cache hit ratio trends, slowest edge locations, origin latency by cluster, and CPU/memory/network utilization.

### CDN Security Dashboard
Malicious traffic detection: attack type distribution, top attacker IPs, DDoS request rate timeline, targeted POPs, mitigation actions, and severity trends.

### Digital Experience Dashboard
Real user performance monitoring: page load by country, API latency trends (avg and p95), video buffering events, CDN POP comparison, ISP performance, and a correlation panel showing cache hit ratio vs. page load time.

## Demo Narrative

The sample data tells a realistic incident story over 24 hours:

1. **Baseline (24-8 hours ago)** - Normal operations. Cache hit ratio at ~95%, response times fast, no significant security events.

2. **Traffic Spike at LAX (8-6 hours ago)** - The LAX edge POP experiences a 3x increase in request volume. CPU and memory utilization climb on LAX edge servers.

3. **Cache Degradation (6-4 hours ago)** - Cache hit ratio at LAX drops to ~60%. MISS events surge, forcing more requests back to origin.

4. **Origin Strain (4-3 hours ago)** - Origin-us-west latency rises 5x (from ~25ms to ~280ms). Error rates spike. The backend pool struggles under load.

5. **Bot Attack (4-2 hours ago)** - Bot scraping and DDoS attacks target the LAX and us-west POPs. High and critical severity events cluster during this window.

6. **User Experience Degradation (3-1 hours ago)** - Page load times in US-West triple (from ~1.2s to ~4.2s). Video buffering events spike. API latency degrades significantly.

7. **Recovery (1-0 hours ago)** - Mitigation actions applied (rate limiting, blocking, null routing). Metrics normalize. Cache hit ratio recovers.

### Correlation Walkthrough

The **Digital Experience Dashboard** includes a dual-axis chart correlating cache hit ratio with page load time, making the cause-and-effect visible. Walk through the timeline to show how edge degradation cascades into user-facing impact.

## Lookup Tables

| File | Description |
|---|---|
| `cdn_edge_locations.csv` | 15 edge locations with region, country, and capacity |
| `cdn_pop_capacity.csv` | 10 POPs with max and current capacity in Gbps |

Lookups are automatically applied to `cdn:edge:access` events via `LOOKUP-` directives in `props.conf`.

## File Structure

```
TA_next_gen_cdn/
  default/
    app.conf              App identity and metadata
    inputs.conf           Monitor stanzas (enabled for auto-ingest on restart)
    props.conf            5 sourcetype definitions
    transforms.conf       Lookup definitions
    indexes.conf          cdn index definition
    data/ui/nav/          App navigation
    data/ui/views/        3 Simple XML dashboards
  metadata/
    default.meta          System-level export permissions
  lookups/
    cdn_edge_locations.csv
    cdn_pop_capacity.csv
  bin/
    gen_cdn_data.py       Data generator (50K events)
  samples/
    sample_cdn_logs.json
    sample_edge_metrics.json
    sample_origin_performance.json
    sample_security_events.json
    sample_user_experience.json
```
