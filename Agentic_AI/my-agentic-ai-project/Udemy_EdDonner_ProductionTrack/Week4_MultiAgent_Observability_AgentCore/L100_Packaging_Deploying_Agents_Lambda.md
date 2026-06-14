# L100 — Packaging and Deploying Multi-Agent AI Systems to AWS Lambda

> **Week 4 · Day 2** · ⏱️ ~12 min

---

## 🎯 TL;DR

Yeh capstone (Alex financial planner) ka **step 4** hai — paanchon agents ko ek script (`package_docker.py`) se Docker ke through Linux-ready zip files mein package karte hain, phir Terraform (`6_agents`) se SQS queue + IAM + S3 + 5 Lambda functions deploy karte hain, aur har agent ko remotely test karte hain.

---

## 🗣️ Hinglish Explanation

### Context: hum kahan hain

Yeh Week 4, Day 2 ka climax hai. Pichle dino mein humne Alex (agentic financial planner SaaS) ki **database layer** (Aurora Serverless v2), **research agent** (Week 3), aur **paanch agents** ka code bana liya hai jo locally test ho chuka hai. Ab guide ka **step 4** — sab kuch **AWS Lambda** ke liye package karke deploy karna hai.

Paanch agents kaunse hain:
- **planner** — orchestrator (baaki sabko tool calls ke through bulata hai)
- **tagger** — instruments ko tag/classify karta hai
- **reporter** — reports generate karta hai
- **charter** — visualizations/charts banata hai
- **retirement** — retirement analysis karta hai

### Step 1: Sab agents ko ek saath package karo

Pehle agents ek-ek karke package hote the. Ab ek convenience script `parent directory` (backend) mein hai jo sab kuch automate karta hai:

```bash
cd backend
uv run package_docker.py
```

**Yeh script kya karti hai (important nuance):**
- Yeh **Docker use karta hai** packaging ke liye — **par hum Docker container build NAHI kar rahe**. Confusing lagta hai, lekin idea yeh hai: Lambda **Linux** par chalta hai. Agar tum Mac/Windows par dependencies install karoge toh wo native binaries us OS ke hisaab se banenge — Lambda par crash ho sakte hain (especially C-extensions wale packages jaise `pydantic`, `numpy`, etc.). Isliye Docker ke andar ek **Linux environment** spin karke usmein dependencies install karte hain, taaki package **Lambda-compatible** ho. Yeh ek **common technique** hai.
- Har agent ko uski dependencies ke saath **alag zip file** mein package karta hai (deployment package).
- Output: har agent ki subdirectory mein ek **fresh `.zip` file** banti hai (jaise `charter/charter.zip`). Purani zip overwrite ho jaati hai.
- Process **kayi minutes** leta hai.

> **AWS Lambda kya hai (background):** Lambda ek **serverless compute** service hai. Tum apna code (function) upload karte ho — AWS infrastructure provision karta hai, request aane par function ko spin up karta hai, chalata hai, aur idle hone par band kar deta hai. **Pay-per-invocation**, auto-scaling, koi server manage nahi. Code ko ek **deployment package** (zip ya container image) ke roop mein deliver karte ho. Lambda Amazon Linux par chalta hai — isi liye Linux-compatible packaging zaroori hai.

Run successful hone par output: **"5 out of 5 packaged"**, sab **success** mark — paanch fresh zip files ready.

### Step 2: Terraform setup (`6_agents` directory)

Ab deploy ka time. Terraform directory mein ek `6_agents` folder hai jisme agents ka infra defined hai.

**Pehle config file banao** — example/template ko copy-paste karke rename karo `terraform.tfvars`:

```hcl
# terraform.tfvars (6_agents)
region              = "us-east-1"        # tumhara apna region

# Aurora cluster ARN aur secret — BLANK chhod do
# Terraform inhe existing infrastructure se khud lookup kar lega
aurora_cluster_arn  = ""
aurora_secret_arn   = ""

s3_bucket_name      = "alex-vectors"     # part 3 wala vectors bucket
account_id          = "123456789012"     # tumhara AWS account ID
bedrock_model_id    = "amazon.nova-pro-v1:0"   # Nova Pro suggested
bedrock_region      = "us-west-2"        # us-west-2 suggested
sagemaker_endpoint  = "alex-embeddings"  # questions vectorize karne ke liye
polygon_api_key     = "YOUR_POLYGON_KEY"
polygon_plan        = "free"             # "free" ya "paid"

# langfuse_... = "..."   # COMMENTED — yeh baad mein aayega (observability day)
```

Important points:
- **Aurora ARN/secret blank** — Terraform existing infra se lookup karega. (Extra-safe rehne ke liye Ed ne `.env` se dono Aurora secrets manually copy kiye `tfvars` mein — tum bhi kar sakte ho.)
- **S3 bucket** = `alex-vectors` (Week 3 mein bana tha vector storage ke liye).
- **SageMaker endpoint** kyun? Kyunki agent ko research lookup karne ke liye **questions ko vectorize** karna padta hai — yeh kaam SageMaker-deployed embedding model karta hai.
- **Bedrock** = managed frontier-model service; yahan **Nova Pro** model use ho raha hai (OSS 120B bhi try kar sakte ho).
- **Langfuse line commented** — observability "joy for another day" (Day 4).

### Step 3: `main.tf` mein kya infra hai (samajhne layak)

Terraform `apply` se pehle `main.tf` dekho — kaafi infrastructure hai:

1. **SQS queue** — *Simple Queue Service*. Yeh managed task queue hai. Tasks queue par jaate hain, picked up hote hain, aur run hote hain. Yahi se agents ko **tasks deliver** honge (UI message daalega → planner uthayega).
2. **IAM stuff** — bahut saari **policies**. (IAM = *Identity and Access Management* — kaun-si service kya kar sakti hai, permissions define karta hai.) Har Lambda ko apni execution role + policies chahiye (S3 read, SQS access, Bedrock invoke, SageMaker invoke, RDS Data API, CloudWatch logs).
3. **S3 objects for Lambda packages** — har agent ka deployment zip ek **S3 object** banta hai. (Lambda bade packages ko pehle S3 par upload karke wahan se kheechta hai.)
4. **5 × `aws_lambda_function`** — planner, tagger, reporter, charter, retirement. Har ek mein specify hota hai:
   - kaunsi **zip file** collect karni hai
   - **environment variables** (config file se) — model ID, region, bucket, endpoint, polygon key, etc.
5. **CloudWatch log groups** — har Lambda ke logs collect karne ke liye. (CloudWatch = AWS ka monitoring/logging service.)

> **Terraform / IaC background:** Terraform ek **Infrastructure as Code** tool hai — tum infra ko HCL files mein *declaratively* describe karte ho (kya hona chahiye), Terraform actual state ko desired state se match karta hai. `init` = providers/modules download. `plan` = diff dikhata hai. `apply` = changes karta hai. **Idempotent** — dobara chalao toh sirf zaroori changes karega.

### Step 4: Deploy karo — init + apply

```bash
cd terraform/6_agents
terraform init     # quick (providers/modules setup)
terraform apply    # THE BIG ONE
```

`apply` pehle batata hai kya karega; **`yes`** type karna padta hai. Phir:
- **5 different agents** ko **5 different Lambda functions** par deploy karta hai
- zip files pehle **S3 par upload** hote hain, phir Lambda function par
- **SQS queue** set up hoti hai (taaki UI eventually queue par task daal sake)
- saath mein **CloudWatch** + **IAM** sab build hota hai

Complete hone par output mein milta hai: deployed confirmation, **model**, **region**, **SQS** ka location, aur banaye gaye **CloudWatch log groups** ki info.

### Step 5: Redeploy all lambdas (good practice)

Yeh step **strictly zaroori nahi** abhi (kyunki abhi-abhi deploy kiya), par **code change ke baad** hamesha karna chahiye:

```bash
cd backend
uv run deploy_all_lambdas.py
```

Yeh script pehle har deployment ko **"taint"** karti hai — yaani Terraform ko mark karti hai ki "yeh redeploy hona chahiye" — phir paanchon Lambda functions ko packaged code se **update** kar deti hai.

> **Tainting (Terraform concept):** `taint` ek resource ko "needs recreation" mark karta hai, taaki agle apply par wo destroy + recreate ho. Yahan iska use force-redeploy ke liye ho raha hai, bhale hi code same dikhe.

### Step 6: Remote testing — "moment of truth"

Ab har agent ko **remotely** (cloud Lambda par) test karte hain. `test_simple.py` vs `test_full.py` ka farak: **simple** local test hai, **full** actual **Lambda call** karta hai cloud mein.

**Tagger se shuru:**
```bash
cd backend/tagger
uv run test_full.py
```
Yeh Lambda call karke 3 instruments tag karta hai (jaise planner internally karega — ek Lambda doosri Lambda ko bulata hai). Pehli baar Lambda ko **spin up** hona padta hai (cold start), thoda extra time. Result: Arc, Sophie, Tesla sab tag hue (e.g. Tesla → "North American equity", 98% equity / 2% cash), **no errors** = success.

**Reporter:**
```bash
cd backend/reporter
uv run test_full.py
```
Lambda function chala, "Report generated successfully" — bunch of reports aaye.

**Charter + retirement + planner (parallel — Lambda async hai!):**
```bash
cd backend/charter && uv run test_full.py
# alag terminal:
cd backend/retirement && uv run test_full.py
# alag terminal:
cd backend/planner && uv run test_full.py    # THE BIG ONE
```
Lambda ke **asynchronous/parallel** nature ko dikhane ke liye Ed teen terminals mein ek saath chalata hai. Charter ne charts banaye (local jaise hi dikhe par cloud par chale). Retirement bhi success. **Planner** sabse bada hai (baaki sabko orchestrate karta hai) — job progress monitor karta hai, thoda zyada time leta hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`package_docker.py`** | Saare agents ko Docker (Linux env) ke through Lambda-ready zip mein package karne wala script |
| **Docker for packaging (not container)** | Container build nahi — sirf Linux-compatible dependencies banane ke liye Docker use |
| **AWS Lambda** | Serverless compute — code zip upload karo, AWS per-request chalata hai, auto-scale |
| **Deployment package (.zip)** | Lambda function ka code + dependencies, ek zip mein |
| **SQS (Simple Queue Service)** | Managed task queue — UI task daalti hai, planner uthata hai |
| **`terraform.tfvars`** | Agents infra ke liye config values (region, model, bucket, keys, endpoint) |
| **Aurora ARN/secret blank** | Terraform existing infra se khud lookup kar leta hai |
| **`6_agents/main.tf`** | SQS + IAM policies + S3 objects + 5 Lambdas + CloudWatch logs ka IaC |
| **`terraform init` / `apply`** | Init = setup; Apply = actual deploy (yes confirm karna padta hai) |
| **`deploy_all_lambdas.py`** | Taint + redeploy all 5 lambdas — code change ke baad chalao |
| **Taint** | Terraform resource ko "recreate me" mark karna (force redeploy) |
| **`test_full.py` vs `test_simple.py`** | Full = real Lambda call (cloud); Simple = local |
| **Cold start** | Lambda ko pehli baar spin up hone mein lagne wala extra time |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye yeh lecture **distributed agentic architecture** ka asli production roop hai. Notice karo: har agent ek **independent serverless service** hai — yeh microservices pattern hai, jahan planner ek service doosri service ko (Lambda → Lambda) call karta hai, na ki ek hi process mein in-memory function call. Packaging step ka sabaq universal hai: **deploy target ke OS ke liye build karo** — Mac par bana `numpy` wheel Amazon Linux par toot sakta hai, isliye Docker-based Linux build (ya Lambda layers / `--platform manylinux`) standard practice hai. SQS ka use seekho: synchronous HTTP ki jagah **queue-based decoupling** se producer (UI) aur consumer (planner) independent scale karte hain, retries milte hain, aur spikes absorb hote hain. Aur Terraform `taint` ka analog tumhare CI mein "force rebuild/redeploy" flag hai. Local `test_full.py` jaisa harness banana — jo real cloud endpoint hit kare — ek lightweight **integration/smoke test** hai jo deployment verify karta hai.

---

## ✅ Takeaway

- `uv run package_docker.py` Docker ke through **Linux-ready zip** banata hai (container nahi) — Lambda OS-compatibility ke liye
- `6_agents` Terraform: `terraform.tfvars` bharo → `terraform init` → `terraform apply` (yes) — SQS + IAM + S3 + 5 Lambdas + CloudWatch deploy
- Aurora ARN/secret blank chhod sakte ho (Terraform lookup karta hai); langfuse line commented rakho
- Code change ke baad `uv run deploy_all_lambdas.py` (taint + redeploy)
- `test_full.py` har agent ko **real cloud Lambda** par test karta hai — Lambda async hai, parallel terminals mein chala sakte ho

---

<details>
<summary>📜 Full Transcript (English)</summary>

And now we've reached step four of the guide. And the big thing to do now is to be packaging everything up for Lambda. And this time, we're not going to do them one by one, because it's just a nice little script in the parent directory in backend. So CD backend. There we are. And now I'm going to do UV run package_docker.py. And off it goes. Packaging packaging packaging. So let's just quickly explain what this is doing. It's going to use Docker to do the packaging process. We're not building a Docker container. I know it's a bit confusing. We're we're using Docker in order to make sure that the things that we package up are ready for Linux. For Lambda, it's a common technique. We're packaging up each agent together with its dependencies. We're going to be creating different zip files for deploying to Lambda. And it's going to take several minutes. What we're expecting to come out of this is that in each subdirectory there'll be a new fresh zip file created, which if we if we go into each each of these directories look at charter. You'll see there was already one there from before charter zip. But each of these is being recreated right now. Uh, and they will be happening and it will take a few minutes to run. But when it's done, we'll be the proud owners of packaged zip files for each one. There we go. You can see what I've been yammering away. The first one's been done, and in a moment, they'll all be done. And I will see you then. And you'll see that this has run successfully. Everything has been marked success. Five out of five packaged. We now have five new zip files in each of those subdirectories. Okay. It's time to deploy. So we're going to go back to to terraform. The terraform directory has a six underscore agents directory with our Terraform set up for our agents. And first of all we're going to again copy Terraform to make that into our official Terraform files. So you can just right click on here and do a copy and paste and rename it to look like this. Now in here we'll need to set the the Lambda function the region as US East one for me. And wherever your region is for you, you can leave these two blank. This was the Aurora cluster. Uh, Arn and secret. Um, because it's going to be able Terraform is gonna be able to look that up, uh, from the existing infrastructure. But you will need to populate the S3 bucket name. Uh, Alex vectors. It should be Alex Vectors. And then the your account ID, it's whatever we did back in all the way back in part three. Uh, and the bedrock model ID will be using, uh, I suggest Nova Pro, the bedrock region, which I suggest us West two, and also the SageMaker endpoint name, because our agent needs to be able to vectorize questions to be able to look up research of. And then finally the polygon API key and the polygon plan just the word free or paid. So there's quite a lot in there to fill in. If we go into the example, you'll see that that in this example file it's all here for you. Fill in the region. You can you can just delete that and leave it blank. Um, you can also paste in your actual credentials and uh, key if you wish. I think I did do that. So maybe you should do that. But I believe if you leave it blank it will automatically populate it anyway. Then your Alex vectors your bedrock model ID and the SageMaker endpoint, your polygon plan that, uh, it can be. I should probably make it default to free, uh, your key and your plan and then leave this commented out. This is something we will come back to. Lang views is a joy for another day. Uh, so, um, save save this as Terraform.tf vars and then come, come back here and it's time for us to to do this. That's all there is. Uh, of course it's worth taking a look at main.tf. Let's look at what infrastructure. There's a lot of it. We're about to kick off. There's going to be the, uh, the SQS queue. This is how we we will be delivering tasks to our agents. So there is this SQS queue. SQS simple queue service is the AWS service that allows you to have managed tasks that go on a queue and they get picked up and run. Um, and then we have some IAM stuff. There's always IAM stuff, lots of policy stuff here. And uh, you can read through all of these policies. We have S3 objects for our Lambda packages. Uh, so each of our, each of our Lambda deployment packages gets a S3 object and then the Lambda itself, AWS Lambda function. This is planners Lambda function. And you can see where we specify the zip file for it to collect. Uh, and this is where we specify the environment variables that it needs to have. Uh from, from the file. Then this is the, uh, planner, uh, and the tagger and reporter and, uh, charter. So here you see them all. And retirement. That's our final agent. Those are all of our different, uh, setups. And then we have here. Which one is this? Sorry, that that is the retirement lambda function. Uh, then we have some CloudWatch log groups, and that is it. That is our full set of Terraform, uh, code to describe our infrastructure that we're building. And now we're going to do a Terraform init and then Terraform apply. And it shouldn't be required. But just to be extra safe, I did just copy from my env file those two aurora secrets into that terraform tf vars file. So so I'm in good shape. You should do the same. And then we're going to go into the upper directory into Terraform. And now we're going to go into the sixth agents directory. And we're going to go ahead and run terraform init. This should be a quick for me, but it might take a little bit longer for you. And then terraform apply. This is the big one. It's going to tell me what it's about to do. And I'll have to type the word yes I'll type yes and off it goes doing its stuff. It's now deploying five different agents to five different Lambda functions. It's uploading those zip files that have been packaged up. They first go to S3 and then they get uploaded to the Lambda function. It's also setting up the SQS, the simple queue service, so that eventually our user interface will be able to put something on a queue and then let everything run. And all of that has been built along with things like CloudWatch stuff and the IAM stuff. And I'll come back when it's finished and we'll be ready to give this a try. And it completed. There we go. It finished up and it says that that uh, everything is deployed and it gives us the model, the region where SQS is. And it also tells us about the CloudWatch logs that were created. So lots of good information there. The next step isn't strictly necessary in this case, but a good practice to do it is to redeploy all of our lambdas. You would want to do this anytime you change any code. So we'll go back. We have of course just deployed the lambdas. So they are all all up to date. But we go into backend and we do UV run deploy all lambdas.py and off that goes. And that is now going to first. That's what's called tainting, which is marking each of these different deployments as needing to be redeployed. And it's going off and deploying them right now updating the five Lambda functions with our packaged code. And we will let that run. And I'll be back in a minute. All right. And that has been deployed successfully. And you know, I you know, I don't use the expression moment of truth lightly. It's been a while since I've set it apart. Here we have it. Here we have surely a moment of truth. Let's go into. We're now going to test. Test each of our agents remotely. We're going to start with a simple one, the tagger. So we're going to go into tagger uh and we're going to do UV run test full uh test underscore full dot pi. And so the difference between this and test simple is that what this is doing is making a lambda call to tag three instruments. So it's calling out to our serverless function running in the cloud. And it's doing it in the same way as the planner. The the lambda function itself will call the others. So off it's going to lambda to tag these instruments right now. Uh, and once we're done with that, we're going to come through and test each of them in turn. Uh, and the first time, of course, that lambda function has to spin up, so it might take a bit longer and it's then going to go through and tag each of those. Uh, and with any luck, there we go. It's finished. Uh, and we've got back some, some tagging that happened. Uh, and uh, yeah, all of these three got, uh, got tagged and there were no errors. So that is a success. And now let's go up and go to reporter and UV run test full dot pi. And we're now running the reporter again also running it as a lambda function. And while we're doing that let's just look back what we're seeing here. Checking database for tagged instruments Arc was tagged successfully, Sophie was tagged successfully. And Tesla was taxed successfully as a North American equity. That sounds good. Uh, some of this looks a little bit odd. Uh, 98% equity and 2% cash. I guess that that might well be true. Uh, I have to say, I don't know. So, uh, the, uh, the tagging does appear to have been successful. Um, the, uh, reporter Lambda is now running, and there we go. We can see that it came back with a bunch of reports. Report generated successfully. Uh, and, uh, that all sounds great. I don't know what this is, but I think we can safely ignore it because this is clearly generated successfully, and everything worked. And now we'll go and try the charter. Uh, UV run test full. Off it goes. And you know what? We can we can be, uh, we can show how lambda is nice and asynchronous because we can open another terminal at the same time and run retirement and planner in parallel. Uh c backend, uh, and, uh, we can go into, um, retirement and UV run, test full pi and kick that one off and then open another terminal and CD, uh, back end and CD planner. This is the big one, of course. And you've run test.py. And this is the, uh, the the. Yeah, we'll let that run as well. So, so, um, each of these is now running. Let's go back up to charter and see how that's doing that already completed. It created a bunch of different charts, just as we would hope. It looks rather similar to the one that was running locally. But this has of course run on Lambda. And here we go. We see that the retirement one also completed successfully. And now if we come over here, uh, you can see that this is, uh, running at the moment, uh, and it's monitoring the job progress right here, which is, which is great. And this one might take a bit longer, the planner, since it's got to do all of the others. So I will come back in a second when planner, which is the last of this set of tests, uh, has completed.

</details>
