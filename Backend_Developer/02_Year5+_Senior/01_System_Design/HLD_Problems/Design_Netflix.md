# Design Netflix (Video Streaming Platform)

---

## 1. Requirements

### Functional
- Upload videos (content team only)
- Stream videos (adaptive bitrate)
- Search and browse catalog
- Recommendation engine
- Continue watching (resume position)
- Offline download
- Multiple profiles per account, parental controls

### Non-Functional
- 200M subscribers, 100M daily active
- 15% of global internet traffic at peak
- < 2s startup time for video
- 99.99% availability
- Smooth streaming even on slow networks (adaptive bitrate)

---

## 2. Scale Estimation

| Metric | Calculation | Result |
|--------|-------------|--------|
| Concurrent streams | 100M DAU × 2h/day ÷ 86400 | ~2.3M concurrent |
| Bandwidth | 2.3M × 4 Mbps (HD avg) | ~9.2 Tbps |
| Storage per movie | 4K = 60GB, 1080p = 20GB, 720p = 10GB | ~90 GB/movie/all resolutions |
| Total catalog | 15,000 titles × 90GB | ~1.35 PB |
| New content | ~50 new titles/week × 90 GB | ~4.5 TB/week |

---

## 3. Architecture

```
Content Creators → Upload Service → Transcoding Pipeline → S3/CDN
                                                              │
Users ─────────────────────────────────────────────────────▶ CDN Edge ──▶ User
      │                                                       (nearest)
      ▼
API Gateway
  │
  ├── Auth Service (JWT, device mgmt)
  ├── Catalog Service (search, browse) → Elasticsearch
  ├── Streaming Service (get play URL, bitrate manifest)
  ├── User Service (profiles, history, watchlist)
  ├── Recommendation Service (ML pipeline)
  └── Analytics Service (Kafka → Spark → data warehouse)
```

---

## 4. Video Upload & Transcoding Pipeline

```python
from dataclasses import dataclass
from enum import Enum
import boto3, ffmpeg

class Resolution(Enum):
    R_360P  = (640, 360,   800_000)    # width, height, bitrate_bps
    R_480P  = (854, 480,   1_500_000)
    R_720P  = (1280, 720,  3_000_000)
    R_1080P = (1920, 1080, 8_000_000)
    R_4K    = (3840, 2160, 35_000_000)

@dataclass
class TranscodeJob:
    content_id: str
    source_s3_key: str
    resolutions: list[Resolution]
    status: str = "pending"

class TranscodingService:
    """
    Distributed transcoding using worker fleet.
    Each resolution is a separate job (parallelized).
    """
    SEGMENT_DURATION = 10   # seconds per HLS segment

    def transcode(self, job: TranscodeJob):
        """
        Output: HLS (HTTP Live Streaming) format
        - Master playlist: lists all quality variants
        - Per-quality playlist: lists all 10-second segments
        - Segment files: .ts chunks
        """
        for res in job.resolutions:
            w, h, bitrate = res.value
            output_prefix = f"content/{job.content_id}/{res.name.lower()}"

            # FFmpeg command (as subprocess in production)
            cmd = [
                "ffmpeg", "-i", f"s3://{job.source_s3_key}",
                "-vf", f"scale={w}:{h}",
                "-b:v", str(bitrate),
                "-codec:v", "libx264", "-codec:a", "aac",
                "-hls_time", str(self.SEGMENT_DURATION),
                "-hls_playlist_type", "vod",
                "-hls_segment_filename", f"s3://netflix-content/{output_prefix}_%03d.ts",
                f"s3://netflix-content/{output_prefix}/playlist.m3u8"
            ]
            # Execute ffmpeg...

    def generate_master_playlist(self, content_id: str, resolutions: list[Resolution]) -> str:
        """
        Master HLS playlist referencing all quality levels.
        Player uses this to switch between qualities.
        """
        lines = ["#EXTM3U"]
        for res in resolutions:
            w, h, bitrate = res.value
            lines.append(f'#EXT-X-STREAM-INF:BANDWIDTH={bitrate},RESOLUTION={w}x{h}')
            lines.append(f'https://cdn.netflix.com/content/{content_id}/{res.name.lower()}/playlist.m3u8')
        return "\n".join(lines)
```

---

## 5. CDN Strategy — Open Connect

```
Netflix's custom CDN: Open Connect Appliances (OCA)
- Netflix-owned hardware placed inside ISP data centers
- Pre-populates popular content during off-peak hours (proactive caching)
- 95% of traffic served from OCAs (not Netflix origin)

Flow:
User requests → DNS resolves to nearest OCA →
  If OCA has content → serve directly (CDN hit)
  If OCA misses → fetch from S3 origin + cache

CDN Cache Key: content_id + resolution + segment_number

Content Steering:
  - Steer user to nearest OCA based on: latency, load, ISP
  - Fallback hierarchy: local OCA → regional OCA → origin
```

```python
class CDNRouter:
    """Route video requests to optimal CDN edge node."""

    async def get_cdn_url(self, content_id: str, resolution: str,
                           user_ip: str) -> str:
        # 1. Determine user's ISP and region
        region = await self.geo_lookup(user_ip)
        isp    = await self.isp_lookup(user_ip)

        # 2. Find nearest OCA with lowest latency and available capacity
        oca = await self.steering_service.get_best_oca(region, isp, content_id)

        # 3. Generate signed URL (time-limited, prevents hotlinking)
        base_url = f"https://{oca.hostname}/content/{content_id}/{resolution}"
        signed   = self.sign_url(base_url, ttl_seconds=3600)
        return signed

    def sign_url(self, url: str, ttl_seconds: int) -> str:
        import time, hmac, hashlib
        expires = int(time.time()) + ttl_seconds
        signature = hmac.new(
            self.secret_key.encode(),
            f"{url}:{expires}".encode(),
            hashlib.sha256
        ).hexdigest()
        return f"{url}?expires={expires}&sig={signature}"
```

---

## 6. Adaptive Bitrate Streaming (ABR)

```python
class ABRPlayer:
    """
    Client-side adaptive bitrate logic.
    Measures bandwidth, switches quality to avoid buffering.
    """
    QUALITIES = [360, 480, 720, 1080, 2160]   # p values
    BUFFER_TARGET = 30      # seconds to buffer ahead
    BUFFER_LOW    = 5       # switch down if buffer < 5s
    BANDWIDTH_SMOOTH = 0.7  # EMA factor

    def __init__(self):
        self.current_quality = 720
        self.estimated_bandwidth = 5_000_000   # 5 Mbps initial

    def update_bandwidth(self, segment_size_bytes: int, download_time_s: float):
        """Exponential moving average of measured bandwidth."""
        measured = segment_size_bytes * 8 / download_time_s
        self.estimated_bandwidth = (self.BANDWIDTH_SMOOTH * self.estimated_bandwidth
                                    + (1 - self.BANDWIDTH_SMOOTH) * measured)

    def select_quality(self, buffer_seconds: float) -> int:
        """Select quality based on buffer level and bandwidth."""
        # Safety: if buffer is low, switch down regardless
        if buffer_seconds < self.BUFFER_LOW:
            idx = self.QUALITIES.index(self.current_quality)
            if idx > 0:
                self.current_quality = self.QUALITIES[idx - 1]
            return self.current_quality

        # Normal: pick highest quality that bandwidth supports
        bitrate_by_quality = {360: 800_000, 480: 1_500_000, 720: 3_000_000,
                               1080: 8_000_000, 2160: 35_000_000}
        best = 360
        for q in self.QUALITIES:
            if bitrate_by_quality[q] < self.estimated_bandwidth * 0.8:   # 80% safety margin
                best = q
        self.current_quality = best
        return best
```

---

## 7. Streaming Service

```python
class StreamingService:
    """Provides play manifest URL + resume position + DRM token."""

    async def get_play_manifest(self, user_id: str, content_id: str,
                                 device_type: str) -> dict:
        # Check entitlement (is user subscribed? does account allow this content?)
        await self.check_entitlement(user_id, content_id)

        # Get resume position from viewing history
        position = await self.get_resume_position(user_id, content_id)

        # Generate DRM license URL (Widevine / FairPlay)
        drm_token = await self.drm_service.generate_token(user_id, content_id)

        # Get best CDN URL for user
        manifest_url = await self.cdn_router.get_cdn_url(
            content_id, "master", await self.get_user_ip(user_id)
        )

        return {
            "manifest_url":   manifest_url,
            "resume_position": position,
            "drm_license_url": f"https://license.netflix.com/widevine/{drm_token}",
            "max_resolution":  self._get_max_resolution(device_type)
        }

    async def update_position(self, user_id: str, content_id: str,
                               position_seconds: int):
        """Update continue watching position every 10 seconds during playback."""
        key = f"position:{user_id}:{content_id}"
        await self.redis.setex(key, 86400 * 30, position_seconds)  # 30 day TTL
        # Async write to Cassandra for persistence
        await self.kafka.send("viewing_events",
                              {"user_id": user_id, "content_id": content_id,
                               "position": position_seconds, "ts": time.time()})
```

---

## 8. Recommendation Engine

```python
"""
Netflix Recommendation Pipeline:

Offline (batch, daily):
  Data: viewing history, ratings, device, time-of-day, geo
  Algorithm: ALS (Alternating Least Squares) collaborative filtering
  Output: top-N recommendations per user → stored in Redis

Online (real-time):
  Personalize row order based on current session context
  Bandits (explore/exploit) for new content
  Session-based context (time of day, device)

A/B Testing:
  Different recommendation algorithms in parallel
  Measure: play rate, completion rate, member retention
"""

class RecommendationService:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def get_recommendations(self, user_id: str, row: str,
                                   limit: int = 20) -> list[str]:
        """
        Fetch pre-computed recommendations for user + row type.
        rows: "continue_watching", "trending", "top_picks", "new_releases"
        """
        key = f"recs:{user_id}:{row}"
        recs = await self.redis.lrange(key, 0, limit - 1)
        if not recs:
            # Fallback to popular content for cold-start users
            recs = await self.redis.lrange(f"popular:{row}", 0, limit - 1)
        return [r.decode() for r in recs]
```

---

## 9. Failure Scenarios

| Scenario | Solution |
|----------|----------|
| CDN edge goes down | Fallback to regional CDN, then origin. Retry with different OCA. |
| Transcoding job fails | Job queue (SQS) with retry + DLQ. Idempotent job IDs. |
| Player can't buffer | ABR switches to lower quality. Minimum 360p always available. |
| Origin S3 unreachable | Multi-region S3 replication. OCAs have full copy for popular content. |
| Recommendation service down | Fallback to trending/popular (cached, no personalization). |
| DRM license failure | Cached license token (time-limited). Retry with backoff. |

---

## 10. Netflix vs YouTube — Key Differences

| Aspect | Netflix | YouTube |
|--------|---------|---------|
| Content | Curated, owned | User-generated, millions |
| Transcoding | Fewer files, very high quality | Massive volume, automated |
| CDN | Own OCA inside ISPs | Google's global CDN |
| DRM | Widevine + FairPlay (required) | Optional |
| Recommendation | Heavy ML, subscriber retention | Watch time maximization |
| Search | Catalog search (limited) | Full web-scale search |
| Live Streaming | Limited (sports events) | Full live platform |

---

## 11. Interview Questions

**Q1: Why does Netflix use HLS over DASH?**
> Both are adaptive bitrate protocols. HLS = Apple's format, native on iOS/Safari. DASH = MPEG standard, better for Android/Chrome. Netflix uses both: HLS for Apple devices, DASH for others. They're similar — both use playlists + segments. Key difference: HLS uses .ts segments, DASH uses .mp4/fMP4.

**Q2: How does Netflix pre-populate CDN caches?**
> Open Connect Appliances are placed inside ISP networks. Netflix runs a "proactive caching" service that analyzes predicted demand (based on release schedules, viewing history) and pushes content to OCAs during off-peak hours (2-6 AM). Popular new releases are pushed to thousands of OCAs before premiere.

**Q3: What is the startup time problem and how does Netflix solve it?**
> Video startup time = time from "play" click to first frame. Netflix optimizes: (1) Pre-download first segment when user hovers over title. (2) DNS pre-resolution of CDN endpoints. (3) TCP pre-connection to likely CDN. (4) Start with lowest quality, switch up as buffer fills. Target: < 2 seconds.

**Q4: How does DRM work at Netflix scale?**
> Content is encrypted at rest (AES-128). Player gets DRM license from license server. License contains decryption key valid for current session + device. Widevine (Android, Chrome), FairPlay (Apple), PlayReady (Windows). License server verifies: user subscription active, device trust level, content restrictions.

**Q5: How does Netflix handle peak traffic (e.g., new season premiere)?**
> Pre-scaling: autoscaling triggered before known peak (New Year's, popular show premiere). CDN pre-caching: content pushed to OCAs days before. ABR: players automatically adjust quality to available bandwidth. Chaos Engineering (Netflix's own practice): intentionally inject failures in production to test resilience.

**Q6: Why does Netflix have microservices on AWS when they have their own CDN?**
> Open Connect handles video delivery only (CDN). Everything else (API, auth, catalog, payments, recommendations) runs on AWS. Separation of concerns: OCA hardware is optimized for high-throughput video bytes, not API logic. AWS provides global availability, managed services (S3, Aurora, etc.).
