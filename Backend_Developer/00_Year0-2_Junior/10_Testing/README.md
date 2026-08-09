# 🧪 Testing

> **9 theory + 9 practical (1:1).** "Tests likhte ho?" har interview me aata hai —
> asli farq tab padta hai jab poocha jaye *"kya test karte ho aur kya nahi, aur kyun."*

---

## 🔴 Pehle yeh 3

| # | Topic | Kyun |
|---|---|---|
| [01](theory/01_pytest_advanced.md) | **pytest advanced** — fixtures, scope, parametrize, monkeypatch | Base yahi hai; fixture scope ka jawab senior signal hai |
| [08](theory/08_fastapi_testing_patterns.md) | **FastAPI testing patterns** — TestClient, DB override, async | Tumhara daily stack |
| [09](theory/09_testcontainers_python.md) | **Testcontainers** — asli Postgres/Redis test me | "Mock karte ho ya real DB?" ka 2026 wala jawab |

---

## 📚 Poori list

| # | Theory | Practical | Kya |
|---|---|---|---|
| 01 | [pytest advanced](theory/01_pytest_advanced.md) | [`01_pytest_advanced.py`](practical/01_pytest_advanced.py) | Fixtures, conftest, markers, parametrize |
| 02 | [Snapshot testing](theory/02_snapshot_testing.md) | [`02_snapshot_testing.py`](practical/02_snapshot_testing.py) | Golden files, syrupy |
| 03 | [Mutation testing](theory/03_mutation_testing.md) | [`03_mutation_testing.py`](practical/03_mutation_testing.py) | mutmut — "coverage 90% hai par test bekaar hain" |
| 04 | [Contract testing (Pact)](theory/04_contract_testing_pact.md) | [`04_contract_testing_pact.py`](practical/04_contract_testing_pact.py) | Consumer-driven contracts, microservices |
| 05 | [Test parallelization](theory/05_test_parallelization.md) | [`05_test_parallelization.py`](practical/05_test_parallelization.py) | pytest-xdist, flaky isolation |
| 06 | [Performance testing (Locust)](theory/06_performance_testing_locust.md) | [`06_performance_testing_locust.py`](practical/06_performance_testing_locust.py) | Load test, p95 padhna |
| 07 | [TDD / BDD practices](theory/07_tdd_bdd_practices.md) | [`07_tdd_bdd_practices.py`](practical/07_tdd_bdd_practices.py) | Red-green-refactor, Gherkin |
| 08 | [FastAPI testing patterns](theory/08_fastapi_testing_patterns.md) | [`08_fastapi_testing_patterns.py`](practical/08_fastapi_testing_patterns.py) | TestClient, dependency override, async |
| 09 | [Testcontainers](theory/09_testcontainers_python.md) | [`09_testcontainers_python.py`](practical/09_testcontainers_python.py) | Ephemeral Postgres/Redis, CI setup |

Config: [`practical/pytest.ini`](practical/pytest.ini)

---

## 📄 Root-level files (extra depth)

Ye 4 files folder root me hain (theory/ me nahi) — **standalone deep-dives**:

| File | Kya | Note |
|---|---|---|
| [property_based_testing_hypothesis.md](property_based_testing_hypothesis.md) | Hypothesis, property-based testing | 🔴 **Sirf yahan hai** — theory/ me iska koi version nahi. Padho. |
| [mutation_testing_mutmut.md](mutation_testing_mutmut.md) | Mutation testing | [theory/03](theory/03_mutation_testing.md) ka longer version |
| [contract_testing_pact.md](contract_testing_pact.md) | Pact | [theory/04](theory/04_contract_testing_pact.md) ka longer version |
| [load_testing_locust_k6.md](load_testing_locust_k6.md) | Locust + k6 | [theory/06](theory/06_performance_testing_locust.md) ka longer version + k6 |

> **Overlap hai** — teen files theory/ ke topics dohrati hain. Jaldi revise karna ho to `theory/` padho;
> gehrai chahiye to root wali. Property-based testing sirf root me hai.

**Related:** [Mid-track Engineering Practices](../../01_Year3-4_Mid/14_Engineering_Practices/) · [Microservices testing](../../01_Year3-4_Mid/05_Microservices/12_microservices_testing.md) · [FastAPI](../06_FastAPI/) · [DevOps CI/CD](../../../DevOps/10_CICD/)
