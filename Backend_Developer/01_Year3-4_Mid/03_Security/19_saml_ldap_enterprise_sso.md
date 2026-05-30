# Enterprise SSO — SAML 2.0 + LDAP / Active Directory
**Security · Year 3-4 | Senior Backend + Agentic AI**

## Quick Concepts

**WHAT:**
- **Enterprise SSO** = ek baar IdP pe login karo, saare connected SaaS apps khul jaate hain (workforce identity)
- **SAML 2.0** = XML-based protocol jismein IdP signed **assertions** bhejta hai SP ko (browser ke through)
- **IdP (Identity Provider)** = jahan user authenticate hota hai → Okta, Azure AD / Entra ID, ADFS, Ping, OneLogin
- **SP (Service Provider)** = tumhari app jo identity consume karti hai
- **Assertion** = XML statement: "yeh user authenticate ho gaya, yeh uske attributes hain" (signed)
- **ACS (Assertion Consumer Service)** = SP ka endpoint jahan IdP signed SAMLResponse POST karta hai
- **AuthnRequest** = SP ka request IdP ko: "is user ko authenticate karo"
- **RelayState** = opaque round-trip value (original deep-link / CSRF-style state)
- **Metadata** = XML doc jo entityID, endpoints (ACS, SSO URL), aur signing certs describe karta hai
- **LDAP** = Lightweight Directory Access Protocol — directory service query/auth karne ka protocol
- **Active Directory (AD)** = Microsoft ka directory (LDAP + Kerberos + DNS); enterprise mein ubiquitous
- **DN (Distinguished Name)** = directory entry ka unique path, e.g. `cn=ashish,ou=eng,dc=acme,dc=com`
- **Bind** = LDAP ka authentication operation (credentials se connection authenticate karna)

**WHY enterprise SSO (B2B / workforce):**
- ✅ IdP-managed identity — IT admin ek jagah se users provision / deprovision karta hai
- ✅ Employee resign → IdP se disable → saare apps se access instantly gone (kill-switch)
- ✅ One login across 50+ SaaS tools (Salesforce, Slack, Jira, tumhari app)
- ✅ Compliance: centralized audit, MFA enforcement, conditional access policies IdP pe
- ✅ B2B deals mein "SAML SSO support" often a hard procurement requirement hota hai

**WHERE it fits vs OAuth2/OIDC (jo repo already padha chuka hai):**
```
OAuth2 / OIDC  →  consumer + modern + mobile + API delegation
                  ("Login with Google", JSON/JWT, /authorize + /token)
                  → padho: 01_jwt_oauth2_rbac.md, 04_oauth2_flows_deep.md

SAML 2.0       →  enterprise workforce SSO, legacy, B2B
                  XML assertions, browser-redirect POST, no tokens for APIs
                  → IdP-managed, IT controls the directory

LDAP / AD      →  the source of truth BEHIND the IdP
                  (or direct auth for on-prem internal apps)
```
> Senior framing: **SAML = federation protocol** (cross-org, browser). **LDAP = directory protocol** (query/auth a user store). IdP (Okta/Azure AD) often *reads* an LDAP/AD directory internally, then *speaks* SAML/OIDC outward to your app.

---

## Why This Shows Up in Senior Interviews

```
"Onboard a Fortune-500 customer who demands SSO into our SaaS."
   → Answer: SAML 2.0 SP integration (their IdP = Okta/Azure AD).

"Authenticate employees against the company's on-prem user store."
   → Answer: LDAP/AD bind (search-then-bind) over LDAPS.

"OIDC bhi to hai, SAML kyun?"
   → Enterprise IdPs + legacy apps + procurement checklists still
     SAML-first. Many B2B buyers gate the deal on SAML.
```

---

## SAML 2.0 — The Actors & Flows

### Roles

```
IdP (Identity Provider)            SP (Service Provider)
─────────────────────              ─────────────────────
Okta / Azure AD (Entra ID)         Tumhari app (the SaaS)
ADFS / Ping / OneLogin             entityID = https://app.acme.com
Authenticates the user             Consumes the assertion
Signs the assertion                Validates signature + conditions
Holds signing private key          Holds IdP's public cert (from metadata)
```

### SP-initiated vs IdP-initiated

```
SP-initiated (preferred, secure):
   User app.acme.com pe jaata hai → SP detect karta hai "not logged in"
   → SP AuthnRequest banata hai → IdP pe redirect
   → IdP authenticate → signed response wapas SP ke ACS pe
   → InResponseTo se request-response correlate hota hai ✅

IdP-initiated (Okta dashboard "chiclet" click):
   User pehle IdP pe login → app icon click → IdP directly
   unsolicited SAMLResponse SP ke ACS pe POST kar deta hai
   → NO AuthnRequest, so InResponseTo MUST be absent
   → CSRF/replay surface zyada → high-security apps disable this
```

### Full SP-initiated Flow (the one to memorize)

```
   Browser                 SP (your app)                 IdP (Okta/Azure AD)
     │                          │                              │
     │ 1. GET /dashboard        │                              │
     │─────────────────────────►│  not authenticated           │
     │                          │  build <AuthnRequest>        │
     │                          │  store RelayState + reqID    │
     │ 2. 302 redirect to IdP SSO URL                          │
     │    ?SAMLRequest=<deflate+b64>&RelayState=/dashboard     │
     │◄─────────────────────────│                              │
     │                                                         │
     │ 3. GET IdP SSO URL (HTTP-Redirect binding)              │
     │────────────────────────────────────────────────────────►│
     │                                                         │
     │ 4. User authenticates (password + MFA, conditional acc.) │
     │◄────────────────────────────────────────────────────────│
     │                                                         │
     │ 5. IdP builds SIGNED <Response> containing <Assertion>  │
     │    auto-submitting HTML <form> → HTTP-POST binding      │
     │◄────────────────────────────────────────────────────────│
     │                                                         │
     │ 6. POST /saml/acs                                       │
     │    SAMLResponse=<base64 XML>&RelayState=/dashboard      │
     │─────────────────────────►│                              │
     │                          │  VALIDATE:                   │
     │                          │   - XML signature (IdP cert) │
     │                          │   - Issuer == IdP entityID   │
     │                          │   - Audience == SP entityID  │
     │                          │   - Conditions NotBefore/    │
     │                          │     NotOnOrAfter (clock)     │
     │                          │   - InResponseTo == reqID    │
     │                          │   - assertion ID not replayed│
     │                          │  extract NameID + attributes │
     │                          │  create LOCAL session        │
     │ 7. 302 → RelayState (/dashboard), Set-Cookie session    │
     │◄─────────────────────────│                              │
```

> Key insight: SAML data **browser ke through** travels (front-channel). SP aur IdP ka koi direct back-channel call nahi hota (unlike OAuth's `/token`). Isliye assertion ka **signature** hi trust ka foundation hai.

### Bindings — HTTP-Redirect vs HTTP-POST

```
HTTP-Redirect binding:
   - Message DEFLATE-compressed + base64 + URL-encoded in query string
   - Used for the AuthnRequest (SP → IdP) — small payload
   - Signature is a detached query param (SigAlg + Signature)

HTTP-POST binding:
   - Message base64-encoded inside an auto-submitting HTML <form>
   - Used for the SAMLResponse (IdP → SP) — assertion is large
   - Signature is XML-DSig *inside* the XML (enveloped)
```

### Metadata Exchange (setup-time)

```
Dono sides metadata XML exchange karte hain (ek baar, onboarding pe):

SP metadata (you publish):
   - entityID            (your unique ID, e.g. https://app.acme.com)
   - ACS URL + binding   (where IdP posts the response)
   - SP signing cert     (if you sign AuthnRequests)
   - NameIDFormat        (emailAddress / persistent / transient)

IdP metadata (they give you):
   - entityID            (IdP's unique ID → becomes expected Issuer)
   - SSO URL             (where you redirect the AuthnRequest)
   - IdP signing cert(s) (used to VERIFY assertion signature)  ⭐
```

### XML Signing & Encryption (XML-DSig / XML-Enc)

```
Signing (mandatory in practice):
   - IdP assertion ko apni PRIVATE key se sign karta hai
   - SP IdP ki PUBLIC cert (metadata se) se verify karta hai
   - Sign the <Assertion>, the <Response>, ya dono — SP must require it

Encryption (optional):
   - <EncryptedAssertion> — SP ke public key se encrypt
   - Needed jab attributes sensitive ho aur TLS-only trust kaafi na ho
   - SP apni private key se decrypt karta hai
```

---

## SAML Security Pitfalls (interview gold)

### XML Signature Wrapping (XSW)

```
The #1 SAML attack class. Idea:
   - Attacker ek VALID signed assertion leta hai
   - XML tree ko manipulate karta hai: signed element ko move/wrap karke
     ek NAYA forged assertion inject karta hai
   - Buggy SP signature ko "valid" maanta hai (kyunki original signed
     blob abhi bhi document mein present hai) but identity NAYE
     unsigned/forged element se padhta hai
   → Attacker kisi bhi user ke roop mein login kar leta hai
```

**Defenses (a vetted library does these for you):**
```
✓ Signature ko EXACT element pe validate karo, fir SAME element se
  hi data padho (no "validate here, read there" mismatch)
✓ Schema-validate the XML; reject unexpected/extra elements
✓ Reference URI ko resolve karke confirm karo signed node = data node
✓ Canonicalization (C14N) sahi se apply karo
```

### The MUST-validate checklist

```
SAMLResponse accept karne se pehle SP ko verify karna HAI:
   1. XML signature valid (IdP ki public cert se)            ⭐
   2. Issuer == expected IdP entityID
   3. Audience (in <Conditions><AudienceRestriction>) == SP entityID
   4. Conditions NotBefore <= now <= NotOnOrAfter (+ small clock skew)
   5. SubjectConfirmation Recipient == your ACS URL
   6. SubjectConfirmationData NotOnOrAfter not expired
   7. InResponseTo == the AuthnRequest ID you issued
        (and for IdP-initiated, InResponseTo MUST be absent)
   8. Replay protection: assertion ID seen-before? → reject
        (cache used IDs until their NotOnOrAfter)
```

> **NEVER parse SAML XML by hand.** XSW, XXE, canonicalization, namespace edge-cases — yeh sab ek battle-tested library ka kaam hai. Roll-your-own = guaranteed CVE.

---

## Python — SP Side with `python3-saml` (OneLogin)

```bash
# pip install python3-saml ldap3
# python3-saml depends on lxml + xmlsec (libxml2/xmlsec1 system libs)
# Ubuntu: apt-get install libxml2-dev libxmlsec1-dev libxmlsec1-openssl pkg-config
```

### Settings (`saml/settings.json` style)

```python
# saml_settings.py
# python3-saml ek dict (ya JSON) leta hai jo SP + IdP describe karta hai.

SAML_SETTINGS = {
    "strict": True,        # ⭐ ALWAYS True in prod — enforces all validations
    "debug": False,

    "sp": {
        "entityId": "https://app.acme.com/saml/metadata",
        "assertionConsumerService": {
            "url": "https://app.acme.com/saml/acs",
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
        },
        "singleLogoutService": {
            "url": "https://app.acme.com/saml/sls",
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
        },
        "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        # SP key/cert — needed if you sign AuthnRequests or decrypt assertions
        "x509cert": "",
        "privateKey": "",
    },

    "idp": {
        # Yeh sab IdP ke metadata XML se aata hai (Okta/Azure AD se download)
        "entityId": "https://idp.okta.com/exk1abcd",      # becomes expected Issuer
        "singleSignOnService": {
            "url": "https://acme.okta.com/app/.../sso/saml",
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
        },
        "singleLogoutService": {
            "url": "https://acme.okta.com/app/.../slo/saml",
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
        },
        "x509cert": "MIID...IdP_SIGNING_CERT...AB",        # ⭐ verifies assertions
    },

    "security": {
        "wantAssertionsSigned": True,       # require signed <Assertion>
        "wantMessagesSigned": False,        # optionally require signed <Response>
        "wantNameId": True,
        "requestedAuthnContext": True,
        "rejectUnsolicitedResponsesWithInResponseTo": True,
        "signatureAlgorithm": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
        "digestAlgorithm": "http://www.w3.org/2001/04/xmlenc#sha256",
    },
}
```

### FastAPI — initiate login + ACS view

```python
# saml_routes.py
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from .saml_settings import SAML_SETTINGS

router = APIRouter(prefix="/saml")


async def _build_req(request: Request) -> dict:
    """python3-saml ek framework-agnostic request dict expect karta hai.
    Form data ko 'post_data' mein, query ko 'get_data' mein daalo."""
    form = await request.form()
    return {
        "https": "on" if request.url.scheme == "https" else "off",
        "http_host": request.url.hostname,
        "script_name": request.url.path,
        "server_port": request.url.port,
        "get_data": dict(request.query_params),
        "post_data": {k: v for k, v in form.items()},
    }


@router.get("/login")
async def saml_login(request: Request):
    """SP-initiated: build AuthnRequest → redirect to IdP SSO URL."""
    req = await _build_req(request)
    auth = OneLogin_Saml2_Auth(req, old_settings=SAML_SETTINGS)

    # RelayState = original deep-link; lib base64+deflates the AuthnRequest
    # and returns the IdP redirect URL with ?SAMLRequest=...&RelayState=...
    return_to = request.query_params.get("next", "/dashboard")
    redirect_url = auth.login(return_to=return_to)
    return RedirectResponse(redirect_url, status_code=302)


@router.post("/acs")
async def saml_acs(request: Request):
    """Assertion Consumer Service — IdP yahan signed SAMLResponse POST karta hai."""
    req = await _build_req(request)
    auth = OneLogin_Saml2_Auth(req, old_settings=SAML_SETTINGS)

    # ⭐ process_response() does the heavy lifting:
    #   signature verify, Issuer/Audience/Conditions/InResponseTo,
    #   replay window — because strict=True
    request_id = request.session.get("saml_request_id")  # stored at /login
    auth.process_response(request_id=request_id)

    errors = auth.get_errors()
    if errors:
        # get_last_error_reason() gives a human reason (e.g. invalid signature)
        raise HTTPException(401, f"SAML validation failed: {auth.get_last_error_reason()}")

    if not auth.is_authenticated():
        raise HTTPException(401, "SAML response not authenticated")

    # Identity extract karo
    name_id = auth.get_nameid()                 # e.g. "ashish@acme.com"
    attributes = auth.get_attributes()          # {"groups": ["eng"], "displayName": [...]}
    session_index = auth.get_session_index()    # needed for Single Logout (SLO)

    # ── JIT provisioning: user na ho to create kar do (see SCIM section) ──
    user = get_or_create_user(email=name_id, attributes=attributes)

    # Create your OWN local session / issue your JWT (SAML ends here)
    request.session["user_id"] = user.id
    request.session["saml_session_index"] = session_index

    # RelayState pe wapas bhejo (validate it's a local path — open-redirect guard)
    relay = (await request.form()).get("RelayState", "/dashboard")
    if not relay.startswith("/"):
        relay = "/dashboard"
    return RedirectResponse(relay, status_code=303)


@router.get("/metadata")
async def saml_metadata(request: Request):
    """Publish SP metadata XML so the IdP admin can configure their side."""
    from onelogin.saml2.settings import OneLogin_Saml2_Settings
    settings = OneLogin_Saml2_Settings(SAML_SETTINGS, sp_validation_only=True)
    metadata = settings.get_sp_metadata()
    errors = settings.validate_metadata(metadata)
    if errors:
        raise HTTPException(500, f"Invalid SP metadata: {errors}")
    from fastapi.responses import Response
    return Response(content=metadata, media_type="application/xml")
```

> Flask note: same library, `onelogin.saml2.auth.OneLogin_Saml2_Auth` — bas `_build_req` ko Flask `request.form` / `request.args` se bana lo. Logic identical hai.

---

## SAML vs OIDC — Decision Table

| Aspect | SAML 2.0 | OIDC (OAuth2-based) |
|---|---|---|
| Data format | XML (assertions) | JSON / JWT (ID token) |
| Era / vibe | Enterprise, legacy, B2B | Modern, mobile, API-first |
| Transport | Browser front-channel (POST/redirect) | `/authorize` + back-channel `/token` |
| Token for APIs? | ❌ No native API token | ✅ Access token for APIs |
| Mobile / native | 😐 Clunky (web-view) | 😍 Built for it (PKCE) |
| Crypto | XML-DSig (signing/enc) | JWS / JWKS |
| Discovery | Metadata XML (manual exchange) | `/.well-known/openid-configuration` |
| Library risk | High (XSW, XXE) → use vetted lib | Lower, still validate JWT properly |
| Typical IdP | Okta, Azure AD, ADFS, Ping | Same vendors + Google, Auth0, Cognito |
| When to pick | B2B SSO, procurement requires SAML, legacy SP | Greenfield, mobile, microservice APIs |

> Practical reality (2026): naya kuch bana rahe ho → **OIDC**. Enterprise customer demand kare ya legacy app integrate karna ho → **SAML**. Mature SaaS dono support karta hai.

---

## LDAP / Active Directory

### What a directory looks like (DIT — Directory Information Tree)

```
dc=acme,dc=com                         (domain root)
 ├── ou=people                         (Organizational Unit)
 │    ├── cn=ashish chaurasiya         ← an entry (object)
 │    │     uid: ashish
 │    │     mail: ashish@acme.com
 │    │     userPassword: {hashed}
 │    └── cn=neha sharma
 └── ou=groups
      ├── cn=engineering               (group; member: list of DNs)
      └── cn=admins

DN (Distinguished Name) = full path, read leaf→root:
   cn=ashish chaurasiya,ou=people,dc=acme,dc=com

Building blocks:
   dc = domainComponent     ou = organizationalUnit
   cn = commonName          uid = user id        mail = email
```

### Bind = authentication

```
Bind operation = "yeh credentials sahi hain kya?" (LDAP ka auth)

Simple bind:
   DN + password directly bhejte ho → server verify karta hai
   ⚠️ Password plaintext jaata hai → MUST be over LDAPS/StartTLS

SASL bind:
   Mechanism-based (e.g. GSSAPI/Kerberos, DIGEST-MD5, EXTERNAL/mTLS)
   Stronger; AD environments often Kerberos (GSSAPI) use karte hain

Anonymous bind:
   No credentials → only public/readable entries
   (some dirs allow it for searching; usually restricted)
```

### LDAPS / StartTLS — never plaintext

```
LDAP   → port 389  (plaintext)        ❌ NEVER bind here over a network
LDAPS  → port 636  (TLS from connect) ✅ implicit TLS, preferred
StartTLS → port 389, upgrade to TLS   ✅ explicit upgrade after connect

Simple bind plaintext over 389 = credentials wire pe clear text.
Mandatory: LDAPS (636) ya StartTLS. Validate the server cert.
```

### Search-then-bind pattern (THE auth pattern)

```
User sirf username deta hai (DN nahi pata). To:

1. Service account se bind karo (read-only "search" creds)
2. username se SEARCH karo → user ka actual DN nikalo
        filter: (&(objectClass=person)(uid=ashish))
3. Us DN + user ke ENTERED password se DOBARA bind karo
        → bind success = password sahi = authenticated ✅
        → bind fail   = wrong creds
4. (optional) group membership search karke roles map karo
5. Rebind service account back (ya naya connection)

Kyun search-then-bind? Kyunki DN unpredictable hota hai
(cn=Full Name vs uid=login). Search se resolve karke fir verify.
```

### Python — `ldap3`

```python
# pip install ldap3
from ldap3 import Server, Connection, Tls, ALL, SUBTREE
import ssl

# ── 1. Server over LDAPS (port 636), validate the cert ──
tls = Tls(validate=ssl.CERT_REQUIRED, ca_certs_file="/etc/ssl/acme-ca.pem")
server = Server("ldaps://ad.acme.com", port=636, use_ssl=True,
                get_info=ALL, tls=tls)

SERVICE_DN = "cn=svc-ldap,ou=service,dc=acme,dc=com"
SERVICE_PW = "..."                       # from secrets manager, NOT hardcoded
BASE_DN    = "dc=acme,dc=com"


def authenticate(username: str, password: str) -> dict | None:
    """Search-then-bind: resolve DN, then verify password by re-binding."""

    # ── 2. Bind as service account (read-only search creds) ──
    #    auto_bind=True → bind happens on Connection construction
    conn = Connection(server, user=SERVICE_DN, password=SERVICE_PW,
                      auto_bind=True)

    # ── 3. Search for the user's DN ──
    #    NOTE: escape user input in real code (ldap3.utils.conv.escape_filter_chars)
    from ldap3.utils.conv import escape_filter_chars
    safe_user = escape_filter_chars(username)
    conn.search(
        search_base=BASE_DN,
        search_filter=f"(&(objectClass=person)(uid={safe_user}))",
        search_scope=SUBTREE,
        attributes=["distinguishedName", "mail", "displayName", "memberOf"],
    )
    if not conn.entries:
        conn.unbind()
        return None                      # user not found

    entry = conn.entries[0]
    user_dn = entry.entry_dn             # the real DN we'll bind with
    user_info = {
        "email": str(entry.mail) if "mail" in entry else None,
        "name": str(entry.displayName) if "displayName" in entry else None,
        "groups": [str(g) for g in entry.memberOf] if "memberOf" in entry else [],
    }
    conn.unbind()

    # ── 4. Re-bind AS THE USER with the entered password ──
    #    Success of this bind == correct password.
    user_conn = Connection(server, user=user_dn, password=password)
    if not user_conn.bind():             # returns False on bad creds
        return None                      # authentication failed
    user_conn.unbind()

    return user_info                     # authenticated + attributes/groups
```

```python
# Group-based authorization mapping (memberOf → app roles)
def map_roles(groups: list[str]) -> set[str]:
    roles = set()
    for dn in groups:
        dn_low = dn.lower()
        if "cn=admins" in dn_low:
            roles.add("admin")
        if "cn=engineering" in dn_low:
            roles.add("engineer")
    return roles or {"viewer"}           # safe default
```

> AD specifics: AD `sAMAccountName` (login name) aur `userPrincipalName` (`user@domain`) attributes deta hai. Filter often `(sAMAccountName=ashish)` ya `(userPrincipalName=ashish@acme.com)`. Group membership `memberOf` deta hai (DN list). Nested groups ke liye AD ka special matching-rule OID (`memberOf:1.2.840.113556.1.4.1941:`) use hota hai.

---

## Provisioning — SCIM + JIT (brief)

```
Problem: SAML tumhe LOGIN deta hai, but user accounts kaun banayega/hatayega?

JIT (Just-In-Time) provisioning:
   - First successful SAML login pe SP user record auto-create kar deta hai
   - Attributes assertion se aate hain (email, name, groups → roles)
   - Simple, no extra API; but DEPROVISION nahi karta automatically
     (employee resign → IdP login band, lekin SP mein stale row reh jaati hai)

SCIM (System for Cross-domain Identity Management):
   - REST + JSON standard (RFC 7643/7644) for lifecycle management
   - IdP → SP: CREATE / UPDATE / DEACTIVATE users & groups proactively
   - Endpoints: /scim/v2/Users, /scim/v2/Groups (PATCH to disable)
   - Solves deprovisioning: IdP se disable → SCIM call → SP user deactivated
   - Enterprise customers often SAML (login) + SCIM (lifecycle) DONO maangte hain

Rule of thumb:
   SAML/OIDC = authentication (who's logging in right now)
   SCIM      = provisioning (who SHOULD exist, kept in sync continuously)
```

---

## Interview Questions & Answers

### Q1: SAML aur OAuth2/OIDC mein fundamental difference kya hai?

**Answer:**

**WHAT:** SAML ek *authentication/federation* protocol hai (XML assertions, browser-based). OAuth2 ek *authorization* framework hai (API access delegation); OIDC uspe authentication layer.

**WHY confusion:** Dono "login" karwate hain, lekin:
```
SAML  → IdP signed XML assertion deta hai SP ko, browser POST se.
         API tokens nahi deta. Enterprise/legacy/B2B.
OAuth2 → access token deta hai API call ke liye (delegation).
OIDC   → OAuth2 + ID token (JWT) = "who are you".
```
**Senior line:** "SAML federation hai cross-org browser SSO ke liye; OIDC modern equivalent hai with JSON/JWT aur native API tokens. Naya banao to OIDC, enterprise customer demand kare to SAML."

---

### Q2: SP-initiated SAML flow step-by-step batao.

**Answer:**
```
1. User SP (app) pe protected page maangta hai → not authenticated.
2. SP <AuthnRequest> banata hai, request ID + RelayState store karta hai.
3. SP browser ko IdP SSO URL pe redirect karta hai
   (HTTP-Redirect binding: SAMLRequest deflate+base64 in query).
4. IdP user ko authenticate karta hai (password + MFA).
5. IdP ek SIGNED <Response> banata hai jismein <Assertion> hota hai;
   auto-submit HTML form se SP ke ACS pe POST (HTTP-POST binding).
6. SP ACS pe: signature verify, Issuer/Audience/Conditions/InResponseTo
   validate, replay-check; NameID + attributes extract.
7. SP apni LOCAL session/JWT banata hai, RelayState pe redirect.
```
Key: trust **assertion signature** pe rests — koi back-channel call nahi hota.

---

### Q3: ACS kya hai? RelayState kis kaam aata hai?

**Answer:**
- **ACS (Assertion Consumer Service)** = SP ka endpoint (`/saml/acs`) jahan IdP signed `SAMLResponse` HTTP-POST karta hai. SP yahan validate karke session banata hai. ACS URL SP metadata mein declared hota hai — IdP usi par hi POST karega.
- **RelayState** = opaque round-trip value. SP-initiated mein typically original deep-link (`/dashboard`) hota hai taaki login ke baad user wahin wapas jaaye. IdP isse touch nahi karta, as-is wapas bhejta hai. **Security:** ise validate karo (local path hi ho) — warna open-redirect ban jaata hai.

---

### Q4: XML Signature Wrapping (XSW) attack kya hai? Kaise bachoge?

**Answer:**

**WHAT:** Attacker ek valid signed assertion ka XML manipulate karke forged assertion inject karta hai. SP signature ko valid maan leta hai (original signed blob document mein hai) but identity attacker ke naye unsigned element se padh leta hai → arbitrary user impersonation.

**HOW bachna:**
```
✓ Signature jis element pe valid hui, data USI element se padho.
✓ Schema validation; extra/unexpected nodes reject karo.
✓ Reference URI resolve karke signed node == data node confirm karo.
✓ Sahi canonicalization (C14N).
✓ Sabse bada: hand-parse MAT karo — python3-saml / vetted lib use karo
  jo XSW + XXE handle karti hai. strict=True rakho.
```
**One-liner:** "XSW = validate-here-read-there bug. Use a battle-tested SAML library; never roll your own XML verification."

---

### Q5: SAMLResponse accept karne se pehle SP kya-kya validate kare?

**Answer:**
```
1. XML signature (IdP ki public cert se) — wantAssertionsSigned
2. Issuer == expected IdP entityID
3. Audience (AudienceRestriction) == SP entityID
4. Conditions: NotBefore <= now <= NotOnOrAfter (+ small clock skew)
5. SubjectConfirmation Recipient == your ACS URL; data NotOnOrAfter valid
6. InResponseTo == your issued AuthnRequest ID
   (IdP-initiated mein InResponseTo ABSENT hona chahiye)
7. Replay protection: assertion ID pehle dekha to reject (cache till expiry)
```
`strict=True` ke saath python3-saml yeh sab enforce karta hai. Skip karne ka matlab = forgery/replay accept karna.

---

### Q6: IdP-initiated vs SP-initiated — kaunsa safe aur kyun?

**Answer:**
```
SP-initiated (safer):
   - SP AuthnRequest banata hai → InResponseTo se correlation
   - Unsolicited response reject ho sakta hai
   - CSRF/replay surface kam

IdP-initiated:
   - IdP dashboard se direct unsolicited SAMLResponse aata hai
   - Koi AuthnRequest nahi → InResponseTo nahi
   - Stolen/replayed response inject karna asaan → CSRF-login risk
   - High-security apps ise disable rakhte hain
     (rejectUnsolicitedResponsesWithInResponseTo = True)
```
Default recommendation: **SP-initiated**. IdP-initiated tabhi jab business explicitly maange, aur tab bhi tight replay + audience checks ke saath.

---

### Q7: LDAP bind kya hai? "Search-then-bind" pattern kyun?

**Answer:**
- **Bind** = LDAP ka authentication operation. Simple bind = DN+password seedha verify (TLS pe hona chahiye). SASL bind = mechanism-based (Kerberos/GSSAPI, mTLS).
- **Search-then-bind kyun:** User sirf login name deta hai, full DN nahi pata (DN `cn=Full Name,...` ya `uid=login,...` ho sakta hai). To:
```
1. Service account se bind (read-only)
2. login name se search → real DN nikalo
3. us DN + entered password se DOBARA bind → success = authenticated
4. group search → roles map
```
Direct bind tabhi possible jab DN deterministically construct ho sake (e.g. AD UPN `user@domain`), warna search lazmi.

---

### Q8: LDAP/AD ko production mein securely kaise connect karein?

**Answer:**
```
✓ LDAPS (port 636) ya StartTLS — NEVER plaintext 389 over network
✓ Server certificate validate karo (CERT_REQUIRED + CA bundle)
✓ Service account least-privilege (read-only search scope)
✓ Service creds secrets manager mein (08_secrets_management_advanced.md)
✓ Filter inputs escape karo (LDAP injection!) — escape_filter_chars
✓ Connection pooling + timeouts; failed-bind rate limit
✓ Map AD groups → app roles (RBAC), don't trust client-sent roles
✓ Bade dir ke liye paged search; bind result cache mat karo as "session"
```
**LDAP injection:** `(uid={username})` mein agar username = `*)(uid=*))(|(uid=*` daal de to filter bypass → isliye `escape_filter_chars()` mandatory.

---

### Q9: SAML/LDAP login ke baad session kaise handle karte ho?

**Answer:**

SAML aur LDAP dono sirf **authentication step** hain — verify hone ke baad apni hi local session/JWT banao, baaki sab same:
```
SAML ACS validate ✅  ──┐
                       ├──► create local session / issue JWT
LDAP bind success ✅ ──┘     → cookie ya Authorization: Bearer
                            → RBAC, refresh, logout sab unchanged
                            (09_session_management.md, 01_jwt_oauth2_rbac.md)
```
SAML ka SLO (Single Logout) optional hai — `SessionIndex` store karke IdP-driven logout support kar sakte ho, par mostly apni local session expire karna kaafi.

---

### Q10: Enterprise SaaS bana rahe ho — SAML, OIDC, SCIM kab kya?

**Answer:**
```
Login (authentication):
   - SAML 2.0   → enterprise/legacy IdPs, B2B procurement requirement
   - OIDC       → modern IdPs, simpler integration; offer dono ideally

Provisioning (lifecycle):
   - JIT        → first login pe user auto-create (no deprovision)
   - SCIM       → IdP proactively create/update/DISABLE users & groups
                  (deprovisioning solve karta hai)

Mature B2B answer:
   "Hum SAML + OIDC dono login ke liye support karte hain, aur SCIM
    provisioning offer karte hain taaki customer ka IdP users ko
    automatically sync aur deprovision kar sake."
```

---

## SAML SP Production Checklist

```markdown
## SAML SP Readiness

### Setup
- [ ] SP metadata published (entityID, ACS URL, NameIDFormat)
- [ ] IdP metadata imported (entityID, SSO URL, signing cert)
- [ ] NameIDFormat agreed (emailAddress / persistent)
- [ ] Cert rotation plan (IdP signing certs expire!)

### Security (strict=True)
- [ ] wantAssertionsSigned = True
- [ ] Validate: signature, Issuer, Audience, Conditions, InResponseTo
- [ ] Replay protection (assertion ID cache till NotOnOrAfter)
- [ ] Clock skew small (≤ 2–5 min); servers NTP-synced
- [ ] IdP-initiated disabled unless explicitly required
- [ ] RelayState validated (local path only — no open redirect)
- [ ] Vetted library (python3-saml); NO hand-rolled XML parsing
- [ ] XXE disabled (library default; never enable external entities)

### Ops
- [ ] Audit log every assertion (subject, issuer, time)
- [ ] Alert on signature-validation failures (attack signal)
- [ ] Rate-limit /saml/acs
- [ ] Clear error UX (don't leak validation internals to user)
```

## LDAP / AD Checklist

```markdown
- [ ] LDAPS (636) or StartTLS — never plaintext bind
- [ ] Server cert validated (CERT_REQUIRED + CA)
- [ ] Service account least-privilege, creds in secrets manager
- [ ] Search filters escaped (escape_filter_chars) — LDAP injection
- [ ] Search-then-bind for auth (don't store/trust DN from client)
- [ ] Group→role mapping server-side (RBAC)
- [ ] Connection timeouts + failed-bind rate limiting
- [ ] Paged search for large directories
```

---

## Common Pitfalls

| Pitfall | Risk | Fix |
|---|---|---|
| Hand-parsing SAML XML | XSW / XXE → impersonation | Use python3-saml, `strict=True` |
| `strict=False` in prod | Validation skipped | Always `strict=True` |
| Not checking `Audience` | Assertion meant for another SP accepted | Validate Audience == SP entityID |
| Ignoring `Conditions` timing | Replay of old assertions | Enforce NotBefore/NotOnOrAfter + skew |
| No replay cache | Same assertion reused | Cache assertion IDs till expiry |
| Trusting IdP-initiated blindly | CSRF-login | Prefer SP-initiated; lock down unsolicited |
| RelayState unvalidated | Open redirect | Allow only local paths |
| LDAP simple bind over 389 | Creds in plaintext | LDAPS/StartTLS, validate cert |
| Unescaped LDAP filter | LDAP injection / auth bypass | `escape_filter_chars()` |
| Storing DN from client as identity | Spoofed identity | Search-then-bind server-side |
| JIT only, no SCIM | Stale accounts after offboarding | Add SCIM deprovisioning |
| Confusing SAML with OAuth | Wrong arch / tokens | SAML=XML federation, OAuth=API authz |

---

## Senior Mantras

```
1. SAML = XML federation (browser, enterprise). OAuth/OIDC = API authz
   (JSON/JWT, modern). Inhe mat confuse karo.

2. SAML ka trust = assertion SIGNATURE. Validate signature + Issuer +
   Audience + Conditions + InResponseTo + replay. Sab, har baar.

3. NEVER hand-parse SAML XML. XSW/XXE tumhe maar denge. Vetted lib,
   strict=True.

4. SP-initiated default rakho. IdP-initiated = bigger attack surface.

5. LDAP auth = search-then-bind. Bind success = correct password.

6. LDAPS/StartTLS always. Plaintext 389 bind = creds on the wire.

7. LDAP filters escape karo — injection real hai.

8. SAML/LDAP sirf login step hai — uske baad apni JWT/session, RBAC
   waisa hi rehta hai.

9. Login (SAML/OIDC) != provisioning (SCIM). Enterprise dono maangta hai;
   SCIM deprovisioning ke liye.

10. Audit EVERYTHING — assertions, binds, signature failures. Forensics
    aur compliance dono ke liye.
```

---

## Related Topics in This Repo

- [01_jwt_oauth2_rbac.md](01_jwt_oauth2_rbac.md) — JWT/session you issue *after* SAML/LDAP auth + RBAC
- [04_oauth2_flows_deep.md](04_oauth2_flows_deep.md) — OAuth2/OIDC, the modern counterpart to SAML
- [09_session_management.md](09_session_management.md) — local session after enterprise login
- [08_secrets_management_advanced.md](08_secrets_management_advanced.md) — LDAP service creds, SP keys, IdP certs
- [03_jwt_vulnerabilities_2fa_secrets.md](03_jwt_vulnerabilities_2fa_secrets.md) — token/secret pitfalls
- [10_zero_trust_microservices.md](10_zero_trust_microservices.md) — identity across services
- [18_passkeys_webauthn.md](18_passkeys_webauthn.md) — passwordless consumer auth (contrast to enterprise SSO)
- [11_compliance_gdpr_pci.md](11_compliance_gdpr_pci.md) — audit/identity compliance
- [17_india_dpdp_compliance.md](17_india_dpdp_compliance.md) — identity data + DPDP
