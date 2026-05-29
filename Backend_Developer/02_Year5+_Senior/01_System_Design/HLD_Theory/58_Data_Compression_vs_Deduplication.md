# Data Compression vs Deduplication — Storage/bandwidth bachane ke 2 tareeke

## WHAT

Dono ka maqsad ek: **kam storage/bandwidth use karo**. Par tareeka alag:

- **Compression** = data ko **chhota encode** karo (patterns/redundancy hata ke). 1 file → wahi file, kam bytes me.
- **Deduplication** = **duplicate data ek hi baar store** karo. 100 copies → 1 actual copy + 99 pointers.

| | Compression | Deduplication |
|---|---|---|
| Idea | Ek blob ko chhota karo | Repeated blobs ek baar rakho |
| Scope | Within a file/stream | Across files/blocks/users |
| Output | Encoded (decompress karna padta hai) | Original chunks + references |
| Best jab | Data me internal patterns | Bahut saara duplicate data |
| Examples | gzip, zstd, snappy, columnar DB | Dropbox, backups, Git |

> Yeh **mutually exclusive nahi** — aksar **saath** use hote hain: pehle dedup (duplicate chunks hatao), fir har unique chunk ko compress karo.

---

## COMPRESSION — Deep Dive

### Lossless vs Lossy
```
LOSSLESS → exact data wapas milta hai. (text, code, DB, zip)
           gzip, zstd, snappy, brotli, LZ4
LOSSY    → kuch detail permanently chhoot jaati hai, par chhota.
           JPEG (image), MP3 (audio), H.264 (video)
```

### Kaise kaam karta hai (intuition)
Repeating patterns ko short codes se replace karta hai.
`"aaaaaa"` → `"6a"`. `"the the the"` → reference + count. Jitni redundancy, utni acchi compression.

### Speed vs Ratio trade-off (interview point)
```
snappy/LZ4 → fast, kam compression   (real-time, DB internal)
gzip       → balanced
zstd       → tunable (fast se strong tak) — modern default
brotli     → strong, slow            (static web assets)
```
Columnar databases (Parquet, Redshift) gajab compress hote hain kyunki ek column ki values **similar** hoti hain (same type, repeated) → pattern zyada.

---

## DEDUPLICATION — Deep Dive

### File-level vs Block-level
```
FILE-LEVEL  → poori file ka hash; same file = ek copy. (simple, kam saving)
BLOCK-LEVEL → file ko chunks me todo, har chunk ka hash;
              same chunk kahin bhi ho → ek baar store. (zyada saving)
```

### Kaise (content-addressed storage)
```
1. Data ko chunks me todo
2. Har chunk ka hash nikalo (SHA-256)
3. Hash pehle se store me hai? 
      haan → bas pointer/ref-count badhao (store mat karo)
      nahi → chunk store karo
4. File = chunk-hashes ki list ban jaati hai
```

### Fixed vs Content-Defined Chunking (sookshm par important)
- **Fixed-size** (e.g. 4KB blocks): simple, par file ke start me 1 byte insert hua toh saare blocks shift → dedup tut-ta hai.
- **Content-defined (Rabin fingerprint):** chunk boundaries **content** se decide hoti hain, isliye insert hone par bhi baaki chunks same rehte hain. (Dropbox/backup systems isi ko use karte hain.)

---

## REAL LIFE ANALOGY

**Compression = kapde vacuum-pack karna.** Wahi sweater, hawa nikaal ke half size. Pehnne se pehle "decompress" (phula) karna padega.

**Deduplication = class me ek hi textbook share karna.** 100 students ke paas same book ki 100 copies rakhne ke bajaye **1 library copy** + sabke paas "shelf number" (pointer). Different books (unique chunks) hi alag rakhi jaati hain.

---

## WHEN TO USE WHAT

| Scenario | Choice | Why |
|---|---|---|
| Network payloads (API/gRPC) | Compression | Bandwidth ghatao on the wire |
| Columnar analytics DB | Compression | Similar column values → great ratio |
| Logs / text storage | Compression | High redundancy |
| Cloud file sync (Dropbox) | Dedup (+compress) | Same file/chunk many users — ek baar |
| Backup systems | Dedup + compress | Daily backups 95% same data |
| Git | Dedup (content-addressed) | Same blobs across commits stored once |
| Media (image/video/audio) | Lossy compression | Perceptual quality theek, size bahut kam |

---

## Illustrative Code (concept)

```python
import hashlib, zlib

# DEDUP — content-addressed store: same chunk ek hi baar
store = {}                       # hash -> chunk_bytes
def put_chunk(chunk: bytes) -> str:
    h = hashlib.sha256(chunk).hexdigest()
    if h not in store:           # naya hi hai toh store
        store[h] = chunk
    return h                     # file = in hashes ki list

# COMPRESSION — har unique chunk ko chhota karke rakho
def put_chunk_compressed(chunk: bytes) -> str:
    h = hashlib.sha256(chunk).hexdigest()
    if h not in store:
        store[h] = zlib.compress(chunk)   # dedup ke baad compress
    return h
# Dono saath: pehle dedup (h check), fir compress. Max saving.
```

---

## Connection to Other Topics

- **Design Dropbox** (HLD_Problems/Design_Dropbox) — block-level dedup + delta sync ka classic use.
- **CDN** (HLD_Theory/32) — compressed assets edge pe serve.
- **Serialization** (HLD_Theory/52) — compact formats (Protobuf) + compression saath.
- **Big Data** (HLD_Theory/53) — columnar compression (Parquet) storage/scan cost ghatata hai.

---

## Interview Q&A

**Q: Compression aur dedup me kya farq, ek hi cheez nahi?**
A: Nahi. Compression ek blob ke andar redundancy hatata hai (encode). Dedup duplicate blobs ko across-the-system ek baar store karta hai (reference). Aksar dono saath: dedup → fir compress.

**Q: Dropbox storage kaise bachata hai jab 1000 log same file upload karein?**
A: Block-level dedup — file chunks ke hash banao; jo chunk pehle se hai usko dobara store mat karo, sirf reference. 1000 uploads ≈ 1 actual store. Plus chunks compressed.

**Q: Fixed-size chunking ka problem kya hai dedup me?**
A: File ke beech 1 byte insert hone par saare aage ke blocks shift ho jaate hain → unke hash badal jaate hain → dedup fail. Isliye content-defined chunking (Rabin fingerprint) use hoti hai jo boundaries content se nikaalti hai.

**Q: Compression algorithm kaise choose karein?**
A: Speed vs ratio. Real-time/DB-internal → snappy/LZ4 (fast). Static web assets → brotli/gzip (strong). General modern default → zstd (tunable). Already-compressed data (JPEG/video) ko dobara compress karna bekaar.
