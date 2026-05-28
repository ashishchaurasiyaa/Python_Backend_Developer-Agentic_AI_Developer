# 13 — Web Application Firewall (WAF)

> Layer 7 filtering of HTTP traffic. Blocks SQL injection, XSS, scrapers, and malicious patterns before they reach your app.

---

## What WAF Does

```
Internet → CDN → WAF → Load Balancer → App
                 ↑
            Inspects every request
            Blocks/throttles/challenges based on rules
```

### Common protections
- **SQL injection** (e.g., `' OR '1'='1`).
- **XSS** (`<script>alert(1)</script>`).
- **Path traversal** (`../../etc/passwd`).
- **Command injection** (`; rm -rf /`).
- **XXE / XEE attacks**.
- **HTTP response splitting**.
- **CSRF token attacks**.
- **Bad bots / scrapers**.
- **Rate limiting**.
- **Geo blocking**.

WAF complements (doesn't replace) app-level security.

---

## Popular WAF Options

### Managed (cloud)
| WAF | Provider | Strengths |
|---|---|---|
| AWS WAF | AWS | Tight AWS integration |
| Cloudflare WAF | Cloudflare | Great DX, CDN integrated |
| Azure WAF | Azure | Azure integration |
| GCP Cloud Armor | GCP | GCP integration |
| Imperva | Imperva | Enterprise, advanced features |
| Akamai WAF | Akamai | Largest CDN |
| Sucuri | GoDaddy | SMB-friendly |

### Self-hosted
| WAF | Notes |
|---|---|
| ModSecurity | OWASP rules; runs in NGINX/Apache |
| Coraza | Modern OSS, Go-based |
| NAXSI | NGINX-specific |
| Wallarm | Hybrid (cloud + agent) |

For most teams: cloud WAF (Cloudflare or AWS) is simplest.

---

## AWS WAF Example

### Basic setup
```hcl
resource "aws_wafv2_web_acl" "main" {
  name  = "api-protection"
  scope = "REGIONAL"

  default_action { allow {} }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    override_action { none {} }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "common-rules"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "RateLimit"
    priority = 2
    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }
    action { block {} }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "rate-limit"
      sampled_requests_enabled   = true
    }
  }
}

resource "aws_wafv2_web_acl_association" "alb" {
  resource_arn = aws_lb.main.arn
  web_acl_arn  = aws_wafv2_web_acl.main.arn
}
```

### Managed rule groups
AWS provides curated rule sets:
- **CommonRuleSet:** OWASP Top 10.
- **KnownBadInputs:** known exploit signatures.
- **SQLDatabase:** SQL injection.
- **AnonymousIPList:** TOR / VPN.
- **BotControl:** bot detection.

Pay per rule group. Combine.

---

## Cloudflare WAF Example

Cloudflare WAF runs at the edge for free with paid plans.

### Rule via UI
- "Block requests where URL contains `/admin` and country != US."

### Page Rules / Transform Rules
```
If (http.request.uri.path matches "/api/v1/admin/.*"
    and ip.geoip.country != "US"
    and not cf.client.bot)
Then block
```

### Rate limiting
```
If http.request.uri.path = "/login"
   and req_count > 5 in 60s per ip
Then block 5min
```

### Bot management (paid)
Cloudflare scores every request 1-99 for bot likelihood. Block low scores.

---

## OWASP CRS (Core Rule Set)

The most widely used WAF rule set (OSS).

### Rule categories
- 920: Protocol enforcement (HTTP request smuggling).
- 921: Protocol attack (HTTP request smuggling).
- 930: Local file inclusion.
- 931: Remote file inclusion.
- 932: Remote code execution.
- 933: PHP injection.
- 934: NodeJS injection.
- 941: XSS.
- 942: SQL injection.
- 943: Session fixation.
- 944: Java RCE.
- 949: Block by paranoia.

Each rule has a score. Total score > threshold → block.

### Paranoia levels (1-4)
- 1: minimal false positives, catches common attacks.
- 2: stricter.
- 3: very strict.
- 4: paranoid (many false positives).

Start at 1, tighten as you tune.

---

## ModSecurity (Self-hosted Example)

```nginx
# nginx.conf
load_module modules/ngx_http_modsecurity_module.so;

http {
    modsecurity on;
    modsecurity_rules_file /etc/nginx/modsec/main.conf;
    ...
}
```

```
# /etc/nginx/modsec/main.conf
Include /etc/nginx/modsec/modsecurity.conf
Include /etc/nginx/modsec/crs-setup.conf
Include /etc/nginx/modsec/rules/*.conf
```

ModSecurity v3 + OWASP CRS 3.x is the standard self-hosted stack.

---

## False Positives Tuning

Out-of-box WAF blocks legit requests too. Tune.

### Common false positives
- File upload (binary triggers SQL injection rule).
- Code review tools (HTML in comments).
- Admin panels with rich text editors.
- Specific app patterns.

### Tuning workflow
1. Run WAF in **Count mode** (not Block).
2. Log everything.
3. Review false positives.
4. Add exclusions.
5. Switch to Block mode.

```hcl
# AWS WAF — exclude a rule for specific endpoint
rule {
  name = "AWSManagedRulesCommonRuleSet"
  ...
  override_action { none {} }
  rule_action_override {
    name = "GenericRFI_QUERYARGUMENTS"
    action_to_use { count {} }   # log only
  }
}
```

---

## Bot Protection

Different from WAF, but often combined.

### Approaches
1. **CAPTCHA** challenges (reCAPTCHA, hCaptcha, Cloudflare Turnstile).
2. **JavaScript challenges** (run JS to prove browser).
3. **Behavioral analysis** (mouse movement, typing pattern).
4. **Device fingerprinting**.
5. **IP reputation** (data center, TOR, VPN flags).

### When to challenge
- Suspicious user agent.
- High request rate.
- Failed login attempts.
- New account creation.

```yaml
# Cloudflare bot rule
If cf.bot_management.score < 30 then challenge
```

---

## Geo Blocking

Block / restrict by country.

### Use cases
- App not licensed in some countries.
- Compliance (sanctions: e.g., block Iran, North Korea).
- Reduce attack surface (90% of attacks from few countries).

```hcl
# AWS WAF
rule {
  statement {
    geo_match_statement {
      country_codes = ["IR", "KP", "RU"]
    }
  }
  action { block {} }
}
```

Be careful: blocks legitimate users in those countries too.

---

## API-Specific Protections

REST/GraphQL APIs need different rules than web pages.

### Schema validation
WAF can validate JSON against schema:
```yaml
# Cloudflare API Shield
schemas:
  - path: "/api/v1/orders"
    method: POST
    schema: |
      {
        "type": "object",
        "properties": {
          "amount": {"type": "number", "minimum": 0}
        },
        "required": ["amount"]
      }
```

### Rate limit per endpoint
```yaml
- path: "/api/v1/login"
  rate: 5 per minute per IP
- path: "/api/v1/orders"
  rate: 100 per minute per token
```

### Request size limit
Block payloads > N KB to prevent DoS.

### JSON depth / array length
Block deeply nested JSON (DoS via parsing).

---

## GraphQL-Specific

GraphQL endpoints harder to protect (single endpoint, varied queries).

WAF + custom validation:
- Block introspection in prod.
- Block queries above complexity threshold.
- Block deeply nested queries.

Some WAFs offer GraphQL inspection (Cloudflare Premium).

---

## Logging & Monitoring

### Log every blocked request
- IP, user agent, URL, headers, body sample.
- Rule that triggered.
- Action taken (block/challenge/log).

### Dashboards
- Top blocked IPs.
- Top blocked endpoints.
- Trends (increase = under attack?).
- Geographic distribution.

### Alerts
- Spike in blocked requests.
- New attack patterns.
- High false-positive rate.

---

## DDoS Considerations

WAF helps mitigate L7 DDoS (HTTP flood). Doesn't help L3/4 (SYN flood, UDP flood). For those: separate DDoS protection (Cloudflare Spectrum, AWS Shield Advanced).

See file 14 for DDoS deep dive.

---

## Defense in Depth

WAF is one layer. Combine with:
- Input validation in app (parameterized queries, output encoding).
- Authentication & authorization.
- Rate limiting at app level.
- Security headers (CSP, HSTS, etc.).
- TLS everywhere.
- Logging & alerting.

WAF stops common attacks; doesn't make app secure.

---

## Cost

| WAF | Cost |
|---|---|
| Cloudflare Pro | $20/month flat |
| Cloudflare Enterprise | $5K+/month |
| AWS WAF | $5/month per Web ACL + $0.60/M requests + rule costs |
| Azure WAF | ~$30/month base + per-rule |
| Self-hosted (NGINX + ModSec) | "Free" (your ops time + servers) |

For startups: Cloudflare's free tier covers a lot.
For enterprise: AWS WAF or Cloudflare Enterprise.

---

## Common Mistakes

### 1. Deploying WAF in Block mode immediately
Floods of false positives. Always start in Count/Monitor mode.

### 2. No exclusions for legitimate traffic
Specific app features broken.

### 3. Blind trust in WAF
"Our WAF protects us." → App still vulnerable to logic bugs. Defense in depth.

### 4. Ignoring WAF logs
Logs reveal attacks + tuning issues. Review weekly.

### 5. Same WAF rules everywhere
Different apps have different attack surfaces. Tune per app.

### 6. Not testing WAF
Penetration tests should target WAF (with consent). Validate it actually blocks.

---

## TL;DR

- WAF = HTTP-level firewall.
- Managed (Cloudflare, AWS) for most. Self-hosted (ModSecurity + OWASP CRS) for full control.
- Block SQL injection, XSS, common exploits, scrapers, bots.
- Always tune in Count mode first.
- API-specific protections: schema validation, rate limits, request size.
- Defense in depth: WAF + app validation + auth + monitoring.
- Log all blocked requests; review weekly.
