# Design YouTube — HLD

## Requirements

### Functional
- Upload videos (up to 10GB, any format)
- Stream videos in multiple resolutions (360p, 720p, 1080p, 4K)
- Search videos by title, description, tags
- Like, dislike, comment, subscribe
- Recommendations (related videos, home feed)
- Live streaming

### Non-Functional
- 2.7 billion users, 500M DAU
- 500 hours of video uploaded every minute
- 1 billion hours of video watched daily
- <2s video start time (low time-to-first-byte)
- 99.99% availability for streaming
- Global audience — low latency everywhere

---

## Back-of-Envelope

```
Uploads:
  500 hours/min × 60 min = 30,000 hours/hour
  Avg video = 7 min → 30,000 × 60 / 7 = ~257,000 videos/hour
  Storage per video (original 1080p, 1hr): ~2 GB
  But avg video = 7 min → ~230 MB raw
  
  Plus transcoded versions (360p, 480p, 720p, 1080p):
  ~500 MB total per video × 257k videos/hr = ~128 TB/hour uploaded

Watch:
  1B hours/day = 41.7M hours/sec? No...
  1B hours/day / 24 / 3600 = 11,574 hours/sec being watched
  11,574 hours × 3600 sec/hr × avg_bitrate(1Mbps) = 41.7 Gbps bandwidth
  Peak: ~100+ Gbps → needs CDN
```

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────┐
│                         CLIENT                           │
│  Web Browser / Mobile App / Smart TV                     │
└─────────┬──────────────────────────────┬─────────────────┘
          │ Upload                       │ Stream (HLS)
          ▼                              ▼
┌─────────────────┐           ┌──────────────────────────┐
│  Upload Service │           │  CDN (CloudFront/Akamai) │
│  (chunked)      │           │  Video segments served   │
└────────┬────────┘           │  from nearest PoP        │
         │                    └──────────────────────────┘
         ▼                              ▲
┌─────────────────┐           ┌─────────────────────────┐
│   Raw Video     │           │   Video Storage (S3)    │
│   Storage (S3)  │           │   Multiple resolutions  │
└────────┬────────┘           └─────────────────────────┘
         │                              ▲
         ▼                              │
┌─────────────────────────────────────────────────────────┐
│          Video Processing Pipeline (async)               │
│  ┌───────────┐  ┌───────────┐  ┌───────────────────┐   │
│  │ Transcode │  │ Thumbnail │  │ Content Moderation │  │
│  │  Workers  │  │ Generator │  │  (AI safety scan)  │  │
│  └───────────┘  └───────────┘  └───────────────────┘   │
└─────────────────────────────────────────────────────────┘
         │ Kafka events
         ▼
┌─────────────────────────────────────────────────────────┐
│                    Backend Services                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │  Video   │  │  Search  │  │  Recom-  │  │  User/  │ │
│  │  Meta    │  │  Service │  │  mendation│  │  Auth   │ │
│  │  Service │  │  (ES)    │  │  Service  │  │ Service │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## Video Upload Pipeline

### 1. Client-Side Chunked Upload

```python
# Client sends 5MB chunks with resumable upload
# Server tracks which chunks received

async def upload_chunk(video_id: str, chunk_index: int, chunk_data: bytes):
    chunk_key = f"raw/{video_id}/chunk_{chunk_index:04d}"
    await s3.put_object(Bucket="uploads-raw", Key=chunk_key, Body=chunk_data)
    await redis.sadd(f"chunks:{video_id}", chunk_index)
    
    # Check if all chunks received
    expected = await db.get_expected_chunks(video_id)
    received = await redis.scard(f"chunks:{video_id}")
    
    if received == expected:
        # Trigger assembly + transcoding
        await kafka.send("video.uploaded", {"video_id": video_id})
```

### 2. Video Transcoding (Async Workers)

```python
# FFmpeg-based transcoding service
import subprocess
from pathlib import Path

RESOLUTIONS = {
    "360p":  (640, 360,   800),    # (width, height, bitrate_kbps)
    "480p":  (854, 480,  1500),
    "720p": (1280, 720,  2500),
    "1080p":(1920,1080,  5000),
    "4k":   (3840,2160, 15000),
}

async def transcode_video(video_id: str, input_path: str):
    output_urls = {}
    
    for res_name, (w, h, bitrate) in RESOLUTIONS.items():
        output_path = f"/tmp/{video_id}_{res_name}.mp4"
        
        # FFmpeg command
        cmd = [
            "ffmpeg", "-i", input_path,
            "-vf", f"scale={w}:{h}",
            "-b:v", f"{bitrate}k",
            "-codec:v", "libx264",
            "-codec:a", "aac",
            "-hls_time", "10",           # 10-second HLS segments
            "-hls_playlist_type", "vod",
            f"/tmp/{video_id}_{res_name}.m3u8"
        ]
        subprocess.run(cmd, check=True)
        
        # Upload to S3
        s3_key = f"videos/{video_id}/{res_name}/"
        await upload_to_s3(f"/tmp/{video_id}_{res_name}*", s3_key)
        output_urls[res_name] = f"https://cdn.youtube.com/{s3_key}/index.m3u8"
    
    # Update DB with all resolution URLs
    await db.update_video(video_id, {
        "status": "ready",
        "stream_urls": output_urls,
    })
    
    # Notify: publish "video.ready" event
    await kafka.send("video.ready", {"video_id": video_id})
```

---

## Video Streaming — HLS (HTTP Live Streaming)

```
HLS (Apple HTTP Live Streaming):
1. Video split into small segments (2-10 second .ts files)
2. Manifest file (.m3u8) lists all segments in order
3. Client downloads manifest → downloads segments sequentially
4. Adaptive bitrate: client switches resolution based on network speed

Example manifest (index.m3u8):
  #EXTM3U
  #EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360
  360p/segment_000.ts
  360p/segment_001.ts
  ...
  #EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1280x720
  720p/segment_000.ts
  ...

All segments served from CDN → low latency globally
```

---

## Adaptive Bitrate Streaming

```python
# Player-side: automatically switch quality
class AdaptiveBitratePlayer:
    QUALITIES = ["360p", "480p", "720p", "1080p"]
    
    def __init__(self):
        self.current_quality = "720p"
        self.buffer_seconds  = 0
    
    def choose_quality(self, bandwidth_mbps: float) -> str:
        """Switch quality based on available bandwidth."""
        if bandwidth_mbps < 1:    return "360p"
        if bandwidth_mbps < 2:    return "480p"
        if bandwidth_mbps < 5:    return "720p"
        return "1080p"
    
    def on_buffering(self):
        """Step down quality on buffering."""
        idx = self.QUALITIES.index(self.current_quality)
        if idx > 0:
            self.current_quality = self.QUALITIES[idx - 1]
```

---

## Database Design

```sql
-- Videos
CREATE TABLE videos (
    id            UUID PRIMARY KEY,
    creator_id    UUID REFERENCES users(id),
    title         TEXT NOT NULL,
    description   TEXT,
    tags          TEXT[],
    status        TEXT DEFAULT 'processing',  -- 'processing','ready','deleted'
    duration_sec  INT,
    views_count   BIGINT DEFAULT 0,
    likes_count   INT DEFAULT 0,
    stream_urls   JSONB,    -- {"360p": "url", "720p": "url", ...}
    thumbnail_url TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_videos_creator ON videos(creator_id, created_at DESC);
CREATE INDEX idx_videos_tags    ON videos USING gin(tags);

-- Video segments metadata (for CDN routing)
CREATE TABLE video_segments (
    video_id   UUID REFERENCES videos(id),
    quality    TEXT,        -- '360p','720p' etc
    segment_n  INT,
    s3_key     TEXT,
    duration   FLOAT,
    PRIMARY KEY (video_id, quality, segment_n)
);
```

---

## Search with Elasticsearch

```python
from elasticsearch import AsyncElasticsearch
es = AsyncElasticsearch()

# Index video on upload
await es.index(
    index="videos",
    id=video_id,
    body={
        "title":       "How to learn Python in 2025",
        "description": "Full tutorial for beginners...",
        "tags":        ["python", "programming", "tutorial"],
        "creator":     "Tech Channel",
        "views":       1_500_000,
        "created_at":  "2025-05-20",
    }
)

# Search
results = await es.search(
    index="videos",
    body={
        "query": {
            "multi_match": {
                "query":  "python tutorial 2025",
                "fields": ["title^3", "tags^2", "description"],  # title boosted
                "type":   "best_fields",
            }
        },
        "sort": [
            {"_score": "desc"},
            {"views": "desc"},     # tie-break by views
        ],
        "from": 0, "size": 20,
    }
)
```

---

## View Count at Scale

```python
# Problem: 1B views/day = 11,500 views/sec → can't write to DB each time

# Solution: Kafka → batch aggregation → periodic DB update
# 1. Client sends "video.viewed" event to Kafka
# 2. Stream processor (Flink/Spark) counts per video per minute
# 3. Writes aggregated counts to DB every 60s

# For display: Redis counter (fast) + periodic DB sync
async def record_view(video_id: str, user_id: str):
    # Deduplicate: same user can't count twice in 1hr
    view_key = f"viewed:{video_id}:{user_id}"
    is_new = await redis.set(view_key, "1", ex=3600, nx=True)
    
    if is_new:
        await redis.incr(f"views:{video_id}")
        await kafka.send("video.viewed", {"video_id": video_id})
```

---

## Interview Talking Points

1. **Why HLS instead of RTMP for streaming?**  
   HLS uses standard HTTP → works through firewalls, CDN-friendly, adaptive bitrate. RTMP is better for live (lower latency).

2. **How do you ensure fast video start (<2s)?**  
   CDN serves segments from nearest PoP. Start with lowest quality first segment → adaptive upgrade. Pre-load first 30s.

3. **How do you handle viral videos (sudden spike)?**  
   CDN absorbs read traffic. Origin S3 never gets hit after first cache. Auto-scale transcode workers if needed.

4. **How do recommendations work?**  
   Collaborative filtering (watched by similar users) + content-based (similar tags/description). ML model pre-computes related videos, stored in Redis per video_id.
