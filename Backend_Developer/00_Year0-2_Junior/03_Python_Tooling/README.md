# 🔧 Python Tooling

> **3 theory + 1 practical.** Chhota folder hai par interview me **senior signal** deta hai —
> "tumhare project me lint/type-check/dependency lock kaise setup hai?" ka jawab yahin se aata hai.

---

## 📚 Files

| # | Theory | Kya | Kyun matter karta hai |
|---|---|---|---|
| 01 | [Poetry + uv](01_poetry_uv.md) | Dependency management, lockfiles, virtualenvs, uv ki speed | "requirements.txt kyun kaafi nahi hai" — reproducible builds |
| 02 | [Ruff + mypy + pre-commit](02_ruff_mypy_precommit.md) | Linting, formatting, static types, git hooks | Team me code quality **automate** karna — senior ka kaam |
| 03 | [Packaging + pyproject](03_packaging_pyproject.md) | `pyproject.toml`, build backends, publishing | Internal library banana / distribute karna |

**Practical:** [`practical/01_tooling_demo.py`](practical/01_tooling_demo.py) — teeno ka wiring ek jagah.

---

## 🎯 Interview me kya bolna hai

- **uv** (2026): pip/poetry se 10-100x fast, Rust me likha — "hum uv pe shift kar rahe hain" ek current-sounding line hai.
- **Ruff** ne flake8 + isort + black replace kar diya — ek tool, ek config.
- **mypy strict mode** legacy codebase pe kaise chadhate hain: `--strict` module-by-module, `disallow_untyped_defs` pehle.
- **pre-commit** = CI se pehle local gate; CI me bhi wahi hooks chalao taaki bypass na ho.

**Related:** [Mid-track Engineering Practices](../../01_Year3-4_Mid/14_Engineering_Practices/) · [Testing](../10_Testing/) · [DevOps CI/CD](../../../DevOps/10_CICD/)
