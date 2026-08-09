# 🔐 Security

> **21 theory + 4 practical.** Security round har senior interview me hota hai — aur yahi wo jagah hai
> jahan "maine JWT use kiya hai" aur "maine JWT **sahi** use kiya hai" ka farq dikhta hai.

---

## 🔴 Interview ke liye pehle yeh 5

| # | Topic | Classic question |
|---|---|---|
| [01](01_jwt_oauth2_rbac.md) | **JWT + OAuth2 + RBAC** | Base — har interview me |
| [04](04_oauth2_flows_deep.md) | **OAuth2 flows deep (+ OIDC)** | "OAuth2 vs OIDC?" · "Authorization code + PKCE kyun?" |
| [03](03_jwt_vulnerabilities_2fa_secrets.md) | **JWT vulnerabilities** | "`alg: none` attack" · "JWT revoke kaise karoge?" |
| [09](09_session_management.md) | **Session management** | "JWT vs session cookie — kab kya?" |
| [08](08_secrets_management_advanced.md) | **Secrets management** | "`.env` prod me kyun nahi?" — Vault, rotation |

---

## 📚 Poori list

### Auth + identity
| # | Topic |
|---|---|
| [01](01_jwt_oauth2_rbac.md) 🔴 | JWT, OAuth2, RBAC |
| [04](04_oauth2_flows_deep.md) 🔴 | OAuth2 flows deep — authorization code, PKCE, client credentials, **OIDC** (id_token vs access_token, JWKS) |
| [03](03_jwt_vulnerabilities_2fa_secrets.md) 🔴 | JWT vulnerabilities, 2FA, secrets |
| [09](09_session_management.md) 🔴 | Session management |
| [18](18_passkeys_webauthn.md) | Passkeys / WebAuthn *(2026 topic)* |
| [19](19_saml_ldap_enterprise_sso.md) | SAML + LDAP enterprise SSO |
| [20](20_opa_abac_policy_as_code.md) | OPA + ABAC, policy-as-code |

### Attacks + defence
| # | Topic |
|---|---|
| [02](02_owasp_brute_force_csrf.md) | OWASP, brute force, CSRF |
| [05](05_rate_limiting_throttling.md) | Rate limiting / throttling |
| [07](07_cors_csp_security_headers.md) | CORS, CSP, security headers |
| [13](13_waf_protection.md) | WAF |
| [14](14_ddos_mitigation.md) | DDoS mitigation |
| [15](15_pen_testing_methodology.md) | Pen-testing methodology |

### Crypto + secrets
| # | Topic |
|---|---|
| [06](06_cryptography_basics.md) | Cryptography basics — hashing vs encryption, bcrypt/argon2 |
| [08](08_secrets_management_advanced.md) 🔴 | Secrets management — Vault, rotation, KMS |

### Supply chain + infra
| # | Topic |
|---|---|
| [16](16_sast_dast_supply_chain.md) | SAST/DAST + supply chain (SBOM, dependency scanning) |
| [21](21_container_image_security.md) | Container image security |
| [10](10_zero_trust_microservices.md) | Zero-trust for microservices |
| [12](12_security_testing.md) | Security testing |

### Compliance
| # | Topic |
|---|---|
| [11](11_compliance_gdpr_pci.md) | GDPR + PCI-DSS |
| [17](17_india_dpdp_compliance.md) | **India DPDP Act** — India roles ke liye relevant |

---

## 💻 Practical

| File | Covers |
|---|---|
| [`01_security_practical.py`](practical/01_security_practical.py) | JWT/OAuth2/RBAC basics |
| [`02_oauth2_rate_limit_crypto_practical.py`](practical/02_oauth2_rate_limit_crypto_practical.py) | OAuth2 flows, rate limiting, crypto |
| [`03_sessions_zerotrust_compliance_practical.py`](practical/03_sessions_zerotrust_compliance_practical.py) | Sessions, zero-trust, compliance |
| [`04_security_testing_practical.py`](practical/04_security_testing_practical.py) | Security testing |

> 4 practicals 21 topics cover karte hain — grouped hain, 1:1 nahi. Baaki topics config/process wale hain.

**Related:** [02_API_Design](../02_API_Design/README.md) · [DevOps Security](../../../DevOps/14_Security/) · [Django security](../../00_Year0-2_Junior/07_Django_DRF/16_security_hardening.md) · [Agentic AI security](../../../Agentic_AI/Modern_Topics/09_ai_security_threats.md)
