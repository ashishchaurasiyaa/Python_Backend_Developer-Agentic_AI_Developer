#!/usr/bin/env python3
"""
Incident Triage Simulation — Lab 01: The Checkout Timeout Cascade
====================================================================
OBJECTIVE: Ek real on-call jaisa incident dekho, khud triage karo,
phir apna answer model answer se compare karo.

WHY THIS LAB LOOKS DIFFERENT FROM THE KAFKA/CELERY LABS
---------------------------------------------------------
Un labs me code hai — TODO bharo, run karo, script khud PASS/FAIL
bata deta hai (deterministic: naya consumer group `earliest` se
padhega ya nahi, yeh checkable fact hai).

Incident diagnosis deterministic nahi hai. "Sahi SEV level kya hai"
ya "root cause kya hai" — yeh JUDGMENT calls hain, senior engineers
tak alag opinion rakh sakte hain. Isko `assert` se grade nahi kar
sakte. Isliye yahan format hai:

    1. Realistic incident data dikhega (Slack alerts + log tail +
       metrics dashboard) — bilkul jaisa on-call engineer dekhta hai.
    2. Tumse triage poocha jaayega (SEV, root cause, mitigation,
       rollback y/n) — free text, apna judgment use karo.
    3. Model answer + rubric reveal hoga.
    4. Tum khud apne answer ko checklist se compare karoge — HONEST
       self-scoring, koi script tumhe pass/fail nahi bolegi.
    5. End me mock post-mortem likhne ka practice — ek aur reveal.

Yeh wahi "SOCH" reflection spirit hai jo Kafka labs ke end me hoti
hai, bas yahan poora lab hi reflection-based hai kyunki skill khud
judgment-based hai, code-based nahi.

Ties to theory:
  - ../03_incident_response_runbooks.md  (severity levels, mitigate-
    first-investigate-after, 5 Whys, root cause vs contributing factor)
  - ../04_post_mortem_writing.md         (post-mortem structure,
    blameless language, action items with owner/due/priority)

RUN
---
    python 01_incident_triage_simulation.py             # interactive
    python 01_incident_triage_simulation.py --auto-demo  # scripted,
                                                          # no typing needed
"""

import argparse
import sys

WIDTH = 70


def rule(char: str = "─") -> str:
    return char * WIDTH


def header(title: str) -> None:
    print()
    print("═" * WIDTH)
    print(f" {title}")
    print("═" * WIDTH)


def subhead(title: str) -> None:
    print()
    print(rule())
    print(f" {title}")
    print(rule())


# ─────────────────────────────────────────────────────────────────
# PRE-FILLED ANSWERS FOR --auto-demo
# (a plausible-but-not-perfect learner: gets the big calls right,
#  root-cause hypothesis is close but not laser-precise — realistic)
# ─────────────────────────────────────────────────────────────────

DEMO_ANSWERS = {
    "sev": (
        "SEV-2. Site pura down nahi hai — browse/search/cart theek "
        "hain. Sirf checkout broken hai, but checkout core revenue "
        "path hai aur error rate climbing hai (18% se 34%), so major "
        "feature broken + many customers affected = SEV-2. Agar yeh "
        "50% cross kare ya doosre features me spread ho to SEV-1 "
        "pe escalate karunga."
    ),
    "root_cause": (
        "Lagta hai naya loyalty-service call (v2.14.0 me add hua) "
        "slow hai aur order-service ke resources ko hold kar raha "
        "hai jab tak loyalty-service respond nahi karta. Loyalty-"
        "service ka CPU alert (14:06) coincidence lag raha hai — "
        "shayad unrelated hai, main uspe zyada focus nahi kar raha."
    ),
    "mitigation": (
        "order-service ko v2.13.x pe rollback karo turant. Rollback "
        "loyalty call ko hata dega, connections free honge, checkout "
        "normal ho jayega. DB pool ya loyalty-service ko fix karne "
        "ki koshish abhi nahi — pehle bleeding rokni hai."
    ),
    "rollback": (
        "Haan, rollback karunga, wait nahi karunga. Deploy time aur "
        "error-rate climb ka time match kar raha hai, customer-facing "
        "revenue path hai, aur runbook clearly kehta hai — uncertain "
        "ho to bhi rollback karo, investigate baad me."
    ),
    "postmortem": (
        "Impact: checkout error rate 34% peak, ~13 min, ~$40k revenue "
        "lost, browse/search unaffected.\n"
        "Timeline: 14:00 deploy -> 14:06 loyalty CPU alert (red "
        "herring) -> 14:10 error rate crosses 6% -> 14:13 DB pool "
        "exhausted -> 14:15 paged -> rollback -> resolved.\n"
        "Root cause: new loyalty-service call had no timeout, so "
        "when loyalty-service got slow, order-service threads held "
        "DB connections until pool exhausted.\n"
        "What went well: alert fired within ~4 min, rollback fixed "
        "it fast once triggered.\n"
        "Action items: add timeouts to all new HTTP clients (P0, "
        "platform team); alert on DB pool utilization >80% (P0, SRE)."
    ),
}


def prompt(question: str, demo_key: str, auto_demo: bool) -> str:
    print(f"\n{question}")
    if auto_demo:
        answer = DEMO_ANSWERS[demo_key]
        for line in answer.splitlines():
            print(f"  > {line}")
        return answer
    print("  (apna jawab likho, phir Enter — multi-line ke liye ek hi")
    print("   paragraph me likho ya alag lines Enter se submit karo)")
    try:
        answer = input("  > ")
    except EOFError:
        answer = ""
    return answer


# ─────────────────────────────────────────────────────────────────
# THE INCIDENT DATA
# ─────────────────────────────────────────────────────────────────

def print_intro() -> None:
    header("INCIDENT TRIAGE SIMULATION — ShopFast Production")
    print(
        "\nDate: 2026-03-11 (Wednesday, peak afternoon traffic)\n"
        "Tumhara role: on-call backend engineer. Pager abhi baja hai.\n"
        "Neeche jo dikhega wahi hai jo tumhe real incident me dikhta "
        "hai — Slack alert channel, log tail, aur metrics dashboard. "
        "Kuch cheezein important signal hain, kuch noise hain. Yeh "
        "tumhe khud decide karna hai — koi label nahi milega."
    )


def print_slack_channel() -> None:
    subhead("#incidents-and-alerts  (Slack — auto-posted by monitoring bots)")
    print(
        "14:00:02  🚀 [deploy-bot] order-service v2.14.0 rollout STARTED\n"
        "             (changelog: \"add loyalty points preview on\n"
        "             checkout page\")\n"
        "14:04:12  🚀 [deploy-bot] order-service v2.14.0 rollout COMPLETE\n"
        "             100% of pods running v2.14.0\n"
        "14:06:47  🟡 [datadog] LOW: loyalty-service CPU 78%\n"
        "             (pod loyalty-7f9c2) — autoscaler: 3 → 5 pods\n"
        "14:07:55  🟡 [datadog] LOW: search-service P99 latency 850ms\n"
        "             (elevated but within known noisy range, 0 tickets)\n"
        "14:10:15  🟠 [datadog] MED: order-service /checkout error rate\n"
        "             6.1% (baseline <0.5%)\n"
        "14:11:30  💬 [supportbot] 4 new tickets in last 5 min, tagged\n"
        "             \"checkout stuck spinning\" / \"something went\n"
        "             wrong at checkout, please retry\"\n"
        "14:12:45  🔴 [datadog] HIGH: order-service /checkout error rate\n"
        "             18.4% and climbing\n"
        "14:14:50  🔴 [datadog] HIGH: order-service /checkout error rate\n"
        "             34.2%. order-service DB pool utilization 100%\n"
        "             (HikariPool-1)\n"
        "14:15:30  📟 [pagerduty] ON-CALL PAGED — SEV assessment needed"
    )


def print_log_tail() -> None:
    subhead("order-service — log tail (chronological, before you were paged)")
    print(
        "14:09:03  INFO   CheckoutController - POST /checkout received\n"
        "                 (session=88f2)\n"
        "14:09:03  INFO   LoyaltyClient - calling loyalty-service\n"
        "                 /v1/points/preview\n"
        "14:09:12  INFO   CheckoutController - POST /checkout received\n"
        "                 (session=91ab)\n"
        "14:09:12  INFO   LoyaltyClient - calling loyalty-service\n"
        "                 /v1/points/preview\n"
        "14:10:41  WARN   LoyaltyClient - call to loyalty-service\n"
        "                 /v1/points/preview took 9821ms (session=88f2)\n"
        "14:10:41  INFO   CheckoutController - checkout completed\n"
        "                 (session=88f2, total 9.9s)\n"
        "14:12:02  WARN   LoyaltyClient - call to loyalty-service\n"
        "                 /v1/points/preview took 14330ms (session=91ab)\n"
        "14:13:10  ERROR  HikariPool-1 - Connection is not available,\n"
        "                 request timed out after 30000ms (session=a02f)\n"
        "14:13:10  WARN   LoyaltyClient - call to loyalty-service\n"
        "                 /v1/points/preview took 30004ms (session=a02f)\n"
        "                 [no client-side timeout configured on this\n"
        "                 client — thread blocked for full duration]\n"
        "14:13:11  ERROR  CheckoutController - 503 returned (session=a02f,\n"
        "                 cause=SQLTransientConnectionException)\n"
        "14:13:44  ERROR  HikariPool-1 - Connection is not available,\n"
        "                 request timed out after 30000ms (session=c771)\n"
        "14:14:02  ERROR  HikariPool-1 - Connection is not available,\n"
        "                 request timed out after 30000ms (session=d918)\n"
        "14:14:50  ERROR  CheckoutController - 503 returned (session=c771,\n"
        "                 cause=SQLTransientConnectionException)"
    )


def print_dashboard() -> None:
    subhead('Grafana — "ShopFast Production Overview" (snapshot @ 14:16 IST)')
    print(
        "  /checkout          error rate:  34.2%  ▲▲▲  (baseline <0.5%)\n"
        "  /browse, /search   error rate:   0.3%  ─    (normal)\n"
        "  /cart               error rate:   0.4%  ─    (normal)\n"
        "\n"
        "  order-service       CPU: 41% (normal)   Memory: 58% (normal)\n"
        "  order-service       HikariPool-1 active connections: 20/20\n"
        "                      (100% utilized) 🔴\n"
        "  orders-db (postgres) CPU: 12% (normal)  connections: 24/200\n"
        "                      (normal)\n"
        "  loyalty-service     CPU: 82% (elevated, autoscaled 3→5 pods)\n"
        "  loyalty-service     error rate: 0.1% (still succeeding, just\n"
        "                      slow — not throwing errors)\n"
        "\n"
        "  Avg checkout revenue during this time slot: ~$8,000/minute"
    )


def print_timeline() -> None:
    print_slack_channel()
    print_log_tail()
    print_dashboard()


# ─────────────────────────────────────────────────────────────────
# TRIAGE
# ─────────────────────────────────────────────────────────────────

def run_triage(auto_demo: bool) -> dict:
    header("YOUR TRIAGE")
    print(
        "\nJawab do (a se d). Jo dikha usi se kaam chalao — real "
        "on-call me bhi itni hi info milti hai shuru me."
    )

    answers = {}
    answers["sev"] = prompt(
        "(a) SEV level kya assign karoge, aur kyun? "
        "(reasoning bhi likho, sirf number nahi)",
        "sev", auto_demo,
    )
    answers["root_cause"] = prompt(
        "(b) Root cause ka hypothesis kya hai?",
        "root_cause", auto_demo,
    )
    answers["mitigation"] = prompt(
        "(c) Abhi turant (immediate mitigation) kya action loge?",
        "mitigation", auto_demo,
    )
    answers["rollback"] = prompt(
        "(d) Deploy rollback karoge ya nahi? Kyun?",
        "rollback", auto_demo,
    )
    return answers


# ─────────────────────────────────────────────────────────────────
# REVEAL
# ─────────────────────────────────────────────────────────────────

def reveal(auto_demo: bool) -> None:
    header("REVEAL — What Actually Happened")

    subhead("The real root cause")
    print(
        "\nv2.14.0 ne ek naya call add kiya: har checkout par "
        "`LoyaltyClient.getPointsPreview()` loyalty-service ko hit "
        "karta hai. Is naye client pe **koi timeout configure nahi "
        "hua tha** (na connect timeout, na read timeout).\n\n"
        "Coincidentally usi 14:00 slot par loyalty-service pe ek "
        "unrelated scheduled batch job (`loyalty-points-batch-recalc`) "
        "chal raha tha jo uska CPU 78-82% tak le gaya — isiliye "
        "loyalty-service *slow* ho gaya (par crash nahi hua, error "
        "rate 0.1% hi raha — dashboard me yeh saaf dikh raha tha).\n\n"
        "order-service ka checkout request flow pehle DB connection "
        "leta hai, phir loyalty-service ko call karta hai — connection "
        "ko HOLD karte hue. Jab loyalty-service call 9s, phir 14s, "
        "phir 30s tak latak gaya (koi timeout nahi tha to rukta raha "
        "jab tak platform default 30s pe khud time-out nahi hua), "
        "order-service ka HikariCP pool (max 20 connections) exhaust "
        "ho gaya. Uske baad UNRELATED DB queries bhi 'Connection is "
        "not available' se fail hone lage — isiliye error rate "
        "checkout ke sirf loyalty-touching requests se zyada tez "
        "climb hua."
    )

    subhead("Why the obvious read is incomplete")
    print(
        "\n\"Deploy broke it, rollback karo\" — yeh DIRECTIONALLY sahi "
        "hai (rollback hi correct mitigation hai), lekin \"root cause "
        "= the deploy\" bolna surface-level hai (yaad karo "
        "04_post_mortem_writing.md ka Mistake #2: \"Root cause: bad "
        "code\" is not a root cause). Asli defect specific hai: NEW "
        "HTTP CLIENT WITHOUT A TIMEOUT. Yeh bug tab bhi wahan hota "
        "jab batch job nahi chalta — kisi bhi din loyalty-service "
        "thoda slow hota (deploy, traffic spike, network blip, kuch "
        "bhi), yehi cascade phir se hota. Batch job sirf TRIGGER tha, "
        "root cause nahi — yeh classic root-cause-vs-contributing-"
        "factor distinction hai (03_incident_response_runbooks.md, "
        "5 Whys section)."
    )

    subhead("The red herring")
    print(
        "\n14:06:47 ka loyalty-service CPU alert sabse pehle fire hua "
        "— isse investigation \"loyalty-service is broken\" ki taraf "
        "khichti hai. Par dashboard clearly dikhata hai loyalty-"
        "service error rate 0.1% hai (SUCCEEDING, just slow) aur "
        "orders-db khud bhi normal hai (CPU 12%, connections 24/200). "
        "Asli signal buried tha log tail me: 'HikariPool-1 ... timed "
        "out' + 'took 30004ms ... no client-side timeout configured' "
        "— yeh do lines back-to-back hi poori kahani batati hain."
    )

    subhead("Correct SEV level")
    print(
        "\nSEV-2. Decision tree (03_incident_response_runbooks.md, "
        "Part 7): service pura down nahi (browse/search/cart normal), "
        "par ek major feature (checkout — core revenue path) many "
        "customers ke liye broken hai aur error rate climbing hai "
        "(6% -> 18% -> 34%). Yeh exactly SEV-2 doc ke example se "
        "match karta hai (\"Payment system slow\", \"Search broken, "
        "other features OK\"). Agar yeh 50%+ tak climb karta ya "
        "browse/cart me spread hota, escalate to SEV-1.\n\n"
        "Dollar cost: ~$8,000/min checkout revenue x ~34% failure x "
        "~13 min (14:10 se ~14:23 tak rollback complete hone tak) = "
        "~$35,000-40,000 lost revenue — yeh reasoning SEV assign "
        "karte waqt madad karta hai (\"would you wake the CEO?\" test "
        "— shayad nahi for SEV-2, but definitely page on-call lead)."
    )

    subhead("Correct immediate mitigation")
    print(
        "\nROLLBACK order-service to v2.13.x — turant, bina fully "
        "root-cause samjhe. Yeh removes the offending code path "
        "immediately. Restart pods / bump pool size WOULD NOT be "
        "enough — loyalty-service abhi bhi slow hai, naye connections "
        "turant phir se exhaust ho jaate. Runbook ka mantra: "
        "**mitigate first, investigate after** — rollback hi sabse "
        "fast, safest lever hai jab uncertain ho."
    )

    subhead("Root-cause fix (NOT the immediate action — do this after)")
    print(
        "\n1. LoyaltyClient pe explicit connect+read timeout add karo "
        "(e.g. 2s) + circuit breaker.\n"
        "2. Naye outbound HTTP clients ke liye timeout mandatory "
        "banao — code review checklist / lint rule.\n"
        "3. DB pool utilization >80% pe alert add karo (yeh error-"
        "rate alert se PEHLE fire hota — earlier warning).\n"
        "4. loyalty-points-batch-recalc ko off-peak hours pe shift "
        "karne ka consider karo."
    )

    subhead("Self-assessment checklist")
    print(
        "\nApna answer upar se compare karo. Honestly check karo — "
        "koi script grade nahi kar raha, tumhara judgment hi seekh "
        "hai.\n\n"
        "  [ ] Correctly identified SEV-2 (ya sahi reasoning ke saath "
        "koi aur level, escalation criteria bhi mention kiya)\n"
        "  [ ] Loyalty-service CPU alert (14:06) ko red herring "
        "pehchana — usko root cause nahi bataya\n"
        "  [ ] \"Deploy broke it\" pe hi nahi ruke — specific defect "
        "(missing timeout / resource holding) tak pahunche\n"
        "  [ ] Rollback ko immediate mitigation chuna, restart/scale "
        "up jaisa insufficient fix nahi\n"
        "  [ ] Immediate mitigation (rollback) aur root-cause fix "
        "(timeout + circuit breaker) ko alag-alag rakha, mix nahi "
        "kiya\n"
        "  [ ] orders-db CPU normal (12%) ko evidence ki tarah use "
        "kiya ki 'database khud down nahi hai' — sirf app-side pool "
        "exhaust hua\n"
        "  [ ] Timeline ke timestamps se causal order banaya (deploy "
        "-> loyalty slow -> pool exhaust -> checkout errors), sirf "
        "correlation pe bhroasa nahi kiya"
    )

    if auto_demo:
        print(
            "\n(auto-demo note: upar wale pre-filled answers ne 6/7 "
            "items hit kiye — root cause thoda generic tha "
            "\"resources hold kar raha\" bola, exact 'missing timeout' "
            "keyword nahi bola. Yeh realistic hai — first-pass "
            "hypothesis aksar directionally sahi hoti hai, exact "
            "nahi.)"
        )


# ─────────────────────────────────────────────────────────────────
# POST-MORTEM
# ─────────────────────────────────────────────────────────────────

MODEL_POSTMORTEM = """\
  Impact: /checkout error rate peaked at 34.2% for ~13 minutes
    (14:10-14:23 IST). Estimated ~$35,000-40,000 lost revenue
    (~$8,000/min x 34% x 13min). browse/search/cart unaffected.
    ~1,200 customers hit an error at checkout based on support
    ticket volume.

  Timeline: 14:00 order-service v2.14.0 deployed (adds loyalty
    points preview call, no timeout configured) -> 14:06 loyalty-
    service CPU alert fires (unrelated batch job — red herring)
    -> 14:10 checkout error rate crosses 6% -> 14:13 HikariPool-1
    exhausted, 503s begin -> 14:15 on-call paged -> 14:2x rollback
    to v2.13.x initiated -> error rate returns to baseline.

  Root cause: The new LoyaltyClient HTTP call added in v2.14.0 had
    no client-side timeout. When loyalty-service latency spiked
    (triggered by an unrelated scheduled batch job), checkout
    request threads held DB connections for up to 30s each while
    blocked on the loyalty call, exhausting order-service's
    connection pool and cascading into failures for unrelated DB
    queries in the same service.

  What went well: Error-rate alerting fired within ~4 minutes of
    degradation starting. Once triggered, rollback resolved the
    acute customer impact within ~10 minutes of paging. The
    dashboard's per-endpoint breakdown let responders quickly rule
    out a database outage.

  Action items:
    1. Add explicit connect+read timeouts and a circuit breaker to
       LoyaltyClient. Owner: platform team. Due: 1 week. P0.
    2. Require timeout config on all new outbound HTTP clients via
       code review checklist / lint rule. Owner: eng lead. Due:
       2 weeks. P1.
    3. Alert on DB connection pool utilization >80% (would have
       fired before the error-rate alert). Owner: SRE. Due: 1 week.
       P0.
    4. Move loyalty-points-batch-recalc to off-peak hours or an
       isolated resource pool. Owner: loyalty team. Due: 2 weeks.
       P2.
"""


def run_postmortem(auto_demo: bool) -> None:
    header("MOCK POST-MORTEM")
    print(
        "\nAb tum incident commander ho. 04_post_mortem_writing.md ka "
        "structure use karke ek CHOTA post-mortem likho — 5 bullets: "
        "Impact, Timeline, Root Cause, What Went Well, Action Items "
        "(owner + due + priority ke saath). Blameless language use "
        "karo (\"the deploy introduced...\", not \"X forgot...\")."
    )
    prompt(
        "Apna 5-bullet post-mortem likho (ek hi block me, ya line by "
        "line):",
        "postmortem", auto_demo,
    )

    subhead("Model post-mortem (for comparison)")
    print(f"\n{MODEL_POSTMORTEM}")

    print(
        "Compare karo: kya tumne dollar impact quantify kiya? Timeline "
        "me timestamps the? Root cause specific tha (not just \"bad "
        "deploy\")? Action items me owner + due date + priority the, "
        "ya vague (\"be more careful\") reh gaye?"
    )


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Incident triage simulation — read, diagnose, "
        "self-assess."
    )
    parser.add_argument(
        "--auto-demo",
        action="store_true",
        help="Run through with pre-filled example answers, no typing "
        "needed — useful to see the full flow or for a non-interactive "
        "sanity check.",
    )
    args = parser.parse_args()

    print_intro()
    print_timeline()
    run_triage(args.auto_demo)
    reveal(args.auto_demo)
    run_postmortem(args.auto_demo)

    header("DONE")
    print(
        "\nYeh skill code se nahi, reps se aati hai. Agla incident "
        "real ho ya simulated, wahi loop chalao: timeline padho, "
        "SEV assign karo, red herrings ko flag karo (dismiss mat "
        "karo, note karo), mitigate first phir investigate, aur "
        "post-mortem me specific + blameless raho.\n"
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Phir se try karo: python "
              "01_incident_triage_simulation.py --auto-demo")
        sys.exit(1)
