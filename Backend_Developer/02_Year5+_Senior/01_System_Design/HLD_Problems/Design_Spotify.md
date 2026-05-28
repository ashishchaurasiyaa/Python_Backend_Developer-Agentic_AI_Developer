# Design Spotify / Music Streaming Service

---

## 1. Requirements

### Functional
- Browse catalog (songs, albums, artists, playlists).
- Search (semantic + text).
- Stream audio (mobile, desktop, web, smart speakers, car).
- Create playlists (user, collaborative).
- Personalized recommendations (Discover Weekly, Daily Mix).
- Follow artists, users.
- Offline downloads (premium).
- Sync playback state across devices.
- Royalty tracking per play.
- Geo-restricted licensing.
- Podcasts.

### Non-Functional
- 500M users globally, 200M MAU.
- 100M concurrent streams at peak.
- Audio start latency < 200ms.
- Buffer rate < 0.1%.
- Catalog: 100M songs, 5M podcasts.
- 99.95% availability.
- Royalty calculation: 100% accurate, monthly settlement.

---

## 2. Scale Estimation

| Metric | Number |
|---|---|
| Concurrent streams | 100M |
| Plays/day | 5B |
| Avg song size | 3 MB (320 kbps × 4 min) |
| Daily bandwidth | 5B × 3 MB | 15 PB/day |
| Catalog total | 100M × 3 MB | 300 TB (single quality) |
| All qualities (4x) | | 1.2 PB |
| User playlists | 4B playlists, avg 50 tracks | 200B entries |
| Search index | 100M × 1KB metadata | 100 GB |

---

## 3. High-Level Architecture

```
                ┌──────────────────────────────┐
                │ Client (web/mobile/desktop)  │
                └──────────────┬───────────────┘
                               │
                       ┌───────▼────────┐
                       │  API Gateway   │
                       └───┬──────┬─────┘
                           │      │
        ┌──────────────────┘      └─────────────────┐
        │                                            │
   ┌────▼─────────┐                          ┌───────▼────────┐
   │  Catalog/User│                          │  Audio Stream  │
   │  /Playlist   │                          │  CDN Origin    │
   │  Services    │                          └───────┬────────┘
   └──┬───┬───┬───┘                                  │
      │   │   │                                       │
  ┌───▼┐ ┌▼──┐ ┌▼────┐                       ┌────────▼─────┐
  │PG  │ │ES │ │Redis│                       │  CDN (global)│
  └────┘ └───┘ └─────┘                       └──────────────┘
                                                     │
   ┌─────────────────┐                       ┌───────▼────────┐
   │  Recommendation │                       │  S3 (master)   │
   │  Service        │                       └────────────────┘
   └─────────────────┘
        ▲
        │
   ┌────┴──────────────┐
   │ ML Training       │
   │ (Spark/Airflow)   │
   └───────────────────┘
```

---

## 4. Music Catalog

Centralized source of truth — managed by Spotify (not user-generated).

### Data model
```sql
CREATE TABLE artists (
    id           UUID PRIMARY KEY,
    name         TEXT,
    metadata     JSONB,
    monthly_listeners BIGINT
);

CREATE TABLE albums (
    id           UUID PRIMARY KEY,
    artist_id    UUID,
    title        TEXT,
    release_date DATE,
    cover_url    TEXT
);

CREATE TABLE tracks (
    id           UUID PRIMARY KEY,
    album_id     UUID,
    title        TEXT,
    duration_ms  INT,
    explicit     BOOL,
    isrc         TEXT,            -- International Standard Recording Code
    audio_master_id TEXT,         -- S3 key for master
    play_count   BIGINT
);

CREATE TABLE track_licenses (
    track_id     UUID,
    country_code TEXT,
    available    BOOL,
    PRIMARY KEY (track_id, country_code)
);
```

Sharded by `id` (UUID v7 — time-ordered).

---

## 5. Audio Storage & Delivery

### Master audio
- Lossless FLAC originals in S3.
- 1 file per track.

### Encoded variants
- 96 kbps Opus (low quality, mobile cellular).
- 160 kbps Vorbis (medium).
- 320 kbps Vorbis (high).
- HiFi: lossless FLAC.

Each variant pre-encoded on ingestion → stored in S3 → CDN.

### CDN
- Global CDN (CloudFront, Akamai, or custom).
- Track URL: `https://cdn.spotify.com/{quality}/{track_id}.opus`.
- Signed URLs (expire in 1h) prevent hotlinking.
- Edge caching: top 10K songs cached globally (long tail fetched from origin).

### Adaptive Bitrate (HLS/DASH for podcasts; raw for tracks)
- Spotify uses chunked HTTP with own protocol.
- Client requests segments, adapts to network conditions.

---

## 6. Streaming Flow

```
1. User taps "Play"
2. Client → POST /play   { track_id, device_id }
3. Server: validate license (track available in user's country?)
4. Server: log play intent → returns signed CDN URL + crypto key
5. Client: GET cdn.spotify.com/track.opus
6. CDN: serves from cache or fetches from origin
7. Client decrypts + plays
8. Client periodically reports playback progress
9. After 30s play → counts as "stream" for royalties
```

### Pre-buffering
- Client buffers 30s ahead.
- Next track pre-fetched once current is 80% played.

### Latency budget
- Tap to first audio: 200ms p99.
- Pre-warm CDN cache for hits.

---

## 7. Search

Elasticsearch indices: tracks, albums, artists, playlists, podcasts.

### Index design
```json
{
  "id": "track_xyz",
  "title": "Bohemian Rhapsody",
  "artist": "Queen",
  "album": "A Night at the Opera",
  "popularity": 95,
  "release_year": 1975,
  "duration_ms": 354000,
  "explicit": false,
  "available_in": ["US", "GB", ...]
}
```

### Query strategy
```json
{
  "query": {
    "bool": {
      "should": [
        {"match": {"title": {"query": "bohemian", "boost": 3}}},
        {"match": {"artist": {"query": "bohemian", "boost": 2}}}
      ],
      "filter": [{"term": {"available_in": "IN"}}]
    }
  },
  "sort": [
    {"_score": "desc"},
    {"popularity": "desc"}
  ]
}
```

### Autocomplete
- Edge n-gram tokenizer → fast prefix queries.
- Suggestions endpoint < 50ms.

---

## 8. Playlists

### User playlists
```sql
CREATE TABLE playlists (
    id          UUID PRIMARY KEY,
    owner_id    UUID,
    name        TEXT,
    is_public   BOOL,
    is_collab   BOOL,
    created_at  TIMESTAMPTZ
);

CREATE TABLE playlist_tracks (
    playlist_id UUID,
    track_id    UUID,
    position    INT,
    added_at    TIMESTAMPTZ,
    added_by    UUID,
    PRIMARY KEY (playlist_id, position)
);
```

### Operations
- Add track at end: `MAX(position) + 1`.
- Reorder: requires careful update; use fractional positions (LexoRank).
- Delete: gaps OK; renumber on reorder.

### Editorial playlists (Spotify-curated)
- "Today's Top Hits", "RapCaviar", country-specific.
- Updated weekly by editors + ML.
- Same schema but `owner_id = spotify_editorial`.

### Collaborative playlists
- Multiple writers.
- Conflict: last-write-wins per position.
- CRDT-like approach possible for live collab.

---

## 9. Recommendations

### Discover Weekly (the famous one)
- Personalized 30-track playlist per user, refreshed Mondays.
- Pipeline: nightly batch job.

### Algorithm sketch
```
1. Collect user's listening history (last 6 months).
2. Build user vector (embeddings from listened tracks).
3. Find similar users (collaborative filtering).
4. Generate candidate tracks (similar users' liked but user hasn't heard).
5. Re-rank by audio similarity (content-based).
6. Diversify (avoid all from same artist).
7. Filter explicit/disliked.
8. Store as playlist for the user.
```

### Real-time recommendations
- Daily Mix: 6 mixes based on listening clusters.
- "Made for You" Home page.
- Recommendation Service serves these via gRPC at < 100ms.

### Tech
- Embeddings: Annoy / FAISS for fast nearest-neighbor.
- Model training: TensorFlow / PyTorch on Spark/Kubeflow.
- Feature store: pre-computed user/track features in Redis.

---

## 10. Playback State (Spotify Connect)

Sync playback across devices: phone, desktop, smart speaker.

### State stored centrally
```python
class PlaybackState:
    user_id: str
    device_id: str
    current_track: str
    position_ms: int
    is_playing: bool
    queue: list[str]
    timestamp: int  # for staleness detection
```

Stored in Redis (low latency).

### Sync via WebSocket
- All user's devices subscribe to `playback:{user_id}` channel.
- Any device action publishes → all others receive update.

```python
async def update_state(user_id, new_state):
    await redis.set(f"playback:{user_id}", json.dumps(new_state), ex=86400)
    await redis.publish(f"playback:{user_id}", json.dumps(new_state))
```

### Conflict (two devices play simultaneously)
- Last write wins.
- Other device pauses on receiving conflicting update.

---

## 11. Offline Downloads

### Flow
- User selects album → "Download".
- Client requests `GET /download/{track_id}`.
- Server: license check + return signed URL (long TTL, 24h).
- Client downloads, stores encrypted on device.

### DRM
- Each track encrypted on server with unique key.
- License grants client a decryption key tied to device.
- Key expires; client re-licenses to keep listening offline (max 30 days).

### Storage on device
- Encrypted file in app sandbox.
- Decrypted in-memory during playback.

---

## 12. Royalty Tracking

Every "stream" (play > 30s) → counted for royalties.

### Pipeline
```
Play event → Kafka → Royalty pipeline (Spark):
  - Validate (not duplicate, not bot).
  - Match track → rights holders (label, artist, songwriter).
  - Apply rate (free tier vs premium).
  - Aggregate monthly per rights holder.
  - Generate payment files.
```

### Data integrity
- Stream events are append-only.
- Audit log immutable.
- Reconciled daily.

### Anti-fraud
- Bot detection: high play rate per user, single-song loops, suspicious geo patterns.
- Flagged streams excluded from royalties.

---

## 13. Geographic Licensing

Songs available in different countries based on licensing.

### Implementation
- `track_licenses` table per (track, country).
- Every play request checks user's country.
- Songs not available shown grayed out / excluded from playlists temporarily.

### IP geolocation
- User's signup country + current IP determine availability.
- VPN evasion: detect known VPN ranges, restrict.

---

## 14. Podcasts

Different from music:
- Long form (30-180 min).
- Streamed as HLS chunks.
- Speed adjust (1.5x, 2x).
- Resume playback at exact position.
- Less encryption needed (often free / ad-supported).

### Storage
- Audio in S3 + transcoded HLS variants.
- Metadata: episode, show, host, transcripts.

### Ad insertion (dynamic)
- Server-side: ads inserted at stream time.
- Personalized ad selection per listener.
- Counted via tracking pixels (similar to display ads).

---

## 15. Multi-Region Architecture

### Region setup
- US-East, US-West, EU, Asia.
- CDN edge in 100+ cities.
- API services regional with cross-region failover.
- User data primarily in region of signup; replicas in 2 others.

### Catalog
- Eventually consistent globally; replicated daily.
- New releases pushed simultaneously.

### Streaming
- CDN serves audio from nearest edge.
- Geographic restrictions applied.

---

## 16. Database Choices

| Data | Store | Why |
|---|---|---|
| User profiles | Postgres (sharded) | Relational, ACID |
| Catalog (tracks/artists) | Postgres + Cassandra | Mostly read-heavy |
| Playlists | Cassandra | Write-heavy, partitioned by user |
| Listening history | Cassandra (time-series) | Append-only, large volume |
| Playback state | Redis | Low latency, ephemeral |
| Search | Elasticsearch | Full-text, fuzzy |
| Recommendations | Redis / RocksDB | Pre-computed lookups |
| Royalty events | S3 + Spark | Immutable, batch-processed |

---

## 17. Caching Strategy

| Layer | Cache | TTL |
|---|---|---|
| CDN | Audio files | Months (immutable) |
| App layer | Track metadata | 1h |
| Search | Hot queries | 5m |
| Recommendations | Discover Weekly | 1 week |
| User profile | Redis | 30 min |
| Now playing | Redis | live |

---

## 18. APIs

```
GET  /search?q=...                          # search
GET  /tracks/{id}                            # track meta
GET  /tracks/{id}/stream                     # signed CDN URL
GET  /artists/{id}/top-tracks
GET  /albums/{id}
POST /me/playlists                           # create
PATCH /playlists/{id}/tracks                 # add/reorder
GET  /me/recommendations
POST /me/player/play   { uri, device_id }    # Spotify Connect
GET  /me/player                              # current state
WS   /ws/player                              # state sync
POST /tracks/{id}/play                       # log stream
```

---

## 19. Edge Cases

### Network drop mid-song
- Client buffers ahead → some grace.
- On reconnect, resume from buffered position.

### Track removed from licensing
- Already-downloaded copies expire when DRM key expires.
- Track grayed out in UI, "not available".

### Multiple devices same account
- Free: only 1 device plays at a time.
- Premium: multiple devices, but only 1 active stream.

### Family Plan
- 6 accounts under one plan.
- Each gets independent profile + recommendations.

---

## 20. Trade-offs

| Decision | Trade-off |
|---|---|
| Pre-encoded multiple qualities | Storage cost, fast serving |
| CDN-cached audio | Cost vs latency; long-tail expensive |
| Centralized playback state | Live sync; Redis SPOF risk |
| Eventually consistent catalog | Simpler, brief licensing delay |
| Heavy ML for recs | Compute cost; massive UX win |
| Server-side ad insertion (podcasts) | Personalization at cost of complexity |

---

## 21. Follow-up Questions

- **"How does shuffle work?"** → Fisher-Yates pseudo-random but biased to mix artists (otherwise 3 Beatles songs in a row feels broken).
- **"Lyrics integration?"** → Licensed via Musixmatch; line-by-line sync via timestamps.
- **"Music videos?"** → Separate video CDN, served similarly with HLS.
- **"How to handle a viral song (100M plays in a day)?"** → CDN absorbs reads. Origin uses read replicas for metadata. Royalty calc unaffected.
- **"How to A/B test recommendation algorithms?"** → User cohorts get different model versions, measure: skip rate, save rate, listening time.
- **"Real-time concert / event audio (live)?"** → HLS live streaming with low-latency CMAF; different architecture from on-demand.
- **"Why no user-uploaded music?"** → Licensing — Spotify cannot relicense user uploads to royalty payers. SoundCloud model is different.
