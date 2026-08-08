# Engineering Practices Labs — Written-Scenario Simulations

> `../` me theory files hain (WHAT/WHY/HOW, Hinglish, no code — *by design*, since these are process/judgment skills, not code skills). Yeh folder unhe **practice** karne ke liye hai. Par format Kafka/RabbitMQ/Celery labs se alag hai — jaan-bujh kar.

## Yeh format alag kyun hai

Kafka labs me code hai: TODO bharo, `python 0N_*.py` chalao, script khud `✅`/`❌` bata deti hai. Yeh possible hai kyunki "naya consumer group `earliest` se padhega ya nahi" ek **deterministic, checkable fact** hai.

Incident triage aisa nahi hai. "Sahi SEV level kya hai", "root cause kya hai" — yeh **judgment calls** hain jahan senior engineers tak disagree kar sakte hain. Isko `assert` se grade nahi kiya ja sakta, aur agar koi script tumhe "✅ PASS" bol de to woh false confidence hai — asli on-call me koi script tumhe nahi bataega ki tumhara SEV assessment sahi tha.

Isliye yeh labs **written-scenario simulations** hain:

1. Realistic incident data dikhta hai — Slack alert channel + log tail + metrics dashboard, bilkul jaisa on-call engineer dekhta hai (kuch signal hai, kuch noise hai, tumhe khud filter karna hai).
2. Tumse triage poocha jaata hai (SEV, root cause, mitigation, rollback y/n) — free text `input()`, apna judgment use karo.
3. Model answer + rubric reveal hota hai (real root cause, red herring ka explanation, correct SEV + reasoning).
4. **Self-assessment, auto-grading nahi** — checklist milta hai, tum khud apne answer ko honestly compare karte ho. Yehi "SOCH" reflection spirit hai jo Kafka labs ke end me hoti hai, bas yahan poora lab hi reflection-based hai.
5. End me mock post-mortem likhne ka practice — apna 5-bullet post-mortem likho, phir model post-mortem se compare karo.

## Kya banata hai

- **On-call diagnostic instinct**: buried signal ko red herring se alag pehchanna, timeline se causal order banana, "deploy broke it" jaisi surface-level explanation se aage jaana.
- **Post-mortem writing muscle**: impact quantify karna, blameless language, specific action items (owner + due + priority).

Dono skills `../03_incident_response_runbooks.md` aur `../04_post_mortem_writing.md` ke framework use karte hain (severity decision tree, 5 Whys, mitigate-first-investigate-after, blameless template) — theory pehle padho, phir lab karo.

## Labs

| # | Lab | Scenario | Failure mode |
|---|---|---|---|
| 1 | [01_incident_triage_simulation](01_incident_triage_simulation.py) | Checkout error rate spikes after a deploy | Cascading DB connection pool exhaustion from a missing timeout on a new downstream call — with an unrelated CPU alert as red herring |

## Kaise chalao

```bash
cd Backend_Developer/01_Year3-4_Mid/14_Engineering_Practices/labs

# Interactive — apne answers type karo
python 01_incident_triage_simulation.py

# Auto-demo — pre-filled example answers ke saath poora flow dekho,
# koi typing nahi chahiye (verification / walkthrough ke liye)
python 01_incident_triage_simulation.py --auto-demo
```

## Protocol

```
1. Timeline padho (Slack + logs + dashboard) — jaldi mat karo, jaisa
   real on-call me karoge
2. 4 triage questions ka jawab do (SEV, root cause, mitigation, rollback)
   — reasoning likho, sirf answer nahi
3. Reveal padho — apna answer checklist se compare karo, honestly
4. Mock post-mortem likho, model se compare karo
```

## Troubleshooting

| Problem | Fix |
|---|---|
| Script hang ho gaya interactive mode me | Har `input()` ek line expect karta hai — Enter dabao submit karne ke liye |
| Sirf flow dekhna hai, type nahi karna | `--auto-demo` use karo |
| Unicode/emoji terminal me tootey dikh rahe | Terminal encoding UTF-8 set karo, ya emoji ignore karke text padho |

---

**Related:** [theory files](../) · [Kafka labs](../../07_Kafka/labs/) (automated-verification format, for comparison) · [Celery labs](../../09_Celery/labs/)
