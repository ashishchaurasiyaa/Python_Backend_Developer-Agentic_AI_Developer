# 🗺️ ROADMAP — Din-ba-Din, Ek Line Pe Chalo

> **Ek hi niyam: jahan `- [ ]` mila, wahi aaj ka kaam hai. Khatam karke `- [x]` kar do. Bas.**
>
> Yeh file isliye hai taaki tumhe kabhi yeh na sochna pade "aaj kya karun". Har din ka kaam pehle se likha hai, exact file path ke saath. Koi choice nahi, koi confusion nahi.
>
> **Roz ka time: ~2.5 ghante** (2h main kaam + 20 min DSA + jo bacha).
> Kam time ho to sirf 🔴 wala karo, 🟡 skip kar do — par **order mat todo**.

---

## Pehle yeh 3 baatein (ek baar padho, phir bhool jao)

**1. Yeh repo padhne ke liye nahi hai — karne ke liye hai.**
1390+ .md files hain. Tumhe saari nahi padhni. Yeh roadmap sirf wahi 120-odd cheezein sequence karta hai jo interview + job ke liye zaroori hain. Baaki files **reference** hain — tab kholna jab lab me atko.

**2. Lab pehle, theory baad me.**
Purana tareeka: theory padho → lab karo. Isse boredom aata hai aur yaad nahi rehta. Yahan ulta hai: lab shuru karo → jahan atko wahi theory file kholo → wapas lab pe. Isse har theory ka **matlab** samajh aata hai.

**3. Har raat [MY_PROGRESS.md](MY_PROGRESS.md) me 3 line.**
Agar "Kiya" wali line khaali hai to us din progress zero tha — chahe kitna padha ho.

---

## 🚨 RUKO — interview N din me hai?

**Interview scheduled hai to yeh roadmap PAUSE karo.** Yeh 8-hafte ka skill-building sequence hai,
interview prep nahi. Interview ke 3-5 din pehle sequence chhodo, prep pe jao, phir wapas isi din pe aa jao.

| Interview | Kab | Kya kholo |
|---|---|---|
| 🔴 **GenAI Developer (Azure)** | **2026-08-11** | [Agentic_AI/Interview_Prep/05_genai_developer_azure_role_prep.md](Agentic_AI/Interview_Prep/05_genai_developer_azure_role_prep.md) — JD→repo gap map + day-wise plan |
| Koi bhi naya | — | [INTERVIEW_PREP_COMPANIES.md](INTERVIEW_PREP_COMPANIES.md) me add karo, phir uska prep doc banao |

**General interview-week formula** (roadmap ki jagah):
1. JD ke top-5 keywords nikalo → repo me unki files kholo (poora topic nahi, sirf 🔴 section)
2. Har topic **bolke** samjhao — 2 min, bina file dekhe. Atko to wahi padho.
3. [COMPULSORY_TOPICS.md](COMPULSORY_TOPICS.md) se apne tier-🔴 pe self-check
4. Ek DSA problem roz (streak) — [`harness.py`](Backend_Developer/03_Interview_AnyYear/01_DSA/practice/)
5. Interview ke baad: outcome [JOB_TRACKER.md](JOB_TRACKER.md) me likho, aur jo nahi aaya wo agla topic

---

## 🔁 Roz ka parallel track (har din, upar wale kaam ke saath)

Yeh 3 cheezein **kisi bhi din ke kaam ke saath** chalti hain — inka apna din nahi hota:

| Kya | Time | Kahan | Kyun roz |
|---|---|---|---|
| 🗣️ **English speaking** | 30 min | [english_speaking/README.md](english_speaking/README.md) | **Asli gap yahi hai.** Tech aata hai, bolna nahi aata — interview isi pe rukta hai. System-design drill *bolke* karo to dono ek saath ho jate hain. |
| 🧮 **DSA** | 20 min | [`01_DSA/practice/`](Backend_Developer/03_Interview_AnyYear/01_DSA/practice/) → `python harness.py` | Coding round pehla filter hai. Streak mat todo — 1 problem bhi chalega. |
| 💼 **Apply** | 15 min | [JOB_TRACKER.md](JOB_TRACKER.md) | Padhai khatam hone ka wait mat karo. Apply karte raho, jo reject hota hai wahi agla topic batata hai. |

---

# 🟢 WEEK 1 — Observability (resume ki sabse badi missing line)

**Kyun pehle:** tumhare resume pe Prometheus/Grafana hai hi nahi. Ek hafte me wo *kiya hua* ban jayega.

- [ ] **Day 1** 🔴 Setup + pehla lab
  `DevOps/11_Monitoring/practical/01_monitoring_lab.md` → **Lab 1** karo (Prometheus + Grafana + node_exporter khada karo)
  Time: 1.5h · Verify: `localhost:9090/targets` pe dono UP dikhein

- [ ] **Day 2** 🔴 Apni app instrument karo
  Same file → **Lab 2** (RED method — Toofan/Niroskos me `/metrics`, Counter + Histogram, p95 panel)
  Time: 2h · **Yeh sabse important lab hai poore hafte ka**

- [ ] **Day 3** 🔴 Alerts
  Same file → **Lab 3** (alert rule + Alertmanager routing)
  Atko to kholo: `DevOps/11_Monitoring/01_prometheus_grafana_alertmanager.md`

- [ ] **Day 4** 🔴 Debugging scenario
  Same file → **Lab 4** (cardinality explosion diagnose karo) + Self-Check Checklist
  Time: 1.5h

- [ ] **Day 5** 🔴 Logging stack
  `DevOps/12_Logging/practical/01_logging_lab.md` → **Lab 1 + 2** (Loki/Promtail, grok filter)

- [ ] **Day 6** 🟡 Logging deep
  Same file → **Lab 3 + 4** (LogQL, mehnga logging setup diagnose)

- [ ] **Day 7** 🔴 **Resume update karo**
  Skills me add: `Prometheus, Grafana, Loki, PromQL, RED method, p95 SLOs`
  Project bullet me add: *"instrumented X with RED metrics; p95 latency Y ms"*
  ✅ Week 1 done — pehli baar resume pe verified line aayi

---

# 🟢 WEEK 2 — Kubernetes (sabse badi skill gap)

- [ ] **Day 8** 🔴 Cluster khada karo + Deployments
  `DevOps/06_Kubernetes/practical/01_kubernetes_lab.md` → Prerequisites (minikube/kind) + **Lab 1**
- [ ] **Day 9** 🔴 Same file → **Lab 1 ke steps 5-6** (rolling update + broken image + rollback)
- [ ] **Day 10** 🔴 Same file → **Lab 2** (ConfigMaps, Secrets, StatefulSet)
- [ ] **Day 11** 🔴 Same file → **Lab 3** (Ingress + HPA + RBAC)
- [ ] **Day 12** 🔴 Same file → **Lab 4** (CrashLoopBackOff debug) + Self-Check
- [ ] **Day 13** 🟡 Autoscaling theory
  `DevOps/06_Kubernetes/06_cluster_autoscaling_karpenter.md` (HPA vs CA vs Karpenter)
- [ ] **Day 14** 🔴 **Resume update** — `Kubernetes (Deployments, Services, Ingress, HPA, RBAC), Helm`

---

# 🟢 WEEK 3 — Terraform + AWS (IaC proof)

- [ ] **Day 15** 🔴 `DevOps/08_Terraform/practical/01_terraform_lab.md` → **Lab 1** (S3 bucket provision)
- [ ] **Day 16** 🔴 Same file → **Lab 2** (variables, validation, outputs, workspaces)
- [ ] **Day 17** 🔴 Same file → **Lab 3** (module + remote state backend)
- [ ] **Day 18** 🔴 Same file → **Lab 4** (state drift detect + reconcile) + Self-Check
- [ ] **Day 19** 🔴 **AWS budget alert pehle set karo ($5)**, phir `DevOps/07_Cloud_AWS/practical/01_aws_lab.md` → **Lab 1** (IAM + S3)
      ⚠️ Har lab ke end me teardown step **chalao**
- [ ] **Day 20** 🔴 Same file → **Lab 2** (2-AZ VPC + subnets) — teardown mat bhoolna
- [ ] **Day 21** 🔴 **Resume update** — `Terraform (modules, remote state), AWS VPC/IAM/ASG`

---

# 🟢 WEEK 4 — Capstone Deploy (yahi M-2 hai — 3 roles unlock)

- [ ] **Day 22** 🔴 Plan likho: Toofan (ya Niroskos) ko deploy karna hai — architecture 1 page
      Reference: `Backend_Developer/01_Year3-4_Mid/04_DevOps/10_fastapi_production_deployment.md`
- [ ] **Day 23** 🔴 Dockerfile production-grade banao (multi-stage, non-root)
      `DevOps/05_Docker/practical/01_docker_lab.md` Lab 1 ka pattern use karo
- [ ] **Day 24** 🔴 K8s manifests likho (Deployment + Service + Ingress + ConfigMap/Secret)
- [ ] **Day 25** 🔴 Terraform se infra (EKS ya EC2+K8s, ya managed alternative)
- [ ] **Day 26** 🔴 Monitoring wire karo (Week 1 wala hi setup, ab deployed app pe)
- [ ] **Day 27** 🔴 **Eval harness + cost tracking** agent pe (Agentic role ke liye yahi missing tha)
      Reference: `Agentic_AI/Level6_Agent_Patterns/10_agent_evaluation.md` + `Agentic_AI/Level8_Production_LLMOps/10_cost_optimization_advanced.md`
- [ ] **Day 28** 🔴 **README likho + resume update + GitHub link**
      ✅ **M-2 complete** — roles 3/4/5 (Agentic, Platform, LLMOps) ab open

---

# 🟡 WEEK 5-6 — System Design (roz ek drill, BOLKE)

> Yahan se roz ka format: **1 drill (45 min, bolke) + 1 theory file + DSA**.
> Bolke karna = English practice bhi saath me. Voice memo record karo.

- [ ] **Day 29** Drill 1: URL Shortener → `Backend_Developer/02_Year5+_Senior/01_System_Design/PRACTICE_DRILLS.md` (Tier 1)
      Theory: `Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/01_Monolithic_vs_Microservices.md`
- [ ] **Day 30** Drill 2: Pastebin · Theory: `Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/04_Latency.md` + `05_Throughput.md`
- [ ] **Day 31** Drill 3: Rate Limiter (LLD) · Theory: `Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/06_Availability.md`
- [ ] **Day 32** Drill 4: Gaming Leaderboard · Theory: `Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/07_Consistency_Strong_vs_Eventual.md`
- [ ] **Day 33** Theory: `Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/08_CAP_Theorem.md` + Drill 1 **repeat** (score 15+ badhna chahiye)
- [ ] **Day 34** Theory: `Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/12_Load_Balancer.md` + `13_Caching_Complete.md`
- [ ] **Day 35** Theory: `Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/20_Database_Indexing.md` + `38_Database_Sharding.md`
- [ ] **Day 36** Drill 5: Twitter/X Feed (Tier 2) · Theory: `Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/31_Back_of_Envelope_Estimation.md`
- [ ] **Day 37** Drill 6: WhatsApp Chat · Theory: `Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/44_Consistent_Hashing_Theory.md`
- [ ] **Day 38** Drill 7: Uber/Ride Matching · Theory: `Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/43_Geohashing.md`
- [ ] **Day 39** Drill 8: BookMyShow · Theory: `Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/59_Saga_Pattern.md`
- [ ] **Day 40** Theory: `Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/51_Idempotency_Tokens.md` + `65_Dead_Letter_Queue.md`
- [ ] **Day 41** Drill 12: **RAG/LLM Backend** (tumhara differentiator — 2 baar karo)
- [ ] **Day 42** Gap log padho → jo cheez baar-baar miss hui, wo 3 drills me sudhaaro

---

# 🟡 WEEK 7 — Messaging + Data (jo JD me maange, wahi deep)

- [ ] **Day 43** `Backend_Developer/01_Year3-4_Mid/07_Kafka/labs/README.md` → setup + **Lab 1, 2**
- [ ] **Day 44** Kafka labs → **Lab 3, 4** (ordering, manual commit redelivery)
- [ ] **Day 45** Kafka labs → **Lab 5** (consumer lag) + `08_ordering_guarantees.md`
- [ ] **Day 46** `Backend_Developer/01_Year3-4_Mid/09_Celery/labs/README.md` → **Lab 1, 2** (states, retries)
- [ ] **Day 47** Celery labs → **Lab 3, 4** (routing/canvas, acks_late crash)
- [ ] **Day 48** `Backend_Developer/00_Year0-2_Junior/04_Database_SQL/07_postgresql_internals.md` (MVCC/WAL/VACUUM)
- [ ] **Day 49** `Backend_Developer/00_Year0-2_Junior/04_Database_SQL/21_isolation_levels_anomalies.md` + `13_postgresql_performance_tuning.md`

---

# 🟡 WEEK 8 — Interview Polish

- [ ] **Day 50** `Backend_Developer/03_Interview_AnyYear/02_Interview_Prep/05_backend_system_design_50q.md`
- [ ] **Day 51** `Backend_Developer/03_Interview_AnyYear/02_Interview_Prep/07_python_tricky_questions.md` + `08_sql_interview_questions.md`
- [ ] **Day 52** `Backend_Developer/03_Interview_AnyYear/02_Interview_Prep/09_debugging_scenarios.md`
- [ ] **Day 53** `Backend_Developer/03_Interview_AnyYear/02_Interview_Prep/11_resume_walkthrough_prep.md` — **apna resume bolke walk karo, record karo**
- [ ] **Day 54** `Backend_Developer/03_Interview_AnyYear/02_Interview_Prep/10_behavioral_backend.md` — STAR format me 5 kahaniyan likho
- [ ] **Day 55** `Backend_Developer/03_Interview_AnyYear/02_Interview_Prep/12_negotiation_offer.md`
- [ ] **Day 56** `Agentic_AI/Interview_Prep/01_system_design_ai_questions.md` — AI-role wale sawaal
      ✅ **Interview-ready**. Ab apply karna shuru karo (agar pehle nahi kiya).

---

# ⏱️ Roz ka parallel track (Day 1 se hi shuru, 20 min)

- [ ] DSA: `cd Backend_Developer/03_Interview_AnyYear/01_DSA/practice && python3 harness.py`
      Roz **1 problem**, order me. 35 problems = 35 din. Week 5-6 tak khatam ho jayenge.
      Target: Day 35 tak 35/35 attempted, Day 49 tak 35/35 passing.

---

# 🔵 Week 8 ke baad — role ke hisaab se (yahan pehli baar choice hai)

Tab tak tumhe pata hoga kis role pe interviews aa rahe hain:

| Agar target hai | To ab yeh |
|---|---|
| **Senior Backend** | `Backend_Developer/01_Year3-4_Mid/05_Microservices/` (poora) + `Backend_Developer/01_Year3-4_Mid/15_Design_Patterns_SOLID/Section_10_Interview_Drills/` |
| **GenAI/Agentic** | `Agentic_AI/Level6_Agent_Patterns/` (11 docs) + `Agentic_AI/Level8_Production_LLMOps/` |
| **Platform/LLMOps** | `DevOps/` ke bache hue phases (Ansible, CI/CD, Security) + `Agentic_AI/Modern_Topics/23_claude_agent_sdk_skills.md` |
| **Koi bhi** | `Agentic_AI/Modern_Topics/23_claude_agent_sdk_skills.md` + `24_openai_agentkit.md` (Claude Agent SDK, AgentKit — 2026 ka hot topic) |

---

## Agar kabhi confuse ho jao

1. Yeh file kholo → sabse pehla `- [ ]` dhundo → wahi aaj ka kaam hai
2. Lab me atko → us phase ki theory file kholo (har lab me link hai)
3. Kuch samajh na aaye → mujhse poocho, poora context yahan hai

**Jo file is roadmap me nahi hai, wo abhi tumhare liye zaroori nahi hai.** Reference ke liye hai, padhne ke liye nahi.

---

**Related:** [MY_PROGRESS.md](MY_PROGRESS.md) (roz 3 line) · [STUDY_PLAN.md](STUDY_PLAN.md) (topic-wise view) · [DAILY_PLAN_90_DAYS.md](DAILY_PLAN_90_DAYS.md) (job-hunt track)
