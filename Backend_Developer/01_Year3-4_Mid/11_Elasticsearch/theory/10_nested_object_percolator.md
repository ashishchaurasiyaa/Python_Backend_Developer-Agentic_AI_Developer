# Elasticsearch — Nested vs Object Field Type & Percolator

## Why It Matters

**Nested vs Object** is one of the most common real-world Elasticsearch
data-modeling mistakes — an array of objects mapped as the default `object`
type silently loses per-element query precision, and the bug only shows up
as "my query returns wrong results" with no error at all. This is exactly
the kind of gap worth closing even in a JD-specific/optional folder, since
it's a genuine production gotcha, not just trivia.

Senior interview: "You store `orders: [{product: 'A', qty: 2}, {product: 'B',
qty: 5}]` and search for `product=A AND qty=5` — it matches even though no
single order line has both. Why, and how do you fix it?" → object type
flattens arrays, losing the association between fields in the same element;
`nested` type fixes it.

---

## The core problem — how `object` type flattens arrays

```json
// Document
{
  "user": "alice",
  "orders": [
    { "product": "A", "qty": 2 },
    { "product": "B", "qty": 5 }
  ]
}
```

```
With default "object" mapping, Elasticsearch internally FLATTENS this to:

  orders.product: ["A", "B"]
  orders.qty: [2, 5]

The association between "A" and "2" (same array element) is LOST.
A query for product=A AND qty=5 WRONGLY MATCHES, because Lucene just
sees "A" is somewhere in orders.product and "5" is somewhere in orders.qty
— it doesn't know they came from different original elements.
```

### The fix — `nested` type

```json
PUT orders_index
{
  "mappings": {
    "properties": {
      "user": { "type": "keyword" },
      "orders": {
        "type": "nested",     // ← this line is the entire fix
        "properties": {
          "product": { "type": "keyword" },
          "qty": { "type": "integer" }
        }
      }
    }
  }
}
```

```python
# Python (elasticsearch-py) — querying a nested field REQUIRES a nested query
from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9200")

response = es.search(index="orders_index", query={
    "nested": {
        "path": "orders",
        "query": {
            "bool": {
                "must": [
                    {"term": {"orders.product": "A"}},
                    {"term": {"orders.qty": 5}},
                ]
            }
        }
    }
})
# Now CORRECTLY returns nothing — no single order line has both product=A AND qty=5
```

Under the hood, `nested` stores each array element as a **separate hidden
Lucene document**, internally joined back to the parent at query time — that
per-element isolation is exactly what preserves the field association a flat
`object` mapping destroys.

---

## When to use which

| Use `object` (default) | Use `nested` |
|---|---|
| Array elements are never queried in combination (only ever query one field at a time) | Need to query multiple fields of the SAME array element together |
| Performance matters more (nested queries are slower — extra hidden documents + join) | Correctness matters more than raw query speed |
| Single embedded object, not an array | An array of objects where cross-field queries happen |

**Cost of `nested`:** more Lucene documents internally (one hidden doc per
array element, in addition to the parent) — more disk, slightly slower
queries and reindexing. This is why ES doesn't default to `nested` — it's
an explicit tradeoff you opt into.

---

## Percolator — "reverse search" (query is stored, document is searched against it)

```
Normal search:  store documents → run a query against them → get matching docs

Percolator:     store QUERIES → run a document against them → get matching queries
```

**Real use case:** alerting/monitoring systems — "notify me when a new
article mentions 'Django' AND 'security vulnerability'" — you register that
as a **stored query**, then every new incoming document gets percolated
against ALL stored queries to see which alerts it should trigger. Doing this
the "normal" way (re-running every user's saved search against each new
document one query at a time) doesn't scale past a handful of saved searches;
percolator is built to evaluate thousands of stored queries against one
incoming document efficiently.

```json
// 1. Create a percolator-type field to hold stored queries
PUT alerts_index
{
  "mappings": {
    "properties": {
      "query": { "type": "percolator" },
      "title": { "type": "text" },
      "body": { "type": "text" }
    }
  }
}

// 2. Register a saved search AS a document
PUT alerts_index/_doc/1
{
  "query": {
    "bool": {
      "must": [
        { "match": { "body": "Django" } },
        { "match": { "body": "vulnerability" } }
      ]
    }
  }
}

// 3. When a NEW article arrives, percolate it — find which stored
//    queries (alerts) it matches
GET alerts_index/_search
{
  "query": {
    "percolate": {
      "field": "query",
      "document": {
        "title": "New Django CVE disclosed",
        "body": "A security vulnerability was found in Django's ORM..."
      }
    }
  }
}
// Returns doc _id: 1 → that stored alert query matched this document
```

**Interview-correct positioning:** percolator is genuinely niche — you're
unlikely to build this from scratch often, but recognizing "user wants to be
notified when new content matches their saved search" as the percolator use
case (rather than reaching for a cron job re-running every saved search) is
the actual signal an interviewer is checking for.

---

## Interview Q&A

**Q: You have an array of objects and a query on two fields returns wrong results — why?**
A: The field is mapped as the default `object` type, which flattens arrays —
losing which values belonged to the same original array element. Remap the
field as `type: nested` and use a `nested` query to restore per-element
field association.

**Q: What's the tradeoff of using `nested` everywhere by default?**
A: Each array element becomes a separate hidden Lucene document internally,
increasing index size and slowing both queries (extra join step) and
reindexing. Only use `nested` where cross-field queries on the same array
element are actually needed.

**Q: What's percolator search, and when would you reach for it?**
A: It inverts normal search — you store queries as documents, then percolate
an incoming document against all stored queries to find which ones match.
Used for scalable alerting ("notify me when new content matches my saved
search") — the standard alternative to re-running every user's saved search
against each new document individually.

---

Related: `01_basics_installation_crud.md` (default mapping behavior this
overrides), `08_circuit_breakers_version_conflicts.md` (nested queries
contribute to the memory pressure circuit breakers guard against, at scale).
