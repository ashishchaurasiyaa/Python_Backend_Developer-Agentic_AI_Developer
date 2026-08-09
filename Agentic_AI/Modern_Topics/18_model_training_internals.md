# Model Training Internals — RLHF/PPO/DPO → GRPO/RFT, Distillation, Validation Loss, Test-Time Compute

**Agentic AI · Modern Topics | Senior AI Engineer**

> "Must Know AI Terms" image ke 3 training-side terms jo repo me thin the. Tum **consume-side** engineer ho (models train nahi karte), isliye yeh **interview-answer depth** par hai — concept + one-liner, full lab nahi.

---

## 1. Reinforcement Learning (RLHF / PPO / DPO)

```
 Base LLM ─► SFT (supervised) ─► Reward Model ─► RL optimize ─► Aligned LLM
                                  (human prefs)   (PPO / DPO)
```

- **RLHF** (Reinforcement Learning from Human Feedback): humans outputs rank karte hain → reward model train hota hai → policy us reward par optimize
- **PPO** (Proximal Policy Optimization): classic RL algo — reward maximize + **KL penalty** (base se zyada na bhatke); heavy, unstable, 2 models memory me
- **DPO** (Direct Preference Optimization): reward model **skip**; preference pairs (chosen vs rejected) par **directly** optimize — simpler, stable, aaj ka default
- **RL is how reasoning models get sharper** (image point) — trial → reward → repeat

**One-liner:** "RLHF aligns behaviour to human preference; PPO is the older RL optimizer, DPO is the simpler modern replacement that skips the reward model."

---

## 2. Distillation

```
 Teacher (large) ──soft outputs/logits──► Student (small) trains to mimic
        │                                        │
   90-95% quality                        fraction of size / cost / latency
```

- Student ko teacher ke **soft probabilities (logits)** par train karo, sirf hard labels par nahi — teacher ki "knowledge" transfer hoti hai
- **Types:** response-based (final outputs), feature-based (hidden states), on-policy (student generates, teacher grades)
- **Why (image point):** "Faster, cheaper, nearly as good. Likely how GPT-4 Turbo / small models built."

**One-liner:** "Distillation compresses a big model's behaviour into a small, cheap, fast one by training on its soft outputs."

---

## 3. Validation Loss / Overfitting

```
loss
 │  train ↓↓↓↓
 │  val   ↓ ... then ↑     ◄── gap widens = OVERFITTING (memorizing, not learning)
 │        └── early-stop at the val minimum
 └──────────────────────────► epochs
```

- **Train loss** = model apne dekhe data par kitna galat; **Validation loss** = held-out (unseen) data par
- **Train ↓ but Val ↑** = overfitting (data ratt raha hai, seekh nahi raha)
- **Fixes:** early stopping, regularization (dropout/weight-decay), more/augmented data
- **Why (image point):** "Lower = better. Catches overfitting before it's too late."

**One-liner:** "Validation loss on held-out data is the honest signal; train loss can lie because the model may just be memorizing."

---

## Part 2 — The Post-2024 Training Era (GRPO · RFT · Test-Time Compute)

> Upar ke 3 terms **2022–23 ki alignment duniya** hain (RLHF → DPO): "model ko insaan ki taste par align karo". 2024–25 me sawaal badal gaya: "model ko **sahi** kaise banayein, sirf pasand-aane-layak nahi?" — aur wahin se **reasoning models** (o1/o3, DeepSeek-R1) aaye. Yeh Part 2 wahi delta cover karta hai. Tone same: concept-level, no heavy math.

### Quick reference — 4 optimizers, ek table

| | PPO (2022) | DPO (2023) | GRPO (2024) | RFT / RLVR (2024–25) |
|---|---|---|---|---|
| Reward kahan se | learned reward model | koi nahi — preference pairs directly | reward model **ya** verifier | **verifier / grader** (rule, unit test, exact-match) |
| Critic (value net) chahiye? | **Haan** (policy-sized extra model) | N/A (RL hi nahi) | **Nahi** — group mean hi baseline | Nahi (GRPO/variant hi chalta hai andar) |
| Online ya offline | online (model khud generate karta hai) | **offline** (fixed dataset) | online | online |
| Models in memory | ~4 (policy, ref, reward, critic) | 2 (policy, ref) | ~3 (policy, ref, reward/verifier) | ~2–3 (verifier free hai) |
| Kya sikhata hai | "aisa bol" (taste) | "aisa bol" (taste) | "aisa bol" **+** "aisa soch" | **"sahi jawab nikaal"** |
| Reward hacking risk | high (RM gameable) | N/A | RM use karo to high | **low** — unit test ko meetha nahi bola ja sakta |
| Kaun use karta hai | InstructGPT-era | Llama-3/Tulu-era post-training | DeepSeek-R1, Qwen reasoning | o-series, R1 stage-3, OpenAI RFT API |

**Ek line me evolution:** *DPO ne reward model maara → GRPO ne critic maara → RLVR ne reward model ki **judgement** hi hata di (verifier laga diya).*

---

## 4. GRPO — Group Relative Policy Optimization

**WHAT:** PPO ka sasta cousin. Advantage nikaalne ke liye **critic (value network) hataa do**; uski jagah **same prompt ke G answers ka group average** baseline bana do.

```
 PPO                                     GRPO
 ┌──────────┐   ┌───────────┐            ┌──────────┐  sample G answers for
 │  policy  │   │  CRITIC   │◄─ EXTRA    │  policy  │──  the SAME prompt ──┐
 └────┬─────┘   │  (value)  │   model,   └────┬─────┘                      │
      │         └─────┬─────┘   ~policy       │                            │
      │  advantage =  │         sized         │   r₁ r₂ r₃ … r_G  ◄────────┘
      └──►  r − V(s) ◄┘                       │        │
                                              └─► Aᵢ = (rᵢ − mean(r)) / std(r)
 4 models in GPU memory:                 3 models in GPU memory:
 policy + ref + reward + CRITIC          policy + ref + reward(or verifier)
```

### Intuition — group sampling + relative reward

Critic ka kaam tha: *"is state par expected score kitna hoga?"* — yaani **par score** predict karna, taaki pata chale ki actual reward achha tha ya bura. GRPO kehta hai: predict karne ki zarurat kya hai, **8 baar attempt kar lo aur class-average hi par maan lo**.

```
prompt: "solve 17 × 23"
 ├─ rollout 1 → 391 ✓  r = 1
 ├─ rollout 2 → 391 ✓  r = 1          group mean = 0.75
 ├─ rollout 3 → 380 ✗  r = 0          above mean → logprob PUSH UP  ▲
 └─ rollout 4 → 391 ✓  r = 1          below mean → logprob PUSH DOWN ▼

 saare 4 sahi   → mean=1, spread=0 → advantage ≈ 0 → NO gradient  (bahut easy)
 saare 4 galat  → mean=0, spread=0 → advantage ≈ 0 → NO gradient  (bahut hard)
 mixed          → strongest signal              ◄── FREE CURRICULUM
```

Yeh last wala point interview me sona hai: GRPO **khud-b-khud curriculum filter** karta hai. Jo problems model already solve kar leta hai ya bilkul nahi kar paata, unse gradient hi nahi aata — training automatically **frontier problems** par focus ho jaati hai.

Baaki structure PPO jaisa hi hai — clipped surrogate objective (policy ek step me zyada na hile) + **KL penalty reference model ke against** (base se bhatakna mana). Sirf advantage estimation badla hai.

### Why DeepSeek-R1 chose GRPO

1. **Memory:** critic policy jitna hi bada hota hai. 70B policy ke saath 70B critic = training feasible hi nahi. Critic hata do → almost aadha memory footprint bach gaya, aur wo memory long rollouts (10k+ thinking tokens) me chali gayi.
2. **Stability:** critic ko bhi train karna padta hai. LLM me reward **sequence-end par sparse** hota hai, to per-token value estimate seekhna hi khud ek unstable problem hai. Ek poora failure mode delete ho gaya.
3. **Reward sasta tha:** math/code me reward ek **rule** hai (jawab sahi hai ya nahi) — sampling ki 8x cost afford ho gayi, kyunki grading free hai. Agar reward ke liye har rollout par ek reward-model forward pass lagta, 8x sampling itna sasta na hota.
4. **R1-Zero experiment:** DeepSeek ne base model par **bina kisi SFT ke** seedha GRPO chalaya — aur long chain-of-thought, self-verification, "wait, let me re-check" wala behaviour **emerge** kar gaya. Wo demo hi thi ki simple outcome reward + affordable RL = reasoning. (Trade-off: R1-Zero ka output language-mixed aur unreadable tha — isiliye final R1 me cold-start SFT laga.)

> **Senior Tip:** GRPO ko "PPO minus critic" bolo, "naya RL algorithm" mat bolo. Interviewer usually yahi check karta hai ki tumhe pata hai **critic kis kaam ka tha** (variance-reduction baseline) aur group mean usko kaise replace karta hai.

> **Interview Angle — known warts (bonus points):** group ke saare rewards same ho to advantage 0 → wo poori sampling compute waste. Std-normalization aur length-normalization me subtle bias hai (chhote galat answers ko unfair boost). Isiliye follow-ups aaye — Dr. GRPO, DAPO, GSPO. Naam bhar bol dena kaafi hai, defend karne ki zarurat nahi.

**One-liner:** "GRPO is PPO with the critic deleted — it samples a group of answers per prompt and uses the group's mean reward as the baseline, so advantage is just 'how much better than your siblings you were'. That halves the memory and is why DeepSeek could run RL at R1 scale."

---

## 5. RFT / RLVR — Reasoning Models Kaise Train Hote Hain

**WHAT:** RL, but reward ek **learned model** nahi — ek **verifier/grader** hai. Naam: **RLVR** = Reinforcement Learning with *Verifiable* Rewards. Product form (OpenAI): **RFT** = Reinforcement Fine-Tuning.

```
 ┌──── VERIFIER / GRADER (deterministic, sasta, hack-proof) ────────┐
 │  math   → final answer == ground truth (exact / symbolic match)  │
 │  code   → unit tests pass? compiler exit code? runtime limit?    │
 │  format → <think>…</think> present? JSON schema valid?           │
 │  logic  → puzzle constraint satisfied?                           │
 └────────────────────────────┬─────────────────────────────────────┘
                              │  reward = 0 / 1   (NO reward model)
  prompt ─► policy generates long CoT ─► grader ─► GRPO update ─► repeat
```

### Why verifiable rewards changed everything

Learned reward model ka fundamental problem: wo bhi ek model hai, to **hack ho sakta hai**. RL zyada steps chalao to policy aise outputs dhoondh legi jo RM ko khush karte hain par actually bakwaas hain (confident tone, lambe answers, flattery). Isiliye classic RLHF ko **jaldi rok dena padta tha** — thoda optimize karo, KL leash kaso, bas.

Verifier ko meethi baatein nahi ki ja sakti. Unit test pass hai ya nahi. Isliye tum RL ko **bahut zyada steps** chala sakte ho — aur wahin par model ke paas time hota hai lamba sochna, backtrack karna, khud ko verify karna **seekhne** ka. **Reasoning models isi headroom ka product hain.**

**Cost:** yeh sirf un domains me chalta hai jahan sahi/galat **automatically** decide ho sake — math, code, structured extraction, tool-call correctness. "Ek achhi poem likho" verifiable nahi hai; wahan aaj bhi DPO/RLHF hi chalta hai. Isiliye modern post-training **hybrid** hai: verifiable domains me RLVR + subjective domains me preference-based.

### Rejection sampling + SFT loop (STaR / expert iteration)

Sabse sasta "RL without RL" — aur R1 pipeline ka literal stage:

```
repeat:
   har prompt ke liye N = 8…64 completions sample karo
   sirf wahi rakho jinhe VERIFIER ne CORRECT bola     ◄── rejection sampling
   dedupe + gande (mixed-language, unreadable) traces drop karo
   in survivors par plain SFT karo                    ◄── ab yeh normal fine-tune hai
   improved model se dobara sample karo               ◄── expert iteration
```

Kyun kaam karta hai: model already sahi answer *kabhi-kabhi* nikaal leta hai (N me se 3 baar). Tum bas usi ki apni **best behaviour ko uske hi upar SFT** kar dete ho — probability mass sahi trajectories par shift ho jaata hai. Koi RL infra nahi chahiye, sirf sampling + SFT.

> **Senior Tip:** Rejection-sampling + SFT aur **distillation (Section 2)** ka rishta bata dena — same machinery hai, bas teacher kaun hai wo badalta hai. Apne aap se sample karo = self-improvement; bade RL'd model se sample karo = distillation (R1 ne exactly yehi kiya — R1 se ~800k traces bana kar chhote Qwen/Llama models ko SFT kiya, aur wo "R1-distill" models bina kisi RL ke reasoning karne lage).

### Process vs Outcome reward models (PRM vs ORM)

| | **ORM** (Outcome RM) | **PRM** (Process RM) |
|---|---|---|
| Score kis par | sirf **final answer** | **har reasoning step** par |
| Signal | sparse (ek scalar, poore rollout ke liye) | dense (per-step) |
| Labels | sasta — bas answer check karo | mehnga — human step-annotation ya Monte-Carlo rollouts se auto-label |
| Failure mode | **lucky guess** — galat reasoning, sahi answer, phir bhi reward | **hackable + "step" define karna hi fuzzy** hai |
| Aaj ki reality | RL training ka **default** (rule-based outcome reward) | training reward ke roop me largely chhod diya gaya |

**Verdict jo bolna hai:** PRM idea theoretically better hai (credit assignment dense ho jaata hai — pata chalta hai *kahan* galti hui, sirf *ki* galti hui nahi). Practice me DeepSeek ne report kiya ki scale par PRM se reward hacking hota hai aur continuous re-annotation mehnga hai — to unhone **simple rule-based outcome rewards** choose kiye. PRM aaj bhi zinda hai, par mostly **inference-time verifier/reranker** ke roop me: best-of-N generate karo, PRM se score karo, best chuno.

### RFT as a product (consume-side me tumhare liye yahi relevant hai)

SFT vs RFT ka farq interview me poochha jaata hai:

- **SFT** = "aise likho" — style, format, tone, domain vocabulary copy karta hai. Chahiye: input→output pairs. Model ko *naya* problem-solving nahi sikhata.
- **RFT** = "sahi nikaalo" — tum grader dete ho, model apne answers explore karta hai aur jo grader ko pass karte hain unki taraf shift hota hai. Chahiye: prompts + **grader** (string-match / model-grader / python grader). Bahut chhote datasets (dozens–low thousands) par bhi kaam karta hai, kyunki signal per-example nahi, **per-attempt** aata hai.

**Rule of thumb:** *"Agar main ek script likh kar bata sakta hoon ki output sahi hai ya nahi — RFT candidate hai. Agar nahi likh sakta — prompt engineering + evals hi karo."*

**One-liner:** "RLVR replaces the learned reward model with a grader — unit tests, exact-match, schema checks — so the reward can't be hacked; that's what lets you run RL long enough for long chain-of-thought to emerge. RFT is that packaged as an API: you bring prompts plus a grader, not labelled answers."

---

## 6. Test-Time Compute Scaling

**WHAT:** Quality ka ek **naya axis** — weights same, par model inference par zyada tokens "soch" kar accuracy badha leta hai.

```
 accuracy
   │                          ┌── TEST-TIME scaling (thinking tokens ↑)
   │                     ┌────┘        SAME weights, more tokens,
   │             ┌───────┘             cost = PER REQUEST, forever
   │      ┌──────┘
   │  ┌───┘   ◄── PRE-TRAINING scaling (params + data ↑)
   │  │            cost = ONE TIME, amortized over all requests
   └──┴─────────────────────────────────────────► log(compute)
```

### Yeh training/inference tradeoff kyun badal deta hai

Purana model: capability **training me kharidte** the (bada pretrain), inference cost fix tha. Naya model: capability **runtime par bhi kharid sakte ho**. Iske do bade consequences:

- **Economics palat gayi.** Chhota model + lamba thinking, ek bade model ke single-shot se reasoning tasks par jeet sakta hai. Par pretraining ek baar ka kharcha hai jo har request par amortize hota hai; thinking tokens **har request par dobara** lagte hain. To "sasta model + zyada sochna" high-QPS product me mehnga pad sakta hai — yeh decision ab **per-feature** hai, per-model nahi.
- **Training infra ka bottleneck shift ho gaya.** RL me ab har rollout hazaaron tokens ka hai — training time **generation (rollout)** me jaata hai, gradient step me nahi. Isiliye modern RL stacks (vLLM-style fast samplers + trainer) generation ko first-class citizen treat karte hain. Yeh direct link hai Section 4 se: critic hataana sirf memory bachane ke liye nahi tha — wo memory **lambe rollouts** ko chahiye thi.

### Do flavours

```
 SEQUENTIAL (ek hi stream me lamba socho)      PARALLEL (kai attempts, phir chuno)
 ├─ long CoT                                    ├─ best-of-N sampling
 ├─ self-correction / backtracking              ├─ self-consistency (majority vote)
 └─ "wait, let me re-check"                     └─ tree/beam search over steps
    → model khud ko theek karta hai                → VERIFIER chahiye chunne ke liye
                                                     (yahan PRM wapas kaam aata hai)
```

### Budget forcing

Sabse saaf demo ki "thinking length ek **dial** hai": decoding par intervene karo.

```
 socha bahut zyada? → force-inject "</think>\n\nFinal Answer:"   → thinking CAP
 socha bahut kam?   → "</think>" ko SUPPRESS karo + "Wait" append → thinking EXTEND
                       └─► aksar model apni hi galti pakad leta hai aur sudhaar deta hai
```

Bas ek token ki jugaad se accuracy-vs-tokens curve upar chadhti hai. Yeh idea aaj products me **`reasoning_effort` / thinking-budget** knob ban chuka hai — low/medium/high ya explicit token budget.

> **Senior Tip — overthinking real hai.** Zyada thinking monotonically better *nahi* hai. Easy prompts par reasoning models loop karte hain, khud ko second-guess karte hain, latency aur cost jala dete hain, aur kabhi-kabhi sahi answer se hat jaate hain. Production me **task ke hisaab se budget route karo** — simple classification par low effort, hard debugging par high.

> **Interview Angle — consume-side gotchas:** (1) thinking tokens tumhe **bill hote hain** even though aksar dikhte nahi — cost model me include karo; (2) reasoning traces generally **reusable/cacheable nahi** hote turn ke baar; (3) latency p99 blow up karta hai kyunki thinking length input-dependent hai — timeouts aur streaming UX pehle se plan karo; (4) reasoning models ko chhote CoT prompts ("think step by step") ki zarurat nahi — wo already andar kar rahe hain, aur over-prompting ulta nuksaan karta hai.

**One-liner:** "Test-time compute is a second scaling axis: same weights, more thinking tokens, more accuracy. It moves cost from one-time training to per-request inference — so 'how long should it think' becomes a product decision, and budget forcing / reasoning_effort is the dial."

---

## 7. Interview Answer — "How are reasoning models trained now?"

Yeh 60–90 second ka narrative hai. RLHF → DPO → GRPO → RFT ko **ek kahani** ki tarah bolo, alag-alag facts ki tarah nahi.

```
2022  RLHF + PPO   humans rank → reward model → PPO with KL leash
                   problem: 4 models in memory, unstable, RM hackable
                        │
2023  DPO          reward model DELETE — preference pairs par direct loss
                   simple + stable, par OFFLINE hai: sirf collected pairs jitna
                   hi seekh sakta hai, naya behaviour discover nahi karta
                        │
2024  GRPO         wapas online RL, par ab CRITIC delete — group mean = baseline
                   RL affordable ho gaya → lambe rollouts possible
                        │
2024  RLVR / RFT   reward model ki jagah VERIFIER (unit test, exact match)
 –25               reward ab hack-proof → RL bahut lamba chala sakte ho
                   → long CoT, self-verification, backtracking EMERGE karte hain
                        │
      Distillation bade reasoning model se traces → chhote models par SFT
      + Test-time  → sasta reasoning; aur deploy par thinking-budget knob
```

**Bolne wala version:**

> "Alignment RLHF se shuru hua — reward model on human rankings, phir PPO with a KL penalty. Wo mehnga tha: policy, reference, reward model aur ek critic, chaaron memory me. DPO ne reward model hata diya aur preference pairs par direct optimize kar diya — sasta aur stable, par offline, to wo sirf taste sikha sakta hai, nayi capability discover nahi kar sakta.
>
> Reasoning models ke liye do cheezein badalni padi. Pehla, RL ko dobara affordable banana: GRPO ne **critic** hataya — ek prompt ke liye answers ka group sample karo aur group ka mean hi baseline maan lo, advantage bas 'apne siblings se kitna behtar' ho gaya. Isse memory aadhi bachi jo hazaaron-token wale rollouts me lagi. Dusra, reward ko hack-proof banana: verifiable domains me reward model ki jagah **grader** aa gaya — math me answer match, code me unit test. Learned RM ko lamba optimize karo to policy usko game kar deti hai; unit test ko game nahi kar sakte. Isi headroom me RL itna lamba chala ki long chain-of-thought, self-checking aur backtracking khud emerge kar gaye — DeepSeek ne R1-Zero me dikhaya ki bina kisi SFT ke bhi yeh ho jaata hai.
>
> Practical pipeline usually staged hoti hai: thoda cold-start SFT readability ke liye, phir verifiable rewards par GRPO, phir us RL checkpoint se **rejection sampling** kar ke sirf verified-correct traces uthao aur unpar SFT karo, phir general helpfulness/safety ke liye ek final preference round. Uske baad **distillation** — bada model traces likhta hai, chhote models unpar SFT hote hain, aur wo bina RL ke reasoning kar lete hain. Aur deploy par **test-time compute** ek dial ban gaya hai: same weights, thinking budget badhao to accuracy badhti hai — to 'kitna sochna hai' ab ek product decision hai."

**Agar 20 second hi mile:**

> "DPO killed the reward model, GRPO killed the critic, and verifiable rewards killed the reward model's *judgement* — replaced it with a grader. Reward hack-proof hone ki wajah se RL bahut lamba chal saka, aur usi headroom me long chain-of-thought emerge kiya. Phir distillation se wo capability chhote models me chali gayi, aur test-time compute deploy-side ka knob ban gaya."

**Follow-ups jo aksar aate hain — 1-line answers:**

- *"GRPO me critic ki jagah kya hai?"* → Group ka mean reward; advantage = (r − mean)/std over G samples of the same prompt.
- *"DPO kyun kaafi nahi tha reasoning ke liye?"* → Offline hai — jo pairs collect kiye unse aage nahi ja sakta; reasoning ko **exploration** chahiye tha.
- *"PRM ya ORM?"* → Training reward ke liye ORM/rule-based (PRM scale par hack hota hai aur labels mehnge); PRM inference-time reranker ke roop me useful.
- *"Har domain me RLVR chalega?"* → Nahi — sirf jahan grader likha ja sake. Subjective domains me abhi bhi preference-based (DPO) chalta hai; real systems hybrid hote hain.
- *"Tum consume-side ho, tumhare liye iska matlab?"* → Grader likh sakte ho to RFT; nahi to prompt + evals. Aur reasoning models ka cost/latency model alag hai — thinking tokens bill hote hain, cache nahi hote, budget route karna padta hai.

---

## Interview Q&A

**Q1. GRPO PPO se sasta kyun hai — exactly kya bachta hai?**
Critic network. PPO me value model roughly policy jitna hi bada hota hai aur usko bhi train karna padta hai — memory + optimizer states + ek aur unstable training loop. GRPO advantage ko group statistics se estimate karta hai (same prompt ke G rollouts ka mean/std), to critic ki zarurat hi nahi. ~4 models se ~3 par aa jaate ho, aur bachi hui memory lambe rollouts me lagti hai — jo reasoning training ke liye essential thi.

**Q2. Agar group ke saare answers sahi ya saare galat ho to?**
Advantage ≈ 0, to koi gradient nahi. Yeh waste bhi hai aur feature bhi — effectively **free curriculum learning** ho jaati hai: training automatically un problems par focus karti hai jo model ke "frontier" par hain (kabhi solve hote hain, kabhi nahi). Practical systems isi wajah se prompts ko difficulty ke hisaab se filter/re-sample karte hain taaki degenerate groups par compute na jale.

**Q3. RLVR aur classic RLHF me core difference kya hai?**
Reward ka source. RLHF me reward ek **learned model** hai jo human preferences approximate karta hai — approximate hone ki wajah se gameable hai, isiliye KL leash kasni padti hai aur jaldi rukna padta hai. RLVR me reward ek **deterministic verifier** hai (unit test, exact-match, schema check) — unhackable, isiliye RL ko bahut zyada steps chalaya ja sakta hai. Wahi extra optimization budget reasoning behaviour ko emerge karata hai. Trade-off: RLVR sirf verifiable domains me chalta hai.

**Q4. Rejection sampling + SFT ko RL kyun kehte hain jab wo sirf SFT hai?**
Kyunki signal reward se aa raha hai, labels se nahi. Model apne aap se sample karta hai, verifier filter karta hai, aur surviving trajectories par SFT hota hai — effect wahi hai jo policy-gradient ka: sahi trajectories ki probability badhti hai. Ise expert iteration / STaR bolte hain. Bas gradient estimator crude hai (binary keep/drop) aur negative examples se kuch nahi seekhta — isiliye proper RL se generally weaker hai, par infra bahut simple hai.

**Q5. PRM vs ORM — production me kaunsa lagaoge?**
Training reward ke liye ORM/rule-based, kyunki labels sasta hain aur PRM scale par hack ho jaata hai (aur "step" ki definition hi fuzzy hai). PRM ka best use **inference-time** hai: best-of-N generate karo, PRM se har candidate ko score karo, top chuno — yahan hacking risk nahi hai kyunki policy PRM ke against optimize nahi ho rahi, sirf select ho rahi hai.

**Q6. Test-time compute scaling ne training economics kaise badli?**
Do tarah se. Product side: capability ab runtime par bhi kharidi ja sakti hai, to "bada model" vs "chhota model jo zyada soche" ek real trade-off ban gaya — par test-time cost **har request par** lagta hai jabki training cost amortize hota hai, to high-QPS features me lamba thinking mehnga pad sakta hai. Training side: RL ka bottleneck gradient compute se **rollout generation** par shift ho gaya, kyunki har sample ab hazaaron tokens ka hai — isiliye modern RL stacks fast inference engines ke around design hote hain.

**Q7. Budget forcing kya hai aur kyun kaam karta hai?**
Decoding-time intervention jo thinking length control karta hai: cap karna ho to end-of-thinking token force-inject kar do; extend karna ho to end token suppress kar ke "Wait" append kar do — model aage sochta rehta hai aur aksar apni galti khud pakad leta hai. Kaam isiliye karta hai kyunki self-correction capability model me already train ho chuki hai; budget forcing bas usse trigger/stop karta hai. Aaj yeh `reasoning_effort` / thinking-budget parameters ke roop me productized hai.

**Q8. Chhote open models bina RL ke reasoning kaise kar lete hain?**
Distillation (Section 2 ka direct extension). Ek bada RL-trained reasoning model hazaaron long-CoT traces generate karta hai, verifier se filter hote hain, aur chhote base models un traces par plain SFT hote hain — R1-distilled Qwen/Llama isi tarah bane. Yeh sasta aur effective hai, par ceiling teacher ka hai: student teacher ke behaviour ko copy karta hai, uske aage explore nahi karta. Aage badhne ke liye student par bhi apna RL round chahiye.

---

## Why no `_practical.py` here
Yeh training-internals hain — tum inference/agent side kaam karte ho. Interview me concept + one-liner kaafi hai. Agar kabhi fine-tune/distill karna pade, tab HuggingFace `trl` (DPO/PPO/**GRPO** trainers) dekhna — but woh iss repo ke scope se bahar hai. Consume-side me sabse pehla realistic touchpoint **RFT-style API** hai: prompts + ek grader do, RL provider chalayega.

**Related covered files:** fine-tuning basics → search repo for `fine.?tun`; agent evaluation → [Level8_Production_LLMOps](../Level8_Production_LLMOps/).
