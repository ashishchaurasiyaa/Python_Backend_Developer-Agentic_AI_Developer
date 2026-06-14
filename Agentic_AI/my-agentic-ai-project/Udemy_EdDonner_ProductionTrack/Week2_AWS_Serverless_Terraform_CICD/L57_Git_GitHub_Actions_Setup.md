# L57 — Setting Up Git and GitHub Actions for AI Production Deployments

> **Week 2 · Day 5** · ⏱️ ~10 min

---

## 🎯 TL;DR

Hands-on lab: `twin` project ko pehli baar ek **real git repo** mein convert karte hain — clean slate (destroy environments), final `.gitignore` + `.env.example` banao, nested sub-repos (frontend/backend ke `.git`) ko `rm -rf` se hatao, phir `git init -b main`, config, `git add .`, aur `git commit`.

---

## 🗣️ Hinglish Explanation

### Setup: kahan ho aur kya karna hai

Hum `twin` repo (abhi bhi sirf ek directory, ek "cursed project" — abhi tak repo nahi) mein hain. Week 2 → Day 5 folder kholo, uska preview kholo. Aaj hum **complete DevOps lifecycle** implement karenge — yaani project ko git aur GitHub mein daalna. Agar Day 5 folder na dikhe, toh shayad tum production repo dekh rahe ho (twin repo dekho).

> Note: agar `twin` folder na ho aur sirf `production` repo dikhe — galat repo mein ho.

### Step 1: Environment destroy karo — clean slate

Sabse pehle **dev, test, prod sab environments destroy** karo (`terraform destroy` ya deploy/destroy script se) — taaki bilkul clean slate se shuru karein. Ye pehle bhi kiya tha, par agar reh gaya ho toh ab kar lo.

Agar yakeen na ho ki clean slate hai, toh **AWS console** mein jaake verify karo (haan, console pasand nahi par check kar lo):

- Koi **Lambda** function nahi
- Koi **API Gateway / API** nahi
- Koi **CloudFront distribution** nahi
- Koi **S3 bucket** nahi

Sab khaali = good. Optionally Terraform **workspaces** bhi delete kar sakte ho (aaj locally kaam nahi karenge, isliye optional hai).

### Step 2: Final `.gitignore`

`.gitignore` git ko batati hai ki **kaun si files/folders commit mein NA include** karein. Humne pehle ek `.gitignore` banaaya tha; ab final version daalte hain. Ed ke decisions:

- Is final version mein Ed ne **Terraform state files include nahi kiye** (`.gitignore` mein nahi daale) — kyunki aaj kal state ko share/handle karna hai (next lectures mein remote backend dekhoge).
- **Lambda deployment zip/package** exclude — yeh build artifacts hain.
- **Local conversation history** exclude — varna pain ho jaata.
- **Environment variables** (`.env`) exclude — secrets repo mein nahi jaane chahiye.
- Lekin ek exception: `.env.example` **include** hoga (best practice — neeche dekho).
- **Frontend**: `node_modules` aur `out` (build output) directory exclude.
- **Python**: virtual environments (`.venv`), `__pycache__` etc.
- IDE files (`.idea`, `.vscode`) aur AWS local stuff bhi exclude.

```gitignore
# Terraform
.terraform/
# (Note: Ed kept .tfstate OUT of gitignore in final version — shared via remote backend)

# Lambda build artifacts
*.zip
package/

# Local conversation history
conversations/

# Environment variables — ignore all .env.* EXCEPT the example
.env
.env.*
!.env.example

# Frontend
node_modules/
out/
.next/

# Python
.venv/
__pycache__/
*.pyc

# IDE / OS
.idea/
.vscode/
.DS_Store

# AWS
.aws/
```

Yeh `.gitignore` repo banane ka achha first step hai.

### Step 3: `.env.example` — best practice

`.env.example` ek **example/template file** hoti hai jo doosron ko batati hai ki unhe apni `.env` file kaise set up karni hai (kaun se variables chahiye), **bina actual secrets share kiye**. Jo bhi tumhara repo clone karega, wo `.env.example` dekh ke samajh jaayega ki kya configure karna hai.

```bash
# .env.example — copy this to .env and fill in real values
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=
BEDROCK_MODEL_ID=amazon.nova-micro-v1:0
```

`.gitignore` mein humne `.env.*` ignore kiya par `!.env.example` se exception banaaya — isliye yeh ek file **commit ho jaayegi**. (Cursor mein new file → `.env.example` → example content paste.)

### Step 4: Nested sub-repos hatao (rm -rf gotcha)

Ek **chhota hitch**: jab humne frontend `create-next-app` se banaaya tha, wo by default **apna khud ka git repo** initialize kar deta hai. Toh `frontend` folder ek alag git repo hai — twin folder ke andar. Agar hum twin level par git repo banaayein, toh frontend ek **nested/sub-repo** ban jaayega (confusing aur problematic — git submodule jaisa mess).

Solution: frontend (aur backend, agar galti se `uv init` chalaaya ho `uv init --bare` ki jagah) ke andar ke `.git` folder ko **delete** karo:

```bash
# Mac/Linux — twin directory mein hokar chalao
rm -rf frontend/.git backend/.git 2>/dev/null
```

```powershell
# Windows PowerShell
Remove-Item -Recurse -Force frontend\.git, backend\.git -ErrorAction SilentlyContinue
```

⚠️ **rm -rf ka MASSIVE warning**: `rm -rf` ka matlab — folder aur uske **saare contents bina confirmation ke recursively delete** kar do. Yeh "famously the most dangerous command line thing you could ever do" hai. Spidey-sense alert raho:

- **Pehle confirm karo tum `twin` directory mein ho.**
- `rm -rf` ke baad jo aata hai (`frontend/.git backend/.git`) — wahi delete hota hai. **Mistype mat karo.**
- Galti se `rm -rf` top-level (`C:\` ya `/`) par chalaa diya toh poora system tabaah — *"that's on you, I will not be held responsible."*
- `2>/dev/null` (ya `-ErrorAction SilentlyContinue`) sirf isliye hai taaki agar backend ka `.git` na ho toh error na de.

Agar darr lage toh ChatGPT se help le ke manually `.git` folders dhundh ke delete kar sakte ho (Cursor mein hidden hote hain by default). Par yeh command easy way hai.

### Step 5: `git init -b main`

```bash
git init -b main
```

- `git init` → current directory mein ek **naya git repo** banata hai — internally ek **`.git` directory** create karke.
- `-b main` → **main branch ka naam `main`** rakho. Yeh aaj kal ka common default hai. Purane git versions `master` use karte the, par `main` zyada common ho gaya hai.

Cursor mein file colors ab status reflect karte hain: **dark gray** = git-ignored, **blue/green** = changed files jo commit hone hain.

### Step 6: Git config (identity)

```bash
git config user.name "Ed Donner"
git config user.email "you@example.com"
```

Yeh batata hai ki commits kis naam/email se attribute honge.

### Step 7: Status, stage, commit

Kabhi bhi `git status` se current state dekho:

```bash
git status
# On branch main, No commits yet, untracked files (red) ...
```

Sab files abhi **red** (untracked) hain. Inhe **stage** karo:

```bash
git add .
```

(`.` = current directory ke saare changes stage karo — commit ke liye taiyaar.) Ed bolta hai yeh git lesson nahi hai — guide mein links honge, including **"BJ" ke incredible online git book** ki recommendation.

Phir **commit** karo (staged files ko repo history mein save):

```bash
git commit -m "Initial commit"
```

`-m` = commit message. Commit ke baad `git status` clean dikhega. Ab project ek **proper local git repo** ban gaya hai — agle lecture mein ise GitHub par push karenge.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Clean slate** | Sab AWS resources destroy karke shuru karna — koi leftover infra nahi |
| **`.gitignore`** | Kaun si files commit se exclude karni hain |
| **`.env.example`** | Template env file — doosron ko bina secrets ke setup samjhaata hai |
| **Nested/sub-repo** | Ek repo ke andar doosra `.git` — confusing, git submodule mess |
| **`rm -rf`** | Recursively force-delete bina confirm; sabse dangerous command — careful! |
| **`git init -b main`** | Naya repo banao, main branch ka naam `main` |
| **`.git` directory** | Git ka internal storage — ek repo ki nishaani |
| **`git config user.name/email`** | Commits kis identity se attribute honge |
| **`git add .`** | Saare changes ko stage karo (commit ke liye ready) |
| **`git commit -m`** | Staged changes ko repo history mein save karo |
| **`git status`** | Current repo state — kya staged/untracked/changed hai |

---

## 💼 Backend Dev Ke Liye Note

Ye lab ek seasoned Python dev ke bhi roz-ke gotchas cover karti hai. Sabse bada lesson: `create-next-app` (aur kuch scaffolders, jaise `uv init` bina `--bare`) **automatically `.git` initialize** kar dete hain — isliye monorepo-style projects mein tum unknowingly nested repos paal lete ho, jo `git add` par silently submodule pointers ban jaate hain aur teammates ke clone par empty folders aate hain. Pehla habit: naya scaffolded folder add karne se pehle `find . -name .git -type d` chala ke nested repos detect karo. Doosra, `.env` vs `.env.example` pattern (ignore `.env.*` + `!.env.example` exception) har production Python repo ka standard hai — ye 12-factor "config in env" principle ko enforce karta hai aur accidental secret commits rokta hai (combine with `git-secrets`/`detect-secrets` pre-commit hook for real safety). Aur `rm -rf` ka discipline: hamesha pehle `pwd` se directory confirm karo, aur destructive commands ko script mein wrap karte waqt `set -euo pipefail` lagao taaki ek galat path silently aage na badhe.

---

## ✅ Takeaway

- Pehle **clean slate** — dev/test/prod destroy karo aur AWS console mein verify (no Lambda/gateway/CloudFront/S3)
- Final **`.gitignore`** + **`.env.example`** (ignore `.env.*` but `!.env.example`) banao — secrets out, template in
- **Nested `.git` repos hatao**: `rm -rf frontend/.git backend/.git` — par `rm -rf` ke saath EXTREME caution, pehle `twin` dir confirm karo
- Repo banao: `git init -b main` → `git config user.name/email` → `git add .` → `git commit -m "..."`
- `git status` baar-baar dekho; Cursor file colors (gray=ignored, blue=changed) status reflect karte hain

---

<details>
<summary>📜 Full Transcript (English)</summary>

And now here we are, back in Casa again for the last time this week. We are in the twin repo. You're going to miss this repo. It's not yet a repo. It's still just a directory, a cursed project. But very shortly it's going to be a true repo. Open up that week two folder and go to day five. If you don't have this folder, you may be going to the production repo instead. Open a preview of this and let's get at it. So welcome to the final day of week two. Today we're implementing the complete DevOps lifecycle. Uh, so now we're going to be be putting things in git and GitHub. So step one is about destroying the environment destroying dev test and prod. We did already do that. We've done that already. But if you didn't do it for some reason, now would be a good time to do it. We want to bring everything. We want to destroy all of the environment, to make absolutely sure that we're starting from a clean slate. And if you're unsure if you're in a clean slate, then now you should go into the AWS console. I know we dislike the AWS console now, but go in there anyway and just double check. You've got no Lambda, no gateway, no API, no no, no CloudFront distribution and no S3 buckets. And all is good. Okay, then, uh, it also tells you you could do this. This is this is optional. Deleting the Terraform workspaces. We won't be working locally today. Um, and yes, there's the verify clean slate that I mentioned. Okay. Now we're going to create a dot git ignore. We actually already created a dot git ignore there. But this one is now the final one. And so we'll just put this in there and then look at it. Um let me see. So dot git ignore uh paste that in. This is the final things that we want to ignore. Uh, actually it looks like. Yeah. So in my final version I've decided I'm not going to put any, uh, Terraform state files in there. These these are are all the pretty standard things to have. Um, and, uh, we're also, of course, excluding the Lambda deployment zip and package. These are the artifacts of the build process for Lambda. We obviously don't want to put our conversation, our local conversation history. That would be a pain. Make sure that we don't include environment variables. Do you remember I mentioned ages ago that there would be an environment variable we would check in? You might have been like, oh, that'd be uh, well, that would be we're going to make one called env example, which is just a nice best practice that you leave an example file there for, for, uh, future, uh, people that clone your repo. Um, these are the standard things to exclude for, for the front end. We don't want node modules, we don't want to output directory. And then normal Python excludes like virtual environments and then any IDE stuff and any AWS stuff. There we go. So there is a nice dot git ignore for us a good first step towards creating our repo. And actually yes, I should have mentioned, in case it's not obvious that that's what we're doing right now. We're creating an official GitHub repo right now. This is still just a project in that we've not actually ever pushed it to GitHub before. We could set up GitHub actions. We do need it to be a repo on GitHub. All right. Second step is just a nice best practice is to create a env example which will tell other people how they can set up their own env file. So I'm just going to copy this over here. New file dot example. There it is. Paste in that example contents A nice thing to put in your repo. And because of the way we did our dot git ignore because we ignore all dot env dot star except a dot env example, this file will in fact be included in the repo. Okay back here we go. All right. So next up there is a tiny hitch that I need to alert you to. And we've got a little little fix here for it. Uh, so when we initially set up our front end of this, of this, uh, platform, we use that create next app command and by default create next app. When it's setting everything up and configuring everything it does in fact create a GitHub repo for you. So the front end folder is itself a GitHub repo. So we have a repo within our parent folder within the twin folder. And that's confusing because if we create a GitHub repo at the twin level it will have like like what they call like a sub repo. It's going to have a repo within it. And that makes everything very confusing. So we actually want to remove the fact that the front end folder has a repo. And the back end folder should not be a repo, unless at some point you typed out a wrong instruction instead of uv init bare. If you did uv init, then it will also be a repo. So just to be safe, I've got like a command here that removes any repos from front end and back end. Um, and I've got that as a, as a command from for Mac and for PowerShell. We'll do that now just to make sure that we don't have any sub repos. Um, and if you're not entirely following what I'm saying, it doesn't matter that much. Just do this command. Uh, so, uh, the one reason why I say this to you is that this command has within it rm rf something, and any time that you type rm rf, you should have all of your Spidey sense alert. You should be really, really careful. The same goes for this equivalent, uh, command here. This is a this is famously the most dangerous of any possible command line thing you could ever do. Uh, I'm sure someone will have an exception, but that's the most dangerous that I know of. And you can Google it to read plenty of amusing stories of DevOps horrors where someone's managed to bring down their entire company by an improper use of rm rf. So rm rf means delete a folder and all its contents without asking for verification. Just do it. And do that recursively. And so you do have to be careful that what comes after the rm rf is what it's deleting. It's these two things front end and back end. Git and don't don't Mistype this. Make sure you take the whole line. Make sure you're in the twin folder. When you run this. I will not be held responsible. If anyone types RMI, RF and they're in their top level in C colon backslash that whoa that that's that's on you. So do this carefully in the twin directory. RM rf front end back end. And this this thing here is just to make sure that it doesn't, uh, complain if, uh, if it doesn't exist because the back end one won't exist for me anyway. And there we go. Done. Drama over. If that does worry you, then you can get ChatGPT help to actually just specifically go in and look for those dot git files. I think they're hidden by default in curses. You'd have to find them and then delete them manually. Um, but this is the easy way to do it. All right, enough. Let's get on and create a repo. Okay. Next command is the famous git init minus b main. So git init is setting up a new GitHub repo in the directory you're in. And that works by by basically creating a dot git directory. That's how it, how it does it. Um, the minus b main means that we want our main branch to be called main, and that is the common default. It would normally be that way anyway, but some older versions of git use master as the name of the main branch, but it's more common these days to use main as the name of the main branch. So that is what we will do here. So we're running git init minus b main and there we go. Initialized empty git repo in in and it gives us the directory of of the of the git. And uh you can see something that's happened here in cursor is that the colors here reflect the status of different files. The dark gray means it's git ignored. The blue means that these are things that are changed that need to be checked in. That's exciting. Uh, and now here's just a couple of quick configuration things we can say git config user name and then name. Add Donna and put your name obviously. And then uh git config user dot email. And I'll put my, my normal Gmail not. There we go. That one there. Done. Okay. We have got now a local git. There's the PowerShell commands. All right. In uh in a second we're going to to add these and commit them. So just before we run this you can also do git status at any point to get a sense of what's going on. We're on the branch main. There's been no commits. And we've got all of these red things that have not yet been added in any way to our repo. Uh, so now to, to to add them, to stage them for a for commits. You do git add dot and I'm not going to give a git lesson here. There will be this guide. There's links. There's a amazing amazing online book by a guy called BJ that writes the most incredible books. And he's so, so witty and so his manner is so wonderful. And he's got the guide to git that I've only read little bits of it. If you read all of that, you would know a lot more about git than me. So yeah, if you want to, if you want to follow this rabbit hole, then then that is the resource. All right. And now we do a git commit. We're committing commit commit the files that we've staged to be committed minus M is your message. And we will say well I'll just copy and paste this so that you're not standing there while I type. There we go. Done so. And now if I do a git status, it should all appear in fabulous. Oops. Oh yeah. That's right. It's all. It's all being created. So. So we are we are ready to go. Um, okay, let's do this. Next up it's going to be time to create our actual GitHub repo. Let's go and do that.

</details>
