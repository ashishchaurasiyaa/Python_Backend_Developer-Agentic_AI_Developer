# L47 — Migrating from OpenAI to AWS Bedrock for Cost-Effective LLM Deployment

> **Week 2 · Day 3** · ⏱️ ~9 min

---

## 🎯 TL;DR

Pehle Nova ki **pricing** (per-1000-tokens, extremely cheap) samjhte hain, phir code migrate karte hain OpenAI se Bedrock par: `requirements.txt` se `openai` hatao, `server.py` mein **boto3 `bedrock-runtime` client** + `call_bedrock()` function, aur Lambda mein `BEDROCK_MODEL_ID` env var set karke execution role ko Bedrock permission dete hain.

---

## 🗣️ Hinglish Explanation

### Nova model pricing — bahut sasta

Costs hamesha matter karti hain. Nova models **very cheap** hain. OpenAI ke ulat yahan koi **upfront payment** nahi — sab kuch **AWS account par billed** hota hai (Ed personally pay-as-you-go prefer karta, par big cloud platforms aise nahi chalte).

Pricing dekhne ke liye **Amazon Bedrock pricing** page par jaao, model type select karo (Amazon), aur Amazon ke rates dekho. **Critical detail:**

> ⚠️ Bedrock pricing **per 1,000 tokens** mein quote hota hai — kai dusri sites **per 1 million tokens** mein. Isliye numbers itne chote dikhte hain. Hamesha confirm karo unit kya hai.

Practical math: ~1,000 input tokens ≈ ~750 words (lagbhag ek poori conversation, input + output milake). Tab:
- **Nova Micro**: ek conversation cost **radar par bhi nahi** — practically free
- **Nova Pro** (sabse mehenga Nova): ek conversation phir bhi sirf **~3/10 of a cent** — yaani ek cent kharch karne ke liye 3 hearty conversations chahiye

Ed Micro/Lite default suggest karta hai par khud Pro use karega "why not, it's so cheap." Hamesha tables par nazar rakho — prices change ho sakti hain aur **region-wise** alag ho sakti hain (sahi region select karo).

### Code Migration Step 1: `requirements.txt`

Pehla change — `requirements.txt`. Naya package add **nahi** karna; ek **remove** karna hai: **`openai`** hata do. Hum ab OpenAI Python client library use nahi karenge.

```diff
  fastapi
  uvicorn
  boto3
- openai
```

> 💡 **Good practice:** jo packages use nahi ho rahe unhe dependencies se hatao — smaller package, faster cold starts, kam attack surface. (Note: `boto3` add nahi karna pad raha kyunki woh pehle se hai — humne S3 ke liye already use kiya tha; Lambda runtime mein boto3 built-in bhi aata hai.)

### Code Migration Step 2: `backend/server.py`

`server.py` mein bahut saara code waisa hi rehta hai. Core/start same. Naye/changed parts:

**1. Bedrock client banao (boto3 se):**

```python
import os
import boto3

# pehle S3 ke liye boto3 client banaya tha; ab bedrock-runtime ke liye
bedrock = boto3.client(
    "bedrock-runtime",
    region_name=os.environ.get("AWS_REGION", "us-east-1"),
)

# konsa model use karna — env se ya yahan default badlo
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "amazon.nova-lite-v1:0"   # super-sasta ke liye nova-micro-v1:0 daal do
)
```

`boto3` AWS ka official Python SDK hai. `bedrock-runtime` woh service hai jo actual **inference** (model invoke) karti hai. Non-prod testing mein model ID ko Micro jaise sasta model par switch kar sakte ho.

**2. Conversation load** (locally ya S3 se) — bilkul same jaisa pehle tha.

**3. `call_bedrock()` function** — conversation history ke saath Bedrock call karta hai. Yahan thodi "janky" formatting hai — Bedrock ka message format OpenAI se alag hai:

```python
def call_bedrock(history):
    # OpenAI format se Bedrock format mein translate
    # System message ko as a user "system:" prefix message bhejte hain
    messages = []
    for msg in history:
        role = msg["role"]            # "user" ya "assistant"
        content = msg["content"]
        if role == "system":
            # bedrock system messages aise jaate hain
            messages.append({
                "role": "user",
                "content": [{"text": f"system: {content}"}],
            })
        else:
            messages.append({
                "role": role,          # user / assistant
                "content": [{"text": content}],
            })

    try:
        response = bedrock.converse(
            modelId=BEDROCK_MODEL_ID,
            messages=messages,
        )
        # response pydantic object NAHI — plain JSON/Python dict hai
        return response["output"]["message"]["content"][0]["text"]
    except Exception as e:
        # exception handling
        return f"Error calling Bedrock: {e}"
```

Key differences OpenAI se:
- **Content arrays hain** — har message ka `content` ek list of `{"text": ...}` blocks hai (string nahi)
- **System message ko alag tarah pass** karte hain (yahan `user` role mein `system:` prefix se)
- **Response ek plain dict hai**, OpenAI jaisa pydantic object nahi — `response["output"]["message"]["content"][0]["text"]` se text nikalte hain

Ed bolta hai yeh poora `call_bedrock` function jaisa-ka-taisa **copy-paste** kar sakte ho jab bhi Bedrock call karna ho — yeh ek reusable recipe hai.

**4. Health/root route (new):**

```python
@app.get("/")
def health():
    return {"status": "ok", "bedrock_model": BEDROCK_MODEL_ID}
```

> 😅 **Ed's earlier mistake explained:** Day 2 mein Lambda ke health-check mein `bedrock_model` field dikha tha — woh isliye kyunki Ed ne galti se **is change ke baad wala zip** upload kar diya tha (jo turant fix kar diya). Sharp viewers ne pakda — well done!

**5. `/chat` POST route** — pehle jaisa hi, bas andar OpenAI call ki jagah ab `call_bedrock()` use hota hai. Bas itne hi changes — ab Bedrock use karne ke liye ready hain.

### Code Migration Step 3: Lambda configuration

Ab Lambda ko in changes ke liye taiyaar karo.

**1. Model chuno aur ID copy karo:** Micro/Lite/Pro mein se ek pick karo (testing ke liye Micro/Lite). Ed **Nova Lite** use kar raha. Bedrock screen se **official model ID** copy karo, jaise:

```
amazon.nova-lite-v1:0     # ya amazon.nova-micro-v1:0 / amazon.nova-pro-v1:0
```

**2. `BEDROCK_MODEL_ID` env var set karo:**
1. Lambda console → **functions** → **twin-api**
2. **Configuration** → **Environment variables** → **Edit**
3. Pehle **OpenAI API key** wala env var **delete** karo — ab zaroorat nahi (Ed already kar chuka — "I was on to you")
4. **Add environment variable**: name `BEDROCK_MODEL_ID`, value = `amazon.nova-lite-v1:0`
5. **Save**

Baaki env vars (CORS, S3 bucket) ko bhi check kar lo ki sahi hain.

**3. Lambda execution role ko Bedrock permission do:** Yeh "nonsense" yaad hai? Lambda functions ki **apni permissions** hoti hain (execution role). Function ko Bedrock call karne ke liye explicit permission chahiye:
1. Lambda → **Configuration** → **Permissions**
2. **Execution role name** par click karo (yeh IAM role kholta hai jiske under Lambda chalta hai)
3. **Add permissions** → **Attach policies**
4. Bedrock access wali policy attach karo (jaise `AmazonBedrockFullAccess`)

> 💡 **Do alag permission layers:** Tumhari **IAM user/group** permissions (jo tumhe console se Bedrock use karne deti hain) aur **Lambda execution role** permissions (jo deployed function ko runtime par Bedrock call karne deti hain) **alag** cheezein hain. Dono chahiye. Yeh AWS ka common gotcha hai — "code sahi hai par Lambda Bedrock call nahi kar pa raha" matlab execution role mein permission missing hai.

Iske baad Lambda Bedrock-powered code ke saath production mein ready hai (agle lecture mein deploy + test).

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Bedrock pricing** | Per **1,000** tokens (per million nahi!) — Nova extremely cheap, AWS account par billed |
| **Nova cost** | Micro ~free per convo; Pro ~3/10 cent per convo — region-wise vary kar sakta hai |
| **Remove `openai`** | requirements.txt se hatao — unused dependency clean karna good practice |
| **boto3 `bedrock-runtime`** | AWS SDK client jo actual model inference (invoke) karta hai |
| **`BEDROCK_MODEL_ID`** | Env var jo decide karta hai konsa Nova model use ho (e.g. `amazon.nova-lite-v1:0`) |
| **`call_bedrock()`** | Reusable function — OpenAI format se Bedrock format translate + dict response parse |
| **Bedrock message format** | `content` ek list of `{"text": ...}` blocks; system message alag tarah; response = plain dict |
| **Lambda execution role** | Function ki apni IAM identity — runtime Bedrock call ke liye policy attach zaroori |
| **Two permission layers** | IAM user/group (console) ≠ Lambda execution role (runtime) — dono chahiye |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture ek classic **provider migration** hai — backend dev ke liye iska sabse value-dene wala sabak: **LLM provider ka abstraction layer banao.** Notice karo Ed ne pure call ko ek single `call_bedrock(history)` function mein wrap kiya — `/chat` route ko nahi pata andar OpenAI hai ya Bedrock. Yahi pattern (ek thin adapter function) provider switch ko ek-file change bana deta hai bajaye poore codebase ke. Production mein isse aur aage le jaao: ek interface/protocol define karo (`def generate(messages) -> str`) jiske alag implementations OpenAI, Bedrock, Anthropic ke liye ho — phir config se inject karo. Doosra critical point: **response shapes alag hote hain.** OpenAI pydantic objects deta hai (`.choices[0].message.content`), Bedrock raw dict (`["output"]["message"]["content"][0]["text"]`). Migration mein yahi parsing code 90% bugs ka source hota hai — defensive parsing aur exception handling lagao (jaisa Ed ne kiya). `requirements.txt` se unused `openai` hatana sirf hygiene nahi — Lambda mein chote dependencies = **chhote deployment package + faster cold starts**. Aur sabse important AWS lesson: **execution role permission** — yeh exactly woh jagah hai jahan "locally chal raha tha, Lambda mein break ho gaya" wale bugs aate hain. Local par tumhari `aws configure` credentials use hoti hain; Lambda mein function ki **execution role** — agar usme Bedrock policy nahi, to `AccessDeniedException` milega chahe code perfect ho.

---

## ✅ Takeaway

- Nova pricing **per 1,000 tokens** hai (per million nahi) — Micro practically free, Pro ~3/10 cent/conversation
- `requirements.txt` se **`openai` remove** karo — unused dependency hatana = smaller package, faster cold start
- `server.py` mein **boto3 `bedrock-runtime` client** + reusable **`call_bedrock()`** (format translate + dict parse)
- Bedrock message format OpenAI se alag: `content` = list of `{"text":...}`, response = plain dict
- Lambda: **`BEDROCK_MODEL_ID` env var** set + OpenAI key delete + **execution role** ko Bedrock policy attach (dono permission layers!)

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay. And next I just want to mention model pricing costs are always important. The Nova models are very cheap. Uh, and there isn't like an upfront payment or anything that people complain about with open AI. But, uh, by contrast, there is this idea that it just gets billed to your Amazon account. And so I got to tell you, I would prefer myself at like a pay as you go model, but that's not the way it works with the big cloud platforms. So, uh, for the latest pricing, there is this link here that will take you to the Amazon bedrock pricing. And you can look through here to see the different details. You scroll down. They've got these different links for each of the different types of models. Click on Amazon and we get to see the Amazon prices. Now this price is per 1000 input tokens. And some other sites you get per million input tokens. So it's worth keeping that in mind, which is one reason why they look so very small. But it is per 1000 not per million. So this is the input token cost. This is the output token cost. But nonetheless, if you look at these you'll see that they really are very small. If you think that maybe a thousand input tokens, which is about 750 words, think that that could be one conversation, uh, including the input and the output, perhaps then you can see that if you're using Micro One, conversation is not it's not on the radar, you know, like it's not even not even touching it. And in fact, even Amazon Pro like Nova Pro, you're still one conversation adding up that number and the output tokens, which wouldn't be that much anyway. It would be less than that. But you're still under you're like, uh, 3/10 of a cent. Uh, so you'd need to have three pretty hearty conversations to be able to spend a cent if you were using Nova Pro. And I'm going to suggest we default to using Micro and Lite, but I'm probably going to use Pro myself because why not? This is this is honestly so cheap compared to, uh, almost, almost anything else. So it's, uh, it's very good value. But always keep an eye on the prices in case they change. And in theory they could be different in different regions. So make sure you select the right region. That is about model pricing through bedrock. So keep an eye on those tables. And now it's time for us to use bedrock in our code. And that is going to be an exciting step for us okay. Time to change our code to work with bedrock. So, uh, first up we are going to make a change to requirements.txt. Uh, so we're changing our requirements.txt, but actually we don't have any new packages to add as part of this. So why are we changing requirements.txt? Well, it's because we have a package to remove. We are going to remove OpenAI. There we go. It's gone. Save. We're no longer going to be using the OpenAI Python client library. So we should take it out. Good coding practice to not include packages that we don't need Okay, back to day three. So now we have to update backend server.py to use bedrock. So plenty of code here. And nice and chunky server.py uh module. Let me copy all of this code across. I'm sure you're grateful I'm not typing this. That would take a long time, but I will explain it. Of course. Save. Okay, so what's changed a lot is the same. The the, uh, start with the core stuff is exactly the same. Here is something new. We're creating a bedrock client using the Boto3 Amazon library. Boto3 client. We used that before to get the S3 client. Here we are. We pass in the bedrock runtime, and we use the default AWS region that should be set in. Your EMV bedrock model is where we choose which model to use. And now, especially since we're in, uh, non-production environments at the moment, you can choose to change the bedrock model ID to something like micro with a super, super cheap one if you wish, and we will be setting this. You could set this in your EMV or you can change the default right there. Um, but this this is the, uh, the, the model that we will use. And then everything else here is the same. The same loading the conversation either locally or from S3. And now we have this call bedrock function, which calls bedrock with a conversation history. And you can see there's a little bit of janky stuff here. There's a way you have to do it to call bedrock, uh, for a user message. We're used to having OpenAI format role user content and then the user message. But in fact, this is the way that you send in system messages is like this role user content and then text system colon and then the prompt and role, uh, and then then either user or assistant content and then the message content. So that's this is the format to use. This is how we translate from the structure we're used to into the format that bedrock expects. And what comes back is not a pedantic object, it's just a JSON dictionary. So we take just a Python dictionary. So we take output message content, the first element text. And that gives us the text. So this is just something to to. You could copy and paste this anytime that you need to use bedrock or just use this whole function as is called bedrock as it is as your way to call bedrock. And then there's some exception handling there. Okay. And uh, this is these are all the same. This is the new health, uh, root I've added in here. Bedrock model with the bedrock model ID that's being used. And, and the people that are on the ball, uh, will remember this because this is what appeared in my health, uh, check before, which, uh, yeah, I sort of like I palm that off as, oh, that's something for the future. It didn't occur to me at that time. And the reason I saw that in Lambda before is because I uploaded the wrong zip file. I'd uploaded the zip file after making this change, which I of course fixed soon afterwards when I realized it. But if you caught that, then then well done. Uh, so, uh, rare mistake by me. Uh, the, um, I make 100 mistakes. I just rerecord the chat. The chat thing here, uh, is what we're used to. This is the big post chat. Uh, and this is where we do basically exactly the same. But there's this call bedrock in here using our core bedrock function to make the call to bedrock. And that's honestly, that is it. Those are the end of the changes. We are now ready to use bedrock. Okay. And it's time for us to now make the changes to Lambda to be ready for this. And the first thing is we might as well use the bedrock model ID uh, environment variable to choose which model we're going to use. So first of all pick one of these models. uh, pick either Micro Lite or Pro as the one that you would like to use for our testing purposes. You could start with micro. I'm going to use light for testing purposes, so then copy that model name. This is the official bedrock model ID that you can get from the bedrock screen. Um okay. And now we're looking to set an environment variable called bedrock model ID. Uh, and uh so we go back to our Lambda function functions, twin API. I'll just go back into Lambda. And then within Lambda we go to functions and then go to twin API. Here we have it. You go to configuration and then environment variables. And you might think oh no but I'm going to reveal my OpenAI API key. But no, I went in and I deleted that first because I was on to you. Uh, so you could do the same. You can delete your OpenAI API key because we don't need it anymore. Um, and instead we are now going to edit these and we're going to add an environment variable. It's called Bedrock model ID. And here we will paste in this value we'll use Nova Light. We'll save that. And that save has been made. That is now an environment variable associated with our lambda. Um and check that you're happy with all of the others are right for your environment. And now we are going to, uh, make sure remember this, this nonsense. We we need to make sure that our lambda function is allowed to call bedrock, because these lambda functions have permissions of their own. So we're going to have to go to our lambda function configuration permissions. Uh, do this business where we open the execution role name which is the the role that it executes under and then add permissions, attach policies and give it access to bedrock. So if you followed all that we're going to go here to configuration.

</details>
