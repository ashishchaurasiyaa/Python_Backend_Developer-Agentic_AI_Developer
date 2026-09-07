# Lab 2 — SNS → SQS fan-out with a message filter policy

**Goal:** Prove, live, that a `FilterPolicy` on an SNS subscription filters
at the **SNS layer**, before a message ever reaches the queue — not "the
queue receives everything and your consumer ignores what it doesn't care
about." That distinction matters for cost (you don't pay to receive/poll
messages you'll throw away) and for correctness (multiple subscribers can
each get a different SLICE of the same topic).

**Task:** Open `lab.py`. `subscribe_queue()` subscribes the queue to the
topic with no filter — it currently receives every message published,
regardless of its `priority` attribute. Add:
```python
sns.set_subscription_attributes(
    SubscriptionArn=subscription_arn,
    AttributeName="FilterPolicy",
    AttributeValue=json.dumps({"priority": ["urgent"]}),
)
```

**Verify:**
```bash
./verify.sh
```
Runs `lab.py`, which publishes 3 messages (2 `priority=urgent`, 1
`priority=low`) to the topic. PASS requires exactly 2 messages reach the
queue, and specifically that the `priority=low` one ("order #2 created")
is NOT among them.

**SOCH:**
- If a second queue subscribed to the SAME topic with a filter policy for
  `priority=low` instead, would it receive "order #2 created"? What does
  that tell you about SNS fan-out with different filters per subscriber,
  versus a single shared queue everyone reads from?
- A `FilterPolicy` matches on **message attributes**, not the message body
  itself. If `priority` had been embedded inside the JSON body instead of
  passed as a `MessageAttributes` entry, would this filter have worked at
  all? What does that imply about how you'd need to structure a producer's
  code to make topic-level filtering usable downstream?
