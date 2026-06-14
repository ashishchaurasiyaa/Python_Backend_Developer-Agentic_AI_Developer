# L105 — Deploying AI-Generated APIs to Production with AWS Lambda & Terraform

> **Week 4 · Day 3** · ⏱️ ~7 min

---

## 🎯 TL;DR

Ed FastAPI ke **Swagger docs** (`/docs`) dikhata hai, phir Alex ke API ko **AWS Lambda** par package karta hai aur **Terraform** se pura production infra (S3, Lambda, API Gateway, CloudFront) deploy karta hai — Week 1 + Week 2 ka convergence.

---

## 🗣️ Hinglish Explanation

### Pehle: UI polish + modal tweak

Ed UI se ab bhi impressed hai — bolta hai "stare at it all day". **Reset All** button ek pyaara **modal** dikhata hai ("Are you sure you want to delete all your accounts?"). Initially Claude ne ek **bhayanak native JavaScript `alert()` popup** banaya tha — Ed ne spec dekar **proper modal** banwaya. Yeh dikhata hai ki AI ko production-quality UX ke liye **guidance** deni padti hai. Phir repopulate test data karke quick check, refresh smooth.

### FastAPI ke free Swagger docs

Server `localhost:8000` par chal raha hai. Ed root nahi, **`/docs` route** kholta hai:

```
http://localhost:8000/docs
```

**FastAPI yeh out-of-the-box deta hai** — automatic **Swagger UI** jo saari API routes interactively document karta hai. Yeh routes Claude Code ne generate kiye the. Tum har endpoint expand karke dekh sakte ho: kya karta hai, request/response shape, aur "Try it out" se test bhi kar sakte ho.

> **Background**: FastAPI har endpoint ke type hints + Pydantic models se **OpenAPI schema** auto-generate karta hai. `/docs` = Swagger UI, `/redoc` = ReDoc — dono free, zero config. Production-grade API documentation jo normally manually likhni padti, yahan automatic hai.

Guide ke **step 2.4** mein yeh `localhost:8000/docs` explore karne ka mention hai — positions add/delete/update, cash balance update — sab test kar sakte ho.

### Ab production deployment — Week 1 + Week 2 ka milap

Yeh asli moment hai. Plan:
1. API ko **Lambda service** ke roop mein deploy karo.
2. Uske upar **AWS API Gateway**.
3. **Deployed frontend** (S3 + CloudFront).

Yeh exactly Week 2 wala architecture hai. Ed bolta hai yeh **Week 1 + Week 2 coming together** hai:
- **Week 1** se: Clerk user authentication, **pages router** (Next.js).
- **Week 2** se: pura deployment architecture (Lambda + API Gateway + S3 + CloudFront via Terraform).

### Step 4.1 — Terraform setup

Terraform directory mein **7th folder: `seven-front-end`** kholo — yeh aakhri Terraform folder hai (baad mein ek cheez change karenge). Pehla kaam: **tfvars** banao.

```bash
# terraform/7-front-end/ ke andar
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars` mein fill karo:
- **AWS region**
- **Clerk JWKS URL** aur **issuer** (jo local/SaaS project se mila tha) — yeh authentication tokens verify karne ke liye.

> **Background — Terraform/IaC**: Terraform **Infrastructure as Code** tool hai — `.tf` files mein declaratively likhte ho "kya infra chahiye", Terraform AWS API call karke wo bana deta hai. `tfvars` = sensitive/environment-specific values (region, secrets) jo `.example` template se copy karke fill karte ho (taaki actual secrets git mein commit na hon).

### API Lambda package karo

Pehle local server `Cmd+C` se band karo. Phir backend/API directory mein jao aur packaging script chalao:

```bash
# backend/api/ ke andar
./package_docker.sh   # ya jo bhi guide mein "run package docker" command hai
```

Yeh API code ko ek **zip file** mein package karta hai (Docker-based build se dependencies sahi Lambda runtime ke liye compile hoti hain). Guide bolta hai ~1 min, par Ed ke paas Docker pehle se installed tha toh super fast hua (tumhare liye thoda slow ho sakta hai pehli baar).

> **Background — Lambda packaging via Docker**: AWS Lambda ko ek deployment zip chahiye jismein code + dependencies hon, jo **Lambda ke Amazon Linux environment** ke liye compiled hon. Docker isliye use hota hai taaki dependencies (especially native/C-extension wale) sahi platform ke liye build hon — chahe tum Mac/Windows par ho.

### Terraform init + apply

```bash
# terraform/7-front-end/ ke andar
terraform init     # providers/modules download — pehli baar slow
terraform plan      # (optional) preview — kya banayega bina banaye
terraform apply     # actually banao → "yes"
```

Ed batata hai: hamesha `init` + `apply` karta hai, par chaaho toh beech mein `terraform plan` karke dekh lo ki Terraform **kya-kya create karega** (kuch log ise prefer karte hain safety ke liye).

### `main.tf` mein kya ban raha hai (Week 2 jaisa)

`apply` ke dauraan Ed `main.tf` kholta hai — sab familiar hai Week 2 se:

1. **Provider block** — AWS provider config (shuru mein).
2. **`aws_s3_bucket`** — frontend ke static files ke liye.
3. **IAM policies/roles** — Lambda ko permissions dene ke liye (kaafi IAM "stuff").
4. **`aws_lambda_function`** — API Lambda, jo **abhi banaye gaye zip file** ko use karta hai.
5. **Environment variables** — Lambda ko Aurora cluster **ARN** + **secret** Terraform current state se mil rahe hain; sahi **CORS origins** set ho rahe hain.
6. **`aws_api_gateway_*`** — AWS API Gateway setup, with **proper authority**, plus **throttling/rate-limiting** settings (enterprise deployment ke liye super important).
7. **Lambda permissions** — API Gateway ko Lambda invoke karne ki permission.
8. **`aws_cloudfront_distribution`** — S3 bucket ko global CDN ke saath serve karne ke liye.

> **Background — yeh services kya hain**:
> - **S3** = object storage; yahan frontend ke built static assets rakhe jaate hain.
> - **Lambda** = serverless functions; API code on-demand chalta hai, idle par cost nahi.
> - **API Gateway** = managed HTTP front-door jo requests ko Lambda tak route karta hai; auth, throttling, rate-limiting yahan hoti hai.
> - **CloudFront** = CDN; S3 content ko edge locations se globally fast serve karta hai + HTTPS.
> - **IAM** = permissions/identity; kaunsa service kya kar sakta hai.
> - **CORS** = browser ko batata hai kaun se origins se API call allowed hai.
> - **Throttling/rate-limiting** = ek client kitni requests/sec bhej sakta hai — abuse/cost-spike se bachne ke liye.

Ed emphasize karta hai: yeh infra Week 2 se **consistent** hai, toh pehli baar daunting lage par familiarity se grasp ho jaayega. Jab tak wo bol raha tha, **deployment finish ho gaya** — ek clickable link aaya jisse verify karenge ki yeh actually internet par chal raha hai (agla lecture).

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **FastAPI `/docs`** | Auto-generated Swagger UI — saari API routes interactively documented, zero config |
| **Modal vs alert()** | Production UX: native browser `alert()` ki jagah proper styled modal (AI ko spec deni padi) |
| **Terraform tfvars** | Environment-specific values (region, Clerk URL/issuer) `.example` se copy karke fill |
| **package_docker** | API ko Lambda-compatible zip mein Docker se package karna |
| **terraform init/plan/apply** | init=setup, plan=preview, apply=actually build infra |
| **API Gateway** | Lambda ke saamne managed HTTP gateway — auth, throttling, rate-limiting |
| **CloudFront** | CDN — S3 frontend ko globally fast + HTTPS serve |
| **Aurora ARN/secret** | Lambda env vars Terraform state se aate hain (DB connection) |
| **Throttling/rate-limiting** | Per-client request limits — enterprise strength + cost control |

---

## 💼 Backend Dev Ke Liye Note

Ek Python backend dev ke liye yeh "FastAPI app ko serverless production mein le jaane" ki canonical recipe hai. Tum `uvicorn instant:app` se local chalate ho — production mein wahi ASGI app ek **Lambda handler** (usually Mangum jaisa adapter ya container-image Lambda) ke through serve hota hai, aur API Gateway HTTP requests ko Lambda invoke mein translate karta hai. Do cheezein khaas note karo: (1) **`/docs` OpenAPI** free documentation — manual API docs maintain karne ki zaroorat khatam; production mein ise auth ke peeche rakhna good practice. (2) **Dependencies Docker mein build karna** — kyunki Lambda Amazon Linux par chalta hai, native wheels (pydantic-core, psycopg, etc.) ko target platform ke liye build karna padta hai, warna `ImportError`/`GLIBC` issues. Terraform se yeh poora stack (S3+Lambda+API GW+CloudFront+IAM) **reproducible, version-controlled, one-command** ban jaata hai — manual console clicking ki jagah.

---

## ✅ Takeaway

- FastAPI **`localhost:8000/docs`** par free Swagger UI deta hai — saari (AI-generated) routes documented + testable.
- Production deploy = **Week 1 (Clerk auth + pages router) + Week 2 (Lambda+API GW+S3+CloudFront via Terraform)** ka convergence.
- Flow: `cp terraform.tfvars.example terraform.tfvars` → fill region+Clerk → `package_docker` (API → zip) → `terraform init` → `apply`.
- `main.tf` Week 2 jaisa hi: S3 + IAM + Lambda (zip se) + env vars (Aurora ARN/secret) + API Gateway (throttling) + CloudFront.
- Production UX details (modal vs alert) ke liye AI ko **explicit spec** deni padti hai.

---

<details>
<summary>📜 Full Transcript (English)</summary>

I could stare at this user interface all day. It's just so great and you should come in and play with it. Add and subtract, remove things, make sure that it all works. You can also do things like I can press reset all and it comes up with this lovely modal. Are you sure you want to delete all your accounts? Delete all accounts. And by the way, it wasn't like that initially. It did it with one of those dreadful JavaScript pop ups and I had to tell it to build a modal. So there was definitely tweaking that I had to do, but it responded so quickly. And then we repopulate the test data as a quick way to check. Wait a second. And then it refreshes. So slick, so so so smooth. One other thing I want to show you. So you remember our server is running on localhost 8000. Um, I'm not going to hit our server. I'm going to go to a root docs. This is something which fast API does uh, out of the box, which is really great, which is show us swagger docs of our API. Uh, so this is showing you right now the different API routes that were all generated by by an LLM by Claude code for me. Uh, and you can come in and look at these different, uh, these different, um, API routes and what they do, uh, and look around the, uh, the, some example there. Uh, amazing. So we've got this full documentation of our backend of our API routes, and it's all there on localhost 8000. You should go and take a look for yourself. And here we are back in the in the the guide. You'll see it explains how you can explore the API documentation in step 2.4, uh by going to host and localhost 8000 docs and look around. And we already did this. We added a test portfolio data. And you can go through these different steps to add new positions, delete them, update the cash balance, make sure everything works. But I can't wait to get on to deploying this to production. This is this is really where everything comes together is we're now going to take this and deploy it out there. So that API is running as a Lambda service so that we have an API. the AWS API gateway on top of it, and then we have our deployed front end. It's just what we did in week two. So in many ways this is week one and week two coming together. We're using the the clerk uh, user authentication. We're using the pages router. But we're using the everything from week two in terms of the whole deployment architecture. So I hope you're excited. Let's get to it. Go to step 4.1. We're going to set up Terraform and then deploy. Okay. And it's time for us to get Terraform going. So open the terraform directory and come to the seventh folder seven front end. You'll notice it's the last the last of our Terraform folders. Never fear we're going to go back and change something later. But still this is the last of our Terraform folders here. Seven front end. Uh, and the first thing to do is to take this terraform.tf example and, uh, copy that and make it terraform.tf vars as before. Uh, right click and copy and then paste and then rename and just fill in these things. Fill in your AWS region and fill in your Clark JDBC URL and issuer should look something like that, which you will have taken from your local, uh, and or from your SaaS project. So you should have that set up in your Terraform.tf vars. Okay. And now it is time now to package up your our APIs Lambda. So what we're going to open up a new of these. By the way I command seed out of the uh, the server that was running from before the local server, which you should do as well. Okay. So we're now going to go into backend and then we're going to go into the API directory. Here we are. And we're going to do you've run package Docker. And this of course is going to package up the the back end the API into a nice uh. Uh a nice zip file. And it says here it'll take about a minute. It did not take about a minute. It caught me off guard. It was so quick, but that might be because I already had it installed. Uh, but hopefully that will be nice and quick for you. And that brings us to time to to run Terraform. How is this happening so quickly? Uh, so let's go out. Let's go to, uh, our terraform directory. Sorry. Back one more into our Terraform directory and now into the seventh folder. And you know the drill by now we start by doing terraform init which will run fast for me, but it might take a bit longer for you. There it go. It's done. And now you can. So I've always said Terraform init and terraform apply. If you wish you could do this step Terraform plan which shows you what it will build if you run it. So sometimes people like to do terraform init and then a terraform plan to see it right there. But now we're going to do a terraform apply. And off it goes. And it says do we want to do this. And we'll say yes. And it's going off and creating. And while it's going off and creating Let's go and click on main and find out what is it creating. And a lot of this should be familiar to you because it'll be very similar to what we built in in in week two. So there's the usual provider stuff at the beginning. And then there is uh, the AWS S3 bucket for the front end. This is the S3 bucket. Uh, then, um, this is some, some, uh, it's, uh, policy. Uh, IAM stuff, IAM stuff. I'm more IAM stuff. And here is our lambda function for the API lambda function. That's where it's getting the zip file that we just built right there. Here are some environment variables that it's getting. It's it's collecting the Aurora cluster Arn and secret from the Terraform current state. Uh, it's setting the the right cause origins. Uh, and this is the API gateway. This is where we're setting up our AWS API gateway. You can see we're giving it the all of the right authority to do what we need. This is some throttling and rate limiting settings. So we're putting on our API gateway which is super important for an enterprise strength deployment. Uh, and uh some some uh permissions stuff. This is the AWS CloudFront distribution. This is where we're taking our S3 bucket and saying we want to make a CloudFront distribution out of it. And here it is. Uh, and, um, I think we're probably almost done here. There we go. And that's it. So that is all of the infrastructure we're building. And of course, there's a lot here. And the first time you see it, it can be unwieldy. But the good news is so much of this is consistent with what we had before, uh, in week two. So a lot of this should be very familiar to you. And you'll, you'll, you'll hopefully have a good grasp for the infrastructure we're creating. And while I was going through all of that, it finished, it deployed. There's somewhere we can click to and then we can see whether this actually works.

</details>
