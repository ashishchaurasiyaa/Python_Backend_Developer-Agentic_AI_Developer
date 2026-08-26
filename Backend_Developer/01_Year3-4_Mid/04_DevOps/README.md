# 🚢 DevOps (backend-deployment focused)

> **22 theory + 11 practical + 4 runnable labs.** Yeh track **apni service deploy aur operate** karne ke liye hai.
> Full infra-engineer curriculum (Linux/Bash/Networking se shuru) alag hai → [`../../../DevOps/`](../../../DevOps/README.md)

---

## 🔴 Resume ke liye pehle yeh 4

> Yeh chaar tumhare resume ki **unverified lines** hain — [MY_PROGRESS.md](../../../MY_PROGRESS.md) ke hisaab se.
> Padhna kaafi nahi, labs karo.

| # | Topic | Kyun |
|---|---|---|
| [06](06_kubernetes_helm.md) | **Kubernetes + Helm** | Senior JD ka sabse bada must-have |
| [05](05_prometheus_grafana.md) | **Prometheus + Grafana** | Observability — resume pe hai hi nahi abhi |
| [19](19_opentelemetry_distributed_tracing.md) | **OpenTelemetry + tracing** | "Distributed system debug kaise karte ho?" |
| [07](07_terraform.md) | **Terraform** | IaC proof |

---

## 📚 Poori list

### Containers + serving
| # | Topic | # | Topic |
|---|---|---|---|
| [01](01_docker.md) | Docker | [02](02_nginx.md) | Nginx |
| [21](21_ingress_controller.md) | Ingress controller | [06](06_kubernetes_helm.md) 🔴 | Kubernetes + Helm |

### CI/CD + deployment
| # | Topic | # | Topic |
|---|---|---|---|
| [03](03_github_actions_cicd.md) | GitHub Actions | [13](13_gitops_argocd_flux.md) | GitOps — ArgoCD/Flux |
| [20](20_blue_green_deployment.md) | Blue-green | [18](18_feature_flags_experimentation.md) | Feature flags |
| [09](09_django_production_deployment.md) | Django prod deploy | [10](10_fastapi_production_deployment.md) | FastAPI prod deploy |
| [11](11_deployment_decision_framework.md) | Deployment decision framework | [12](12_deployment_interview_qa.md) | Deployment interview Q&A |

### Cloud + IaC
| # | Topic | # | Topic |
|---|---|---|---|
| [04](04_aws_ec2_s3_rds.md) | AWS EC2/S3/RDS | [22](22_aws_managed_services.md) | **AWS managed** — Lambda, API GW, EventBridge, ECS vs EKS |
| [07](07_terraform.md) 🔴 | Terraform | [15](15_multi_region_deployment.md) | Multi-region + DR |

### Observability + reliability
| # | Topic | # | Topic |
|---|---|---|---|
| [05](05_prometheus_grafana.md) 🔴 | Prometheus + Grafana | [08](08_elk_loki_logging.md) | ELK / Loki |
| [19](19_opentelemetry_distributed_tracing.md) 🔴 | OpenTelemetry + tracing | [17](17_ebpf_observability.md) | eBPF observability |
| [16](16_sre_practices_sli_slo.md) | SRE — SLI/SLO/error budgets | [14](14_chaos_engineering.md) | Chaos engineering |

---

## 🧪 Labs — [`labs/`](labs/) ← yahan haath chalega

| Lab | Kya karoge |
|---|---|
| [01_docker_multistage_build](labs/01_docker_multistage_build.py) | Multi-stage build, image size ghatao, non-root user |
| [02_nginx_reverse_proxy](labs/02_nginx_reverse_proxy.py) | Reverse proxy + upstream + headers |
| [03_prometheus_scrape_and_query](labs/03_prometheus_scrape_and_query.py) | Scrape config + asli PromQL queries |
| [04_deployment_health_gate](labs/04_deployment_health_gate.py) | Health check gate — bura deploy roko |

Runnable reference code: [`practical/`](practical/) (11 files)

**Related:** [full DevOps track](../../../DevOps/README.md) · [05_Microservices](../05_Microservices/README.md) · [STUDY_PLAN.md Part A, Week 1-4](../../../STUDY_PLAN.md) (yahi labs sequence me hain)
