# L43 — Setting Up S3 Buckets and API Gateway for Production AI Apps

> **Week 2 · Day 2** · ⏱️ ~13 min

---

## 🎯 TL;DR

Doosra S3 bucket (frontend static site) banate hain — **public access** + **static website hosting** + ek **bucket policy** ke saath; phir **API Gateway (HTTP API)** banate hain jo Lambda ko duniya ke saamne expose karta hai, saari routes (`ANY /`, `GET /`, `GET /health`, `POST /chat`, `OPTIONS /`) Lambda par bhejte hain, **CORS** configure karte hain, aur live endpoint par `/health` hit karke production verify karte hain.

---

## 🗣️ Hinglish Explanation

Aadhe raaste par hain. Ab tak: ek **memory S3 bucket**, ek **Lambda function** (S3 permission ke saath). Is lecture mein hum **doosra S3 bucket** (frontend ke liye) aur **API Gateway** banayenge.

> **Recap — do S3 buckets kyun?** Ek **memory bucket** (L42 mein bana — conversation JSON store) aur ek **frontend bucket** (poori static website host karega — HTML/CSS/JS). Dono ka role bilkul alag.

### Part 1: Frontend S3 bucket (public static website)

1. **S3** → **Create bucket** → **General purpose**.
2. Name: **`twin-frontend-<account_id>`** (account ID Copy karke paste).
3. **Same region** mein (baaki sab ke saath consistent).
4. **Block all public access** ko **uncheck** karo — kyunki hum chahte hain duniya is bucket ko dekhe (yeh hamari public website hai).
5. Acknowledge checkbox tick: *"I acknowledge that this will result in the bucket becoming public"* — haan, website public honi hi chahiye.
6. **Create bucket**.

> **Static website hosting:** S3 sirf files store nahi, balki unhe directly **website ki tarah serve** kar sakta hai (HTTP par). No server, no compute — pure object serving. Bilkul ideal hai SPA/static frontend ke liye.

7. Bucket → **Properties** → neeche scroll → **Static website hosting** → **Edit** → **Enable**.
8. **Index document:** `index.html`
9. **Error document:** `404.html`
10. **Save changes**.

#### Bucket policy — public read allow karo

Public access block hatane se bucket "public-capable" ho gaya, par actual public **read** allow karne ke liye ek **bucket policy** chahiye (resource-based IAM policy).

> **Bucket policy** = bucket par directly attached ek JSON IAM policy jo batati hai kaun kya kar sakta hai. Yahan hum **anyone (`Principal: *`)** ko **`s3:GetObject`** (read) allow kar rahe hain — taaki browser website files fetch kar sake.

1. Bucket → **Permissions** tab → **Bucket policy** → **Edit**.
2. Yeh policy paste karo, aur **`Resource` mein apna bucket ARN** daalo (`/*` zaroori hai — saare objects par apply):

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "PublicReadGetObject",
         "Effect": "Allow",
         "Principal": "*",
         "Action": "s3:GetObject",
         "Resource": "arn:aws:s3:::twin-frontend-<account_id>/*"
       }
     ]
   }
   ```

   - **ARN (Amazon Resource Name)** bucket ke heading ke paas se Copy kar sakte ho; usme **`/*`** add karna mat bhoolo (warna sirf bucket, objects nahi).
3. **Save changes** (pehle ARN sahi karo, tabhi save).

Ed honestly bolta hai yeh "super hokey / janky" hai aur galti karna aasan hai — par yeh "biology" hai, seekhna padega. **Good news:** jab Terraform se karenge (Week 2 Day 4), yeh saari permission/policy code se automatic ho jaayegi — *"that's how people really do it in earnest."* Abhi manual way (jaise Terraform se pehle hota tha).

### Part 2: API Gateway

> **API Gateway** ek managed service hai jo tumhare Lambda function ke **upar baithta hai** aur use **outside world ke saamne expose** karta hai — routing, throttling, auth, CORS, custom domains, etc. handle karta hai. Lambda ko tum directly bhi expose kar sakte ho (Function URL), par API Gateway **more robust, enterprise-strength** tareeka hai.

#### API banao

1. Console → **API Gateway** search → **Create API** → **HTTP API** (**first option** — definitely yahi select karo, REST API nahi).
2. **Name:** `twin-API-gateway`.
3. **Next mat dabao** — **Add integration** dabao (routes baad mein bhi add kar sakte ho, par yeh easiest hai).
4. Integration type: **Lambda**, region: **us-east-1**, function: **`twin-API`** (sirf yahi dikhna chahiye). Yeh keh raha hai "yeh API us Lambda se integrated hoga." → **Next**.

#### Routes configure karo

Routes batate hain ki kaun-sa incoming request kis Lambda par jaaye (tumhare paas multiple Lambdas bhi ho sakte hain, isliye yeh mapping). Hamare case mein sab `twin-API` par:

| Method | Path | Integration |
|---|---|---|
| `ANY` | `/{proxy+}` (catch-all) | `twin-API` |
| `GET` | `/` (root) | `twin-API` |
| `GET` | `/health` | `twin-API` |
| `POST` | `/chat` | `twin-API` (**most important** — actual chat) |
| `OPTIONS` | `/{proxy+}` | `twin-API` (**CORS preflight ke liye must**) |

Ed ek-ek karke add karta hai:
- **`ANY` + catch-all path** → twin-API (default route).
- **`GET /`** → root request seedha pass.
- **`GET /health`** → health check.
- **`POST /chat`** → *"the one we really care the most about"* — yeh chat endpoint.
- **`OPTIONS /`** → yeh "fussy one" hai. Browser aur server **CORS negotiation** (preflight) ke liye OPTIONS request bhejta hai; ise include nahi karoge toh kuch kaam nahi karega. Bas add kar do.

5. **Configure stages** → defaults chhod do → **Review and create** → confirm sab routes twin-API par jaa rahe → **Create**.

#### CORS configure karo

> **CORS (Cross-Origin Resource Sharing)** browser ka security mechanism hai: ek origin (tumhari frontend website) doosre origin (API Gateway endpoint) ko call kare iske liye server ko explicitly **allow headers** bhejne padte hain, warna browser block kar deta hai.

1. Naye API mein → left menu **CORS** → **Configure**.
2. Settings (har value type karke **Add** dabana zaroori hai jahan multiple ho sakti hain):

   ```text
   Access-Control-Allow-Origin    : *      ← type "*" phir ADD button dabao (warna save nahi hoga!)
   Access-Control-Allow-Headers   : *      ← "*" phir ADD
   Access-Control-Allow-Methods   : *      ← "*" (yahan ek hi, Add nahi chahiye)
   Access-Control-Max-Age         : 300
   ```

   ⚠️ **Ed ki seething warning:** Origin/Headers mein `*` type karke **ADD button** dabana **zaroori** hai — sirf field mein type karke save karoge toh save nahi hoga aur ages lag jaayenge samajhne mein kya galat hai. (Methods mein single value isliye Add nahi chahiye.) **Max-Age = 300** (preflight cache seconds).
3. **Save** → "Successfully created".

### Part 3: Live test 🎉

1. API Gateway → apni API (`twin-API-gateway`) → sidebar mein **API itself** par click → right side par **invoke/endpoint URL** dikhega → Copy.
2. Naya browser window → endpoint URL ke aage **`/health`** lagao → Enter.
3. **Boom** — wapas aata hai:

   ```json
   { "status": "healthy", "use_s3": true }
   ```

Pehli request mein couple seconds lag sakte hain (**cold start** — Lambda launch hua). End-to-end kya hua:
- URL hit hui → Amazon endpoint → **API Gateway** ne dekha `GET /health` → integration `twin-API` Lambda → Lambda ne **FastAPI server spawn** kiya → `/health` route hit → response wapas. (Wahi response jo L42 mein manual test mein mila tha.)

Code mein `server.py` ke top par yeh health check response define hai (`status: healthy`, `use_s3`). **It actually works** — API → Lambda live hai.

**Side note (Ed):** pehle jab test kiya tha tab response mein extra `bedrock_model` field bhi dikhi thi — wo isliye ki usne galti se **course mein aage ka zip** upload kar diya tha. Sahi zip wapas upload karne par clean `/health` aaya. **Yeh demonstrate karta hai code update kitna easy hai — bas naya zip upload karo, code replace ho jaata hai.**

**Bottom line:** ab humare paas hain — **2 S3 buckets** (memory + frontend), **1 Lambda function**, aur **1 API Gateway** jo Lambda tak route karta hai. *"We're in the endgame now."*

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Frontend S3 bucket** | `twin-frontend-<account_id>` — poori static website host karega |
| **Block public access uncheck** | Website public dikhe iske liye; acknowledge box tick |
| **Static website hosting** | S3 files ko directly website ki tarah serve karta hai — index.html + 404.html |
| **Bucket policy** | Resource-based IAM policy; `Principal: *` + `s3:GetObject` = public read |
| **ARN + `/*`** | Resource identifier; `/*` se bucket ke saare objects par apply |
| **API Gateway (HTTP API)** | Lambda ke upar managed layer — routing/CORS/exposure |
| **Routes** | `ANY`, `GET /`, `GET /health`, `POST /chat`, `OPTIONS /` → sab `twin-API` |
| **`OPTIONS` route** | CORS preflight ke liye must — warna kuch kaam nahi karega |
| **CORS config** | Allow-Origin/Headers/Methods `*`, Max-Age 300 — **ADD button dabana zaroori** |
| **Cold start** | Pehli invocation par Lambda launch hone ka delay |
| **Live `/health`** | API Gateway → Lambda → FastAPI → `{status: healthy, use_s3: true}` |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture do classic production patterns dikhata hai. **(1) Static-frontend + API split:** frontend ko ek dumb static host (S3) se serve karna aur backend ko alag compute (Lambda) par rakhna — yeh "JAMstack / static-SPA + API" architecture hai, jo cheap, infinitely scalable, aur CDN-friendly (L44 mein CloudFront aayega). Tumhare backend instinct se ulta lag sakta hai (server HTML render nahi kar raha), par yeh decoupling hi modern norm hai. **(2) API Gateway = reverse proxy / API edge:** ise tum nginx/Kong/Envoy ka managed equivalent samjho — TLS termination, routing, throttling, CORS sab yahan. **Resource-based policy** (bucket policy) bhi note karo — IAM ke do flavours hain: identity-based (user/role par) aur resource-based (resource par, jaise yeh bucket policy ya SQS/SNS policies). **CORS** har full-stack backend dev ka classic dard — yaad rakho preflight (`OPTIONS`) ko server-side handle karna padta hai, aur `Allow-Origin: *` dev/demo ke liye theek par production mein specific origin chahiye (L45 mein refine hoga). Sabse important meta-lesson: Ed ne khud bola yeh saara manual click-ops **error-prone** hai — isiliye **Terraform** (Week 2 Day 4) aata hai, jahan yeh poora setup declarative, version-controlled, repeatable code ban jaata hai. Yeh exactly wahi IaC discipline hai jo har serious backend team adopt karti hai.

---

## ✅ Takeaway

- Frontend ke liye **doosra S3 bucket** banao: public access uncheck + **static website hosting** (index.html / 404.html) + **bucket policy** (`Principal: *`, `s3:GetObject`, ARN + `/*`).
- **API Gateway (HTTP API)** banao jo `twin-API` Lambda ko expose kare; routes: `ANY`, `GET /`, `GET /health`, `POST /chat`, aur CORS preflight ke liye `OPTIONS`.
- **CORS** mein Origin/Headers/Methods `*` + Max-Age 300 — `*` type karke **ADD button zaroor dabao**.
- Live endpoint par **`/health`** → `{status: healthy, use_s3: true}` = API → Lambda → FastAPI chain working (pehli baar cold start delay).
- Code update super easy: **naya zip upload = code replace**. Yeh saara manual click-ops baad mein **Terraform** se automate hoga.

---

<details>
<summary>📜 Full Transcript (English)</summary>

All right. We're about halfway through. I'm sure you must be like what? What's going on? Uh, keep on at it. And if this is too much, come back and do it a second time. We're now going to create another S3 bucket. Remember, there are two S3 buckets. One is a memory, the other is for the whole static front end site. We're going to do that next. We're going to create a new front end bucket. Uh it's going to be called twin front end. And then the random ID it's going to be in the same region. It needs to be in the same region. And we need to uncheck this block, all public access box. And you will see that in just a second. Let's go do this. So we're going to go back to S3. S3. This time you probably will see the same screen as me. Press Create bucket general purpose. We're going to call it twin dash front end dash. And now again we'll copy this in here. Copy. Come here and paste. There we go. Our account ID in there. Now we have to scroll down here and we have to uncheck block all public access because we want the world to see this. And we have to check this. I acknowledge, uh, that this will result in the bucket becoming public. Uh, we're happy with that. It's going to be our website. We want it to be public and everything else is good. And we say create bucket. Okay, there we go. Successfully created that bucket back. We go to our instructions now we now want to go to this bucket. Go to properties and edit the static web hosting um and enable static web hosting. And this is important. We're going to give it an index.html and 404 HTML as the index document in the errordocument. So let's go and do all of this. So come in here we edit our front end bucket. Here it is. We go to properties and we want to have this be a, um. I think it's all the way down here somewhere. Static website hosting. We edit this, we're going to say enable static website hosting. And we're going to say the index document is index dot HTML. The error document is 404 dot HTML. And this is all looking good. And we say save changes. Successfully edited static website hosting. Back we go. We did all this right I hope. Yes we did. And now we need to do more permission stuff. And this one is even more hokey than the last one. We're going to go to the permissions tab. And then under the bucket policy we have to click edit and add. In this policy there are sometimes you have to add in a policy that isn't one of the default settings. So this is allowing anyone in the public to access this bucket because we want this to be a public website. So we. We have to do this. And this feels super hokey, but it's what you do. This is just. The biology. It's one of the things you learn. Uh, the bucket policy, uh, is what we will now update to be this. Okay. So now we're going to do this permissions thing. We're going to go to permissions bucket policy. So here we are looking at our front end S3 buckets. We go to permissions. We're going to go to bucket policy right here. It's in this janky uh edit here. We've got this white box here we paste this in. And this time don't press save. We first have to change this bucket name to be the bucket name that we're trying to, uh, to make available. And conveniently enough, the bucket name is is right here. It needs it needs this this, uh, this on this account resource, uh, Amazon resource number. Uh, we can copy it right there and paste it in here. We need that slash star. And, uh, now with with this, we should be able to save changes. And it's worked. Uh, and remember to do this, you have to get this just right. It's it's so very hokey. It's so easy to get this wrong. Never fear, when we do this with Terraform, it's going to take care of all of this for us in code. And that's that's how people really do it, uh, in earnest. But this is something that we're doing the manual way for now, which is how we used to do before, before Terraform came along. So that has set up the right permission for us. Uh, I do believe. And we click save changes. So we're in good shape. We're moving on. We've done our S3 work. We're going on to the API gateway next okay. Next step is to create the API gateway. Remember, the API gateway is a piece that sits on top of our Lambda function and manages it. Being exposed to the outside world, you can actually expose Lambda functions directly, but this way is the more robust enterprise strength way of doing it. So we start by going back to the console. We will search for API gateway. There it is. When it first comes up for you, you might see something that's a bigger welcome screen because you don't have any. But there should be the create API in there. We're going to create an http API. This first option you need to definitely select that first option. We're going to call it twin API gateway. And then we don't press next. Press Add Integrations. You can actually go through and then do this later. But it's easiest to do it this way for the type of integration. It is a Lambda type of integration. It's in US East one. It's going to ask for the Lambda function and it prompts me and you should hopefully only see twin API, the real one that you've got, and that is your integration. It's saying this API is going to be integrated with that Lambda function. You press next. And now we're in this slightly hokey thing of setting up the routes, which is saying what what routes, what kinds of web requests when coming in. How should they get directed to the lambda function? Because you could have multiple lambda functions and choose to have an API gateway that sends different routes to different lambda functions. We don't have that situation, so we just have to quickly configure this to handle everything we need. So we're going to to first create a route. The method is any and this is the resource path. This is like a default route that we want to put in any. And then that path and integration to twin API. So let's do that first. So any that path and that integration target that's the first one. Great. So far so good. Next up we're going to go get just to the root. If someone tries to to hit the route with a Get request that should just be passed on directly like so that should go straight to our twin API. Add a route. Come back here. We're going to do another get to slash health. Sorry, I double clicked. Uh, we're going to do a get to slash health. That should go straight to twin API. I get to slash health and that should go to twin API. They're all going to go to twin API. Add another route. Back we go. Post to slash chat. This is the important one. Post to slash chat to slash that goes to twin API. That's the one that we really care the most about. Add one more route. And now this one is a fussy one. But we have to add one. That's called Method Options. And the path is again to wherever and then twin API. So we do options. To that goes to twin API. And that has set up our routes. This last one is to do with this thing called the cause the the browser and the server negotiating what it's allowed to do. And so you have to include that as well, or it doesn't work. Uh, but don't worry too much about it. Add it in. It's going to be great. All right. And then step three is to configure stages which will all be defaults. And then review and create. So let's go in and do this right now. Back we come we go next. This all looks great. Next review and create. Everything looks good. It's twin API gateway. It's connected to the twin API. Any goes straight to uh to an API. Get goes to an API, get goes to to health post to chat, goes in and options as well. That all looks perfect. Create. We are creating our API gateway. Marvelous. All right. And then we've got something final to set up around cause okay so in the newly created API we have to go to cause on the left click configure and add these settings star, star, star and 300 for origin headers and methods. Let me show you this. So first of all, it's going to be cause in the left menu right here, uh, and we are going to go to uh configure. Now this is a, this is a sneaky thing. You press star in here because it's meant to be star, but you don't just click over here and keep going. Nope. You have to press the add button and it appears down there. And if you don't do that, nothing will work and it will take you ages to figure out why. Ages. Uh, as you can imagine, this this might have happened to me. It might have taken me quite a while, and it might have made me seething. And if I get seething and I'm normally an upbeat kind of guy, I can't imagine what it's going to do to you. So to make sure you press the add button, uh, and then this is also needs to be star and add. This one is star, but you don't need to press add. It just goes there because you can only have one. And then this. This was. What was it I already forget, was it 30 or. I think it was, uh, 300, 300, uh, 300 for the max control age 300 and then save. Okay. Successfully created and all seems to be good. Uh oh. Look, I even put in a note there about that add button. Uh, it won't be saved if you don't press add. Okay, well, this is super exciting. It's time for us to test. Okay. Test time. So we go back to AWS. We go to the API gateway. We, uh, find our, uh, our API, which is right here, twin API gateway. You click on the left at the API itself in the sidebar right there. And over on the right. This is the endpoint that our API is running on. I copy that, I open a new browser window and I'm going to go Slash health and see what happens. And bam, look at that. What comes back is healthy. Use S3. True. Uh, how about that? That's kind of cool. Uh, it might have taken a couple of seconds for you because, uh, it had to launch the Lambda function. I actually just run it to make sure it was working. Uh, so it was really, really fast for me. But just so you understand, everything that happened there, this request here, this URL was hitting an Amazon endpoint that's connected to our API gateway that saw that we're running a Get request on the health endpoint. It saw that we had an integration to a Lambda function. So it passed control to that lambda function. That lambda function spawned a fast API server, and it launched that fast API server. And it hit the health route, much as we did when we tested manually through the, uh, the UI earlier. And when you do that, that health route responds like this. And if we go back to our code and we look in Server.py and we look up near the top. You'll see this health check, health response status. Healthy use S3, use S3. How about that? It works. It actually works. We have an API onto a Lambda function. And by the way, as a side note, if you're wondering why earlier when I did this once when we hit the server, we saw more than just status in S3. We saw like bedrock model, and you won't have seen that. Uh, that's because I'd, I'd uploaded a zip file from later in the course that has more information in there. Uh, whereas if I then went back and uploaded the zip file when I realized that's what had happened. And of course, we now do get exactly this health check as it should be, and it shows you actually uploading different zip files into that function. Super easy. Just upload a zip file and the new code gets replaced. So anyways, point is we've got ourselves two S3 buckets, a lambda function, and now an API gateway that can come through this lambda function where most of the way there. Now we're in the we're in the endgame.

</details>
