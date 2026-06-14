# L93 — Setting Up Aurora Database Infrastructure for Production AI Apps

> **Week 4 · Day 1** · ⏱️ ~6 min

---

## 🎯 TL;DR

`terraform apply` complete (~7-15 min) — Aurora cluster ready. CRITICAL step: Terraform outputs (cluster ARN + secret ARN wali 2 lines) ko **`.env`** mein copy karo. Phir `backend/database` mein **`uv run test_data_api`** se connection test (empty DB), **`uv run run_migrations.py`** se 17 migrations chalao (schema banao), aur **`uv run seed_data.py`** se 22 ETF instruments seed karo.

---

## 🗣️ Hinglish Explanation

### Apply complete — Aurora cluster ready

Ed ko **7 minutes** lage; tumhe **15 minutes tak** lag sakte hain — toh thoda wait karna padega. Ab tum apne **Aurora database cluster ke proud owner** ho.

### CRITICAL: outputs ko `.env` mein copy karo

*"Super important step — pay attention, mess this up and it could be trouble."*

Terraform apply ke output mein dikhega:
```
Apply complete! Resources: 11 added, 0 changed, 0 destroyed.

Outputs:

cluster_arn = "arn:aws:rds:us-east-1:<ACCOUNT>:cluster:alex-..."
endpoint    = "alex-...rds.amazonaws.com"
secret_arn  = "arn:aws:secretsmanager:us-east-1:<ACCOUNT>:secret:..."
```

Outputs mein hain: **cluster ARN** (Amazon Resource Number), **endpoint**, aur **secret ARN** (Secrets Manager location). Niche scroll karo — guide bolta hai **"add the following to your .env file"** aur **2 rows** deta hai (ek secret with your AWS account number, aur ek credentials detail).

Steps:
1. Yeh **2 lines exactly as-is** copy karo
2. Project **root** ki **`.env`** file mein paste karo
3. **Save karo** — `Cmd+S` / `Ctrl+S` (warna save nahi hoga!)
4. **Carefully** copy karo — koi character miss na ho

> Ed apni `.env` click nahi karta kyunki secrets dikh jaayenge. Tum apni mein paste karo.

```bash
# .env (project root) — example shape
DB_CLUSTER_ARN=arn:aws:rds:us-east-1:123456789012:cluster:alex-db
DB_SECRET_ARN=arn:aws:secretsmanager:us-east-1:123456789012:secret:alex-db-credentials-xxxx
```

### Database test karo

Naya terminal (ya wahi, par root directory par wapas jao):

```bash
cd backend
cd database          # yeh ek UV project hai
uv run test_data_api
```

- Yeh nayi Aurora database se connect karne ki koshish karta hai
- DB **there** hai par **"no tables found"** — empty hai (apparently **7 MB** apne emptiness mein!)
- Toh connection successful — `uv run test_data_api` ke through Aurora reach ho gaya

**`test_data_api` kya karta hai?** Yeh basically ek script hai jo tests karta hai — `RDS client → describe_db_clusters` (jo humne khud try kiya tha) jaise typical AWS functions code se call karta hai. Tum `database` directory mein jaake `TestDataAPI` class dekh sakte ho.

### Leap of faith: code par focus nahi, deployment par

Ed clarify karta hai: agle kuch din mostly **deployment aspects** par focus honge, **software writing par kam**. Code khud (database stuff) ya toh tum kar sakte ho ya general database coding hai.

`src` directory mein actual database code hai jisme **schemas** hain — yeh data model describe karta hai (different data types, schema setup). Yeh **boilerplate Python code** hai.

Ed admit karta hai: iska bada hissa **Claude Code** ne uske direction mein likha — wo document likhta tha, Claude likhta tha, wo wapas check karta tha. Database tables define karna Claude Code "very quick, very good" karta hai. **~60% Claude Code, 40% Ed.** Tum bhi Cursor agent / Claude Code se generate kara sakte ho, ya khud likh sakte ho agar schema-building mein proficient ho. **Course ka purpose deployment hai, building nahi.**

### Migrations chalao (schema banao)

```bash
uv run run_migrations.py
```

Output:
```
Migration complete: 17 successful, 0 errors. All migrations completed successfully.
```

Yeh saara setup + migration karta hai — schema (tables) Aurora mein ban jaata hai.

### Seed data — reference instruments

Ek **instruments table** hai jise popular **ETFs** (Exchange Traded Funds — jaise **SPY**, jo bahut log retirement funds mein rakhte hain) se populate karna hai:

```bash
uv run seed_data.py
```

Output:
```
Setting up 22 instruments... Seed data loaded successfully.
```

Yeh **22 instruments** ka reference data set kar deta hai. (Aur finally test data set hoga — ek fake user + fake account data — jo agle lecture L94 mein cover hota hai.)

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Terraform outputs** | apply ke baad cluster ARN, endpoint, secret ARN print hote hain |
| **`.env` copy step** | 2 output lines (cluster + secret ARN) ko project root `.env` mein daalna — critical |
| **ARN** | Amazon Resource Number — har AWS resource ka unique identifier |
| **test_data_api** | UV script jo Aurora se connect hota hai (RDS client → describe_db_clusters) |
| **uv run** | UV project mein script chalane ka command (Python env auto-managed) |
| **run_migrations.py** | Schema/tables banata hai — 17 migrations |
| **seed_data.py** | Reference data load karta hai — 22 ETF instruments (jaise SPY) |
| **schemas (src/)** | Data model definition — tables, data types (boilerplate Python) |
| **ETF / SPY** | Exchange Traded Fund; SPY = popular S&P 500 ETF |

---

## 💼 Backend Dev Ke Liye Note

Yeh poora flow tumhare familiar **DB bootstrap pipeline** ka mirror hai. Terraform **outputs → `.env`** = infra provisioning ke baad connection params ko app config mein wire karna (jaise CI ek RDS endpoint output karke deploy step ko pass karta hai). **Cluster ARN + secret ARN** ka matlab — Aurora **Data API** use ho raha hai (HTTP-based SQL, IAM/Secrets Manager auth), na ki direct TCP connection — isliye host/port/password ke bajaay ARNs chahiye. Yeh serverless-friendly hai: Lambda ko persistent DB connection pool maintain nahi karna padta (jo Lambda + RDS ka classic pain point hai).

**`run_migrations.py`** = schema migrations — bilkul Alembic/Flyway/Django migrations jaisa, idempotent versioned changes ("17 successful"). **`seed_data.py`** = reference/lookup data seeding (instruments = master data), jise tum fixtures ya seed scripts se karte ho. Aur Ed ka **"60% Claude Code"** admission ek real practical signal hai: boilerplate schema/CRUD/migration code AI se generate karwana standard ho gaya hai — par **review + verify** (wo "come back and check it" wala step) abhi bhi engineer ki responsibility hai. Production mein migrations CI/CD pipeline mein run hote hain, manually nahi.

---

## ✅ Takeaway

- `terraform apply` (~7-15 min) → **11 resources added** → Aurora cluster ready
- **CRITICAL**: Terraform outputs ki **2 lines (cluster ARN + secret ARN)** ko project root `.env` mein **carefully copy + save** karo
- `cd backend/database` → **`uv run test_data_api`** → connection test (empty DB, ~7 MB)
- **`uv run run_migrations.py`** → schema banao (17 migrations, 0 errors)
- **`uv run seed_data.py`** → 22 ETF instruments (jaise SPY) seed
- Database code ~60% Claude Code-generated; focus **deployment** par hai, building par nahi

---

<details>
<summary>📜 Full Transcript (English)</summary>

And welcome back. It actually it took seven minutes to create for me and it might take like 15 minutes. So you might be waiting for a bit there, but you should now be the proud owner of your own Aurora database cluster. And now there's a super important step. And you have to pay attention here because you messed this up. Then it could be trouble. So don't. Uh, so what we have to do is we have to add a couple of of variables from this into our env file. And we're going to be using these in various places. So so you need to be careful about this. So what I'm showing here I'm going to make this a bit larger. This is the output of the Terraform. It completed. Apply complete resources 11 added. And here are the outputs. And you can see it's got the various outputs which includes the cluster Arn, the Amazon resource number, the endpoint and a secret Arn Secrets Manager location of a secret. And if you keep going down you'll see here that there it says add the following to your EMV file. And there's two rows here that includes a secret to be added with your Amazon account number in it, and a sort of credentials detail here. And what you have to do is you're going to need to take these two rows here exactly as they are here, and copy that and paste it into the dot EMV file in your project root, which is of course over here. It's there. I'm not going to click on it or you'll see on my secrets. Wouldn't want that, but you should click on it. You should copy these two lines, paste it in your EMV file. Be sure to save. You have to press command S or control S to save it. And as it says, copy them carefully. Be sure about that and then we will move on. So the next thing we're going to do is now test our new database. So I'm going to bring up a new terminal window. You can use the one you've already got if you wish. You just have to be sure to go back to the directory to your root directory. And then you're going to go CD backend. Let's go into the backend end folder. We're going to this folder right here. And we're going to go into the database subdirectory. CD database. Here we are. We're in database. And what we're going to do now is you've run because this is a UV directory. This is a UV project in here. So we can do UV run test underscore data underscore API which is going to try connecting to a new aurora database to see if it's there. And it is there and it's uh, apparently no tables found. It's empty. It's seven megabytes long in its emptiness, apparently. Uh, so there we do indeed have an aurora database that we have connected to through the UV run Test Data API. Now, I hear what you're thinking. You're thinking, hang on a second. So what does Test Data API actually do? And if we're just about to, as it tells us to, to set up a database, what tables are we going to be creating. And herein lies something which which again I'm going to have to to to suggest that you take a bit of a leap of faith with me during the next few days. We've got a lot to do, and I'm going to be focusing most of what I discuss on the deployment aspects and what it takes to deploy this to production. The code itself, this is going to be less about actually writing the software, because that's some stuff we cover in other courses. And besides, I'm I'm imagining that this is a part that you can do or that's just general database coding should you wish. You can, of course, come in to the database directory and you can look at things like the Test Data API class. Let me give it a bit more space. And you can see that it is basically just a sort of script that goes through and does various tests and creates. It goes to RDS client described DB clusters, which we had tried ourselves before. Uh, and you can see everything that it does in code here and see how you can call typical AWS functions through code. And then more importantly, you can see that there's a source, an src directory here where I've put in the actual database code we're going to be using which includes schemas. And this is where it actually describes the data model that we're going to be using. And you can see that it's got the different different data types we'll be using. And you can see how it sets up the different schema that we'll be using. So this is all quite boilerplate Python code. And I should mention that a large amount of this was written by Claude code under my direction I'd write a document, I get it to write it, I come back and check it. And it's the kind of thing when it comes to things like defining database tables, that it's very quick, very good at doing. So. You could also generate this by by asking either the cursor agent or Claude code to do it. Or if you're already proficient at building database schemas, then you could do it yourself and take a look through what I've got here. It's probably like 60% Claude code, 40% me. But it's not the purpose of the course. The purpose of the course is now about deploying it. So what we're now going to do is run the script, which is going to set up all of our data in our Aurora database, and then we'll look at it. So here we are. Uh, it's now going to be time to run the database migration, which sets everything up. And as I say, you can go and read this class and see what it does. So we are now going to do UV run. Run migrations.py and off it goes and you'll see it's going to do a lot of different setup and migration. Complete 17 successful zero errors, all migrations completed successfully. So that has set up the data. And now we're going to populate our tables. In particular there's an instruments table which we want to populate with lots of popular ETFs which are finance people like like exchange traded funds like like spy that a lot of people have in their retirement funds. So we'll set up all of this reference data by doing UV run seed data dot pi. And you can look through this, look at it going as it sets up 22 instruments, seed data loaded successfully. And that has happened. And uh, finally we're going to set up some test data that we'll be using over the next few days, which will set up like a fake user and some fake data that that user will have in their account.

</details>
