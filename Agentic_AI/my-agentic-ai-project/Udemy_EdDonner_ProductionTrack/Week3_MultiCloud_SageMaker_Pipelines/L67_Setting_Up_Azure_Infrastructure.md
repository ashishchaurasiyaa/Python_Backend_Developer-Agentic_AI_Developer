# L67 — Setting Up Azure Infrastructure for Production AI Container Deployment

> **Week 3 · Day 1** · ⏱️ ~10 min

---

## 🎯 TL;DR

Part 0 (local container) khatam — ab **Part 1: Azure**. Free Azure account banao (~$200 credit), Azure ki hierarchy samjho (**Account → Subscription → Resource Group → Resources**), Cost Management mein **$10 monthly budget alert** set karo, ek **Resource Group (`cyber-analyzer-rg`)** banao, aur **Azure CLI (`az`)** install karke `az login` + verify karo. Azure ab deploy ke liye taiyaar.

---

## 🗣️ Hinglish Explanation

### Recap aur transition

Docker container ko `Ctrl+C` se band karo — `--rm` flag ki wajah se container run karne ke saath hi delete bhi ho jaayega. Band karte waqt **Semgrep results analysis** aur **health checks** ke logs dikhte hain (proof ki sab chal raha tha).

**Part 0 done** — foundation/groundwork: ek working app jo locally container mein chalta hai. Ab **Part 1: Azure**.

### Step 1: Azure account banao

1. Azure link kholo → **Try Azure for free**.
2. Sign up — **credit card** (sirf identity verify karne ke liye) + **phone number** chahiye.
3. **First time** sign up par credit milta hai — Ed ko **$200 credit for 30 days** mila. (Microsoft ke offers region ke hisaab se alag ho sakte hain.)
4. **Students** ke liye **Azure for Students** se aur zyada credit milta hai — zaroor check karo.

### Azure ki hierarchy (zaroori basics)

Portal mein jaane se pehle Azure ki organization samjho — yeh AWS se thodi alag hai:

| Level | Matlab |
|---|---|
| **Account** | Sabse upar — pura "tum" / poori entity |
| **Subscription** | Billing boundary — yahaan credit card attach hota hai (jaise "Azure for Students"). Account ke andar ek ya zyada subscriptions |
| **Resource Group (RG)** | Logical grouping — resources ko organize karne ka folder-jaisa construct. Hamari ek hi hogi: **`cyber-analyzer-rg`** |
| **Resources** | Actual cheezein — Container Apps, databases, storage, etc. |

AWS comparison: AWS mein **Account → Region → Services** flat-ish hota hai (resource group concept optional/tagging-based). Azure mein **Resource Group mandatory** hai — har resource kisi na kisi RG mein hota hai, jisse lifecycle management aur cost tracking easy ho jaati hai (poori RG ek saath delete kar sakte ho).

### Step 2: Portal explore karo

1. **portal.azure.com** kholo.
2. Pehli baar → **email confirm** karo.
3. **Login = passwordless flow** — Azure email par ek link bhejta hai, link click karne se logged in. (Password na maange toh confuse mat ho — yeh by design hai.)
4. Dashboard dikhta hai — Ed ko top par "**195 credit remaining**" (yaani $200 mein se thoda use). Search box upar (AWS jaisa), services neeche (familiar layout). Alag dikhta hai par AWS se concepts common hain.

### Step 3: Cost Management — budget alert ($10/month)

Free tier hone par bhi alerts zaroori — Ed ka consistent message: **apne kharche ka khud responsible raho.**

1. Search box → **Cost Management**.
2. Left sidebar → **Budgets** (yahaan budgets/alerts set hote hain).
3. **Scope** = full account → **Add**.
4. Budget configure:
   - **Name** (unique) — e.g. `monthly-budget-2`
   - **Reset period** = **Monthly** (har mahine spend track hoga)
   - **Creation date** (effective from) + **Expiration date** — ⚠️ **budgets expire hote hain!** Expiry door rakho, par yaad rakho ki expire hone par tracking band ho jaayegi — controls chahiye.
   - **Amount** = **$10/month** (itne se zyada nahi spend karna chahte)
   - **Next**.
5. **Alerts** set karo — kin situations mein email aaye:
   - **50% of budget** spend → email
   - **100% of budget** spend → email
   - **Forecasted 100%** → email (anumaanit spend budget tak pahunchne wala ho)
   - **Alert recipient** = apna **email** (bilkul sahi spelling — yeh critical line of defense hai)
   - Language default chhod do
6. **Create**.

Yeh ek important control hai par **replacement nahi** — Ed bolta hai khud bhi regularly aake Azure mein costs check karo (especially session ke end mein cleanup). Spend tiny aur free credits ke andar hona chahiye, par monitor karna **tumhari responsibility** hai.

### Step 4: Resource Group banao

RG = account ke andar top-level construct (resources ka container).

1. Portal → **hamburger menu** (☰) → **Resource Groups** → **Create**.
2. Configure:
   - **Subscription** — sirf ek hai, wahi select
   - **Name** = **`cyber-analyzer-rg`**
   - **Region** — sabse paas wala choose karo (AWS jaisa: US East/West, Europe, Asia). ⚠️ **Region yaad rakho aur sab cheez consistent rakho** — saare resources same region mein.
3. Create → ho gaya. **Resource Groups** par jaake `cyber-analyzer-rg` dikhega; click karne par empty RG khulta hai.

### Step 5: Azure CLI install karo

Jaise AWS ke liye AWS CLI (`aws configure`) install kiya tha, waise hi Azure ke liye `az` CLI chahiye.

**Mac:**

```bash
# Homebrew ke saath
brew install azure-cli
# ya installer download karo
```

**Windows:** installer download (MSI) — guide mein dono ke instructions hain.

**Verify:**

```bash
az --version       # Ed: 2.76.0 (tumhara newer ho sakta hai)
```

### Step 6: `az login` + verify

```bash
az login
```

Yeh browser kholega → authenticate karo → wapas terminal par done.

Quick checks:

```bash
# subscriptions table format mein dekho
az account list --output table
# -> "Azure subscription 1" + uska ID dikhega

# resource groups list karo
az group list --output table
# -> "cyber-analyzer-rg" dikhna chahiye
```

Output: **ek subscription** ("Azure subscription 1") jiske andar **ek resource group** (`cyber-analyzer-rg`). Successful.

**Azure setup done.** Ed bolta hai yeh AWS se thoda easier aur quick tha. Ab **Azure Container Apps par app deploy** karne ke liye taiyaar — agle lecture mein.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Azure free account** | Credit card + phone se verify; first-time ~$200 credit / 30 days |
| **Azure hierarchy** | Account → Subscription → Resource Group → Resources |
| **Subscription** | Billing boundary — credit card yahaan attach |
| **Resource Group (RG)** | Resources ka logical grouping (mandatory) — yahaan `cyber-analyzer-rg` |
| **Passwordless login** | Azure email par link bhejta hai, password nahi |
| **Cost Management → Budgets** | Spend track + email alerts (50% / 100% / forecasted 100%) |
| **Budget expiration** | Azure budgets expire hote hain — expiry ke baad tracking band |
| **Region consistency** | Saare resources same region mein rakho |
| **Azure CLI (`az`)** | Command-line tool; `az login` se authenticate |
| **`az account list` / `az group list`** | Subscriptions aur resource groups verify karne ke commands |

---

## 💼 Backend Dev Ke Liye Note

AWS ke baad Azure setup ek backend dev ke liye mostly **mapping exercise** hai — concepts same, naam alag. Sabse bada conceptual difference: **Resource Group**. AWS mein resources flat hote hain (region ke andar, tags se group karo), par Azure har resource ko ek RG mein force karta hai — yeh actually achha hai: ek RG poora environment represent kar sakta hai aur **ek command/click se sab delete** ho jaata hai (cost cleanup aur ephemeral environments ke liye perfect; Terraform `terraform destroy` ke saath bahut clean). Subscription ko **billing/security boundary** ki tarah socho — multi-tenant ya multi-team setups mein resource isolation isi level par hota hai. Production engineering ke perspective se do habits yahaan dohrayi gayi hain jo har cloud par lagti hain: (1) **billing alerts pehle din** set karo, runaway costs se bachne ka pehla bachaav; aur (2) **CLI + login flow** se infra programmatically manage karo — `az login` aage chalke Terraform ke Azure provider ko authenticate karega, exactly jaise `aws configure` ne AWS provider ko kiya tha. Passwordless email-link auth bhi note karo — yeh modern Azure AD (Entra ID) identity flow hai jise CI/CD mein service principals se replace kiya jaata hai.

---

## ✅ Takeaway

- **Part 1: Azure** shuru — pehle free account (~$200 credit, 30 din), credit card + phone se verify
- Azure hierarchy yaad rakho: **Account → Subscription → Resource Group → Resources**
- **$10 monthly budget alert** banao (50% / 100% / forecasted 100% par email) — budgets expire hote hain, dhyaan rakho
- Ek **Resource Group `cyber-analyzer-rg`** banao, region sabse paas wala + sab consistent
- **Azure CLI install** → `az login` → `az account list` / `az group list` se verify; ab ACA deploy ke liye ready

---

<details>
<summary>📜 Full Transcript (English)</summary>

And this is showing our Docker container in here. And you'll see a few things like you'll see the same grep results analysis again. And you'll see here the health checks going on. And I'm going to control C here. And that's going to stop the Docker container from running which will also delete it. And now we're going to press on and go to day one part one. That was part zero. The kind of foundation, the groundwork to have a working app running in a container locally. Let's now move on to part one Azure. So first of all, we've got to set up an Azure account. I'm assuming you don't have one already. If you do you can skip this little part. Uh, but first of all, uh, it's time to set up your Azure account by clicking here to launch Azure. And this is somewhere where you can try Azure for free by clicking there, which I have of course already done. And when you do this, uh, it takes you through to the screen to, to sign up and, uh, it knows that I'm already logged in, but the instructions that I give you in here will take you through what's necessary. Uh, you will need to provide a credit card to identify, uh, to to verify that you are. You say you are. And a phone number. And if this is your first time, I do believe that you will get credit. When I did it, I got, I think, $200 credit for 30 days. I believe that Microsoft has different offers for different regions, so it may not be identical for you, but if it is your first time, you should certainly be able to sign up for a free chunk. Uh, which I certainly did. If you're a student, then you may also qualify for, uh, Azure for students, and that gets you more credits. So definitely look out for that. And when you're done, you will come into the portal, which is where we will go next. Before we go there, just to give you some some Azure basics that you'll see when we go in there that there is you have an account which is which is the whole thing. Within that you have subscriptions like like Azure for students or something, but some kind of subscription which you have your credit card against, uh, like, like your billing boundary. And then under that you have a resource group, which is how you sort of organize things into logical groupings. We're just going to have one and it's going to be called Cyber Analyzer RG for resource group. And under that you have individual resources like we will have container apps. Uh so these are the the things subscription resource group and resources for you to look out for. And let's go in and check that out. Now we're also going to be looking at the cost management. So I'm going to start by clicking on Portal.azure.com so that we can get started. And here it goes. And it's coming in. It's working. And there we are. Now the first time you come in uh, confirm your email address. I'm not going to do that. Uh, the first time you come in, the way that you log in, it has a. Oh, look at that. I have 195 credit remaining, so I got my $200 of credit. This is what the dashboard looks like. Let me make that a bit bigger for you. You're familiar with the AWS dashboard. This is the Azure one. It's also got this search box up here which looks very familiar. It's got these services down here which are similar to before so that it looks different. But there's aspects in common which should be familiar to you. But this is your portal home for Azure. Uh, the way that it works, at least at least for me, is that I don't have a password. It's linked to my email, so it sends a link to my email that I link to show that I'm logged in as a passwordless flow, which is which is convenient. So if you're confused, well, you didn't have to enter a password. It's probably because of that. Anyway, let's set up the cost management. Even though you've got a free tier, hopefully we still want to make sure we've got alerts so that we stay on top of our costs. So we start by clicking in the search box right here. And we're going to go to Cost Management which uh, hopefully this is this is seeming very similar to you. It's very similar to AWS. Uh, but this time we look in this left sidebar here and we're going down to budgets. Budgets is where you set up the budgeting, the alerts that you want against different budget spend. Uh, and you can see I've set up a few here already. You won't have any um, the scope is for, for the full account I'm going to press add. And this is where I set up a budget. I want this to be we have to give it a unique name. Again very familiar with AWS. Let's call it monthly budget two because I think I've already got one. Yes. There we go. Uh, reset period. Make that monthly. That means that this will track every single month you'll spend. There's a creation date when this is effective from there's an expiration date. So these things expire. So, uh, it is important to, to keep an eye on this. Uh, I'm going to put this one right out there. I don't want this to expire anytime soon and recognize that that means that this will have a lifetime, and you need to have appropriate controls in place to make sure you do something once this budget has expired and you're no longer tracking it. And let's put in a $10 monthly budget is what we are concerned about. We want to make sure that we don't spend $10 a month. And with that, I press next. Okay, so now we set up our alerts. Like in what situations do we want to get emailed. Well, let's say we want to get emailed if we spend 50% of our budget. And we also want to get emailed if we spend 100% of our budget for sure. And in addition, at the point at which the forecasted amount is 100% of our budget, we also want to be alerted then to and I want it to send alerts to me at my email address. And as before, remember you got to get this email address right. Uh, this this is such an important, uh, line of defense. Uh, it appears to. Or we can leave the language at default. Um, and, uh, this is setting up our appropriate budgeting. So I press create. It's doing its thing. And this is making sure that we now have some controls in place, uh, to monitor our budget. But this should not replace your need to come back and check in Asia, as we will do at the end of this session to check the costs that you've incurred. It's your responsibility to manage your spend. It should, of course, be tiny and well within. Of course, the, the, uh, the free credits that you've got for your, your exploration with Asia. But you want to make sure that you're staying within that comfortably and you have to come back and check that regularly yourself. But for now, we've set up budget alerts, which is an important step, and we can move on with Asia. Okay, so back to the instructions. We've followed the cost management. There's some different description of percentages here. You should choose whatever that you like. It's time for us to make our first resource group. You remember that's the top level kind of construct under your account is are these resource groups. And you do that by going in the portal to the, the what they call the hamburger menu, selecting resource Groups and create. And what we're going to do is we're going to create a resource group. I've already created it. So you'll see that it's called Cyber Analyzer resource Group RG and choose the region that's closest to you. It's got regions just like AWS, and there is in the US and East and West. There's Europe, there's Asia. Uh, and you do need to remember the region and make sure everything is consistent. So let's go in and do that now. Okay. So we go to the hamburger menu and we go to resource groups. And here we go. You can see I've already got my resource group right there. There's a create button. That's the one that you will press. You'll create the resource group and follow the instructions. Get the right region. Uh, keep it under the the the the. If we go here, you'll see that there only is the one subscription. Keep it under that subscription. Give it a name like our name. And then that will be done. You will be, uh, you will have created your first resource group. And when you go to resource groups, you should see Cyber Analyzer RG in there. And if you click on it, uh, up will come that resource group looking just like that and nice and empty. That is where we are with our first and for today our only resource group in Azure. And next we have to install the command line interface for Azure just like we had AWS that interface. Remember we did AWS configure. To set it up we have to install one for Azure. And there is a simple installation instruction for Mac people. You can either use brew if you have homebrew, or you can download the installer. And you can do the same for windows PC types. Uh, we have the way that you can install, uh, just here. So that's the installation instructions for both. And once you've done that, if we bring up a terminal window I can go a Z or Z if you're American minus one version. And there we have it. Uh, we have Azure CLI. I have version 2.76.0. You might have a more recent version. And then we can connect to the CLI by typing AZ login. It will then open up a browser and you'll have to authenticate. And then you'll come back and you'll be done which I've already done. And, uh, then, uh, this this is just taking you through some quick things to, to to check. But we are just going to do this one here AZ account list minus minus output table. This should work. There we go. It shows the subscription that I've got called Azure Subscription one. And with its ID. And now we can do group lists. This is to show the resource groups. We should have one called Cyber Analyzer. Let's see. Here it is. We've got one resource group called Cyber Analyzer RG. And it's successful. So hopefully you're seeing the same. You've got one subscription under which there is one resource group. And that means with that that we are set up with Azure. It's I think that it's a little bit easier to set up than AWS was. It was pretty quick. Hopefully you found it that way too. We're now ready to actually deploy our app on Azure Container Apps. Coming up next.

</details>
