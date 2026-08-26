"""
Lab 02 — Window Functions
════════════════════════════════════════════════════════════════════════════════

ARCHITECTURE — Window Function Anatomy:

    SELECT
        name,
        salary,
        RANK() OVER (
            PARTITION BY dept_id    ← "per department" (like GROUP BY but rows kept)
            ORDER BY salary DESC    ← ranking order within partition
        ) AS salary_rank
    FROM employees;

    PARTITION BY = "reset the window for each group"
    ORDER BY     = "define position within the window"
    No PARTITION = whole table is one window

KEY FUNCTIONS:
  Ranking:   ROW_NUMBER() — always unique 1,2,3,4
             RANK()       — ties get same rank, GAPS after ties (1,1,3)
             DENSE_RANK() — ties get same rank, NO gaps (1,1,2)

  Lag/Lead:  LAG(col, n)  — value from n rows BEFORE current row
             LEAD(col, n) — value from n rows AFTER current row

  Aggregate: SUM() OVER   — running total or partition total
             AVG() OVER   — average within window
             COUNT() OVER — count within window

CLASSIC INTERVIEW PROBLEM:
  "Find the second-highest salary in each department."
  Answer: DENSE_RANK() OVER (PARTITION BY dept_id ORDER BY salary DESC) = 2

INTERVIEW ANSWER:
  "Window functions GROUP BY se alag hain — GROUP BY rows collapse karta hai,
   window functions sirf calculated column add karte hain, original rows rehti
   hain. RANK() ties pe gap deta hai (1,1,3), DENSE_RANK() nahi deta (1,1,2),
   ROW_NUMBER() har row ko unique number deta hai even for ties."

TASK:
  1. TODO 1: ROW_NUMBER — sequential number per department by salary
  2. TODO 2: RANK vs DENSE_RANK — show the difference on tied salaries
  3. TODO 3: PARTITION BY dept — salary rank within each department
  4. TODO 4: Second-highest earner per department (classic interview problem)
  5. TODO 5: LAG — month-over-month revenue change
  6. TODO 6: Running total — cumulative salary spend per dept
  7. TODO 7: LEAD — next month's revenue (forecast comparison)

RUN: python lab_02_window_functions.py

Prereq: none — uses Python's built-in sqlite3 (v3.25+ supports window functions)
"""

import sqlite3
import sys

def setup_db() -> sqlite3.Connection:
    # SQLite 3.25+ supports window functions
    if sqlite3.sqlite_version_info < (3, 25, 0):
        print(f"WARNING: SQLite {sqlite3.sqlite_version} may not support window functions.")
        print("Upgrade Python or use PostgreSQL for full window function support.")
        sys.exit(1)

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE departments (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE employees (
            id      INTEGER PRIMARY KEY,
            name    TEXT,
            dept_id INTEGER,
            salary  REAL
        );
        CREATE TABLE monthly_revenue (
            id      INTEGER PRIMARY KEY,
            month   TEXT,   -- 'YYYY-MM'
            revenue REAL
        );

        INSERT INTO departments VALUES (1,'Engineering'),(2,'Marketing'),(3,'Sales');

        INSERT INTO employees VALUES
            (1,'Alice',   1, 95000),
            (2,'Bob',     1, 80000),
            (3,'Carol',   1, 80000),  -- tied salary with Bob
            (4,'Dave',    2, 70000),
            (5,'Eve',     2, 65000),
            (6,'Frank',   2, 65000),  -- tied salary with Eve
            (7,'Grace',   3, 90000),
            (8,'Henry',   3, 75000),
            (9,'Iris',    3, 75000);  -- tied with Henry

        INSERT INTO monthly_revenue VALUES
            (1,'2026-01', 100000),
            (2,'2026-02', 120000),
            (3,'2026-03', 115000),
            (4,'2026-04', 135000),
            (5,'2026-05', 140000),
            (6,'2026-06', 130000);
    """)
    conn.commit()
    return conn


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — ROW_NUMBER: sequential row number across all employees by salary
# ════════════════════════════════════════════════════════════════════════════
"""
Add a sequential row_number to ALL employees ordered by salary DESC.
No PARTITION BY — one window over the whole table.

Expected result columns: name, salary, row_num
Row numbers should be 1..9, no gaps, no ties (even for equal salaries).

Hint:
  SELECT name, salary,
         ROW_NUMBER() OVER (ORDER BY salary DESC) AS row_num
  FROM employees
  ORDER BY row_num;
"""

def row_number_by_salary(conn: sqlite3.Connection) -> list:
    raise NotImplementedError(
        "TODO 1: ROW_NUMBER() OVER (ORDER BY salary DESC)"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — RANK vs DENSE_RANK: show the difference
# ════════════════════════════════════════════════════════════════════════════
"""
For ALL employees, show salary, RANK(), and DENSE_RANK() ordered by salary DESC.
No PARTITION BY.

Expected: Bob and Carol (both 80000) → same rank.
  RANK: Alice=1, Bob=2, Carol=2, Dave=4  (gap after tie: 3 skipped)
  DENSE_RANK: Alice=1, Bob=2, Carol=2, Dave=3  (no gap)

Result columns: name, salary, rnk, dense_rnk

Hint:
  SELECT name, salary,
         RANK()       OVER (ORDER BY salary DESC) AS rnk,
         DENSE_RANK() OVER (ORDER BY salary DESC) AS dense_rnk
  FROM employees
  ORDER BY salary DESC, name;
"""

def rank_vs_dense_rank(conn: sqlite3.Connection) -> list:
    raise NotImplementedError(
        "TODO 2: RANK() and DENSE_RANK() OVER (ORDER BY salary DESC)"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — PARTITION BY dept: salary rank within each department
# ════════════════════════════════════════════════════════════════════════════
"""
Rank employees by salary WITHIN each department (PARTITION BY dept_id).
Each department restarts at rank 1.

Result columns: name, dept_id, salary, dept_rank

Hint:
  SELECT name, dept_id, salary,
         DENSE_RANK() OVER (PARTITION BY dept_id ORDER BY salary DESC) AS dept_rank
  FROM employees
  ORDER BY dept_id, dept_rank;
"""

def salary_rank_per_dept(conn: sqlite3.Connection) -> list:
    raise NotImplementedError(
        "TODO 3: DENSE_RANK() OVER (PARTITION BY dept_id ORDER BY salary DESC)"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 4 — Classic Interview Problem: 2nd highest salary per department
# ════════════════════════════════════════════════════════════════════════════
"""
Find the employee(s) with the SECOND-HIGHEST salary in each department.
Use TODO 3's result as a CTE, then filter WHERE dept_rank = 2.

Pattern:
  WITH ranked AS (
      SELECT name, dept_id, salary,
             DENSE_RANK() OVER (PARTITION BY dept_id ORDER BY salary DESC) AS dept_rank
      FROM employees
  )
  SELECT name, dept_id, salary
  FROM ranked
  WHERE dept_rank = 2
  ORDER BY dept_id;

Expected:
  dept 1: Bob and Carol (both 80000 — tied for 2nd after Alice 95000)
  dept 2: Eve and Frank (both 65000 — tied for 2nd after Dave 70000)
  dept 3: Henry and Iris (both 75000 — tied for 2nd after Grace 90000)
"""

def second_highest_per_dept(conn: sqlite3.Connection) -> list:
    raise NotImplementedError(
        "TODO 4: WITH ranked AS (...DENSE_RANK()...) SELECT WHERE dept_rank = 2"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 5 — LAG: month-over-month revenue change
# ════════════════════════════════════════════════════════════════════════════
"""
For each month, show the revenue and the PREVIOUS month's revenue using LAG().
Also compute the change (revenue - prev_revenue).

Result columns: month, revenue, prev_revenue, change

LAG(col, 1) returns the value from the row 1 position before (by ORDER BY).
First row's prev_revenue = NULL.

Hint:
  SELECT month, revenue,
         LAG(revenue, 1) OVER (ORDER BY month) AS prev_revenue,
         revenue - LAG(revenue, 1) OVER (ORDER BY month) AS change
  FROM monthly_revenue
  ORDER BY month;
"""

def mom_revenue_change(conn: sqlite3.Connection) -> list:
    raise NotImplementedError(
        "TODO 5: LAG(revenue, 1) OVER (ORDER BY month)"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 6 — SUM() OVER: running cumulative total
# ════════════════════════════════════════════════════════════════════════════
"""
Compute the cumulative (running) revenue total, month by month.

Result columns: month, revenue, running_total

Hint:
  SELECT month, revenue,
         SUM(revenue) OVER (ORDER BY month
                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                           ) AS running_total
  FROM monthly_revenue
  ORDER BY month;

  Note: Without ROWS BETWEEN clause, SQLite/PostgreSQL default for ordered window
  is RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW — same result here.
  Explicit ROWS clause is clearer for interview explanations.
"""

def running_revenue_total(conn: sqlite3.Connection) -> list:
    raise NotImplementedError(
        "TODO 6: SUM(revenue) OVER (ORDER BY month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 7 — LEAD: next month's revenue
# ════════════════════════════════════════════════════════════════════════════
"""
For each month, show the NEXT month's revenue using LEAD().
Last row's next_revenue = NULL (no next month).

Result columns: month, revenue, next_revenue

Hint:
  SELECT month, revenue,
         LEAD(revenue, 1) OVER (ORDER BY month) AS next_revenue
  FROM monthly_revenue
  ORDER BY month;
"""

def next_month_revenue(conn: sqlite3.Connection) -> list:
    raise NotImplementedError(
        "TODO 7: LEAD(revenue, 1) OVER (ORDER BY month)"
    )


# ════════════════════════════════════════════════════════════════════════════
# TESTS
# ════════════════════════════════════════════════════════════════════════════

def run_tests():
    conn = setup_db()
    passed = 0
    failed = 0

    def check(label, condition, msg=""):
        nonlocal passed, failed
        if condition:
            print(f"✅ {label}")
            passed += 1
        else:
            print(f"❌ {label} — FAIL: {msg}")
            failed += 1

    # ── TODO 1 ──────────────────────────────────────────────────────────────
    print("\n── TODO 1: ROW_NUMBER ──")
    rows = row_number_by_salary(conn)
    check("1a. 9 rows returned", len(rows) == 9, f"Got {len(rows)}")
    nums = [r["row_num"] for r in rows]
    check("1b. row_num 1..9 (no gaps)", nums == list(range(1, 10)), f"Got: {nums}")
    check("1c. Alice is row 1 (highest salary 95000)",
          rows[0]["name"] == "Alice", f"First row: {dict(rows[0])}")

    # ── TODO 2 ──────────────────────────────────────────────────────────────
    print("\n── TODO 2: RANK vs DENSE_RANK ──")
    rows = rank_vs_dense_rank(conn)
    by_name = {r["name"]: dict(r) for r in rows}
    check("2a. Alice rank=1, dense_rnk=1",
          by_name["Alice"]["rnk"] == 1 and by_name["Alice"]["dense_rnk"] == 1,
          f"Got: {by_name.get('Alice')}")
    check("2b. Bob and Carol same RANK",
          by_name["Bob"]["rnk"] == by_name["Carol"]["rnk"],
          f"Bob={by_name['Bob']['rnk']}, Carol={by_name['Carol']['rnk']}")
    check("2c. RANK has gap after tie (Dave rank=4, not 3)",
          by_name["Dave"]["rnk"] == 4,
          f"Dave rnk={by_name['Dave']['rnk']} — should be 4 (gap after 2,2)")
    check("2d. DENSE_RANK no gap (Dave dense_rnk=3)",
          by_name["Dave"]["dense_rnk"] == 3,
          f"Dave dense_rnk={by_name['Dave']['dense_rnk']} — should be 3")

    # ── TODO 3 ──────────────────────────────────────────────────────────────
    print("\n── TODO 3: PARTITION BY dept ──")
    rows = salary_rank_per_dept(conn)
    by_name = {r["name"]: r["dept_rank"] for r in rows}
    check("3a. Alice rank=1 in Engineering",
          by_name.get("Alice") == 1, f"Alice dept_rank={by_name.get('Alice')}")
    check("3b. Grace rank=1 in Sales",
          by_name.get("Grace") == 1, f"Grace dept_rank={by_name.get('Grace')}")
    check("3c. Bob rank=2 in Engineering (after Alice)",
          by_name.get("Bob") == 2, f"Bob dept_rank={by_name.get('Bob')}")
    check("3d. Dave rank=1 in Marketing",
          by_name.get("Dave") == 1, f"Dave dept_rank={by_name.get('Dave')}")

    # ── TODO 4 ──────────────────────────────────────────────────────────────
    print("\n── TODO 4: 2nd highest per dept (classic interview) ──")
    rows = second_highest_per_dept(conn)
    names = {r["name"] for r in rows}
    check("4a. 6 rows (2 per dept — all tied for 2nd)",
          len(rows) == 6, f"Expected 6 (2 per dept), got {len(rows)}: {names}")
    check("4b. Bob in result (2nd in Engineering)",
          "Bob" in names, f"Got: {names}")
    check("4c. Carol in result (tied 2nd in Engineering)",
          "Carol" in names, f"Got: {names}")
    check("4d. Alice NOT in result (1st in Engineering)",
          "Alice" not in names, f"Alice shouldn't be here: {names}")

    # ── TODO 5 ──────────────────────────────────────────────────────────────
    print("\n── TODO 5: LAG — month-over-month ──")
    rows = mom_revenue_change(conn)
    check("5a. 6 rows", len(rows) == 6, f"Got {len(rows)}")
    jan = next(r for r in rows if r["month"] == "2026-01")
    feb = next(r for r in rows if r["month"] == "2026-02")
    check("5b. January prev_revenue is NULL", jan["prev_revenue"] is None,
          f"Jan prev_revenue={jan['prev_revenue']}")
    check("5c. February change = +20000",
          abs(feb["change"] - 20000) < 0.01,
          f"Feb change={feb['change']} (120000 - 100000 = 20000)")

    # ── TODO 6 ──────────────────────────────────────────────────────────────
    print("\n── TODO 6: Running total ──")
    rows = running_revenue_total(conn)
    check("6a. 6 rows", len(rows) == 6, f"Got {len(rows)}")
    by_month = {r["month"]: r["running_total"] for r in rows}
    check("6b. Jan running_total = 100000",
          abs(by_month["2026-01"] - 100000) < 0.01,
          f"Jan total={by_month['2026-01']}")
    check("6c. Feb running_total = 220000",
          abs(by_month["2026-02"] - 220000) < 0.01,
          f"Feb total={by_month['2026-02']}")
    check("6d. Jun running_total = sum of all 6 months",
          abs(by_month["2026-06"] - 740000) < 0.01,
          f"Jun total={by_month['2026-06']} (should be 740000)")

    # ── TODO 7 ──────────────────────────────────────────────────────────────
    print("\n── TODO 7: LEAD — next month ──")
    rows = next_month_revenue(conn)
    check("7a. 6 rows", len(rows) == 6, f"Got {len(rows)}")
    by_month = {r["month"]: r["next_revenue"] for r in rows}
    check("7b. Jan next_revenue = 120000",
          abs(by_month["2026-01"] - 120000) < 0.01,
          f"Got {by_month['2026-01']}")
    check("7c. Jun next_revenue is NULL (last month)",
          by_month["2026-06"] is None,
          f"Jun next_revenue={by_month['2026-06']}")

    print(f"\n{'═'*50}")
    print(f"  {passed} passed  |  {failed} failed")
    if failed == 0:
        print("  ✅ ALL PASS — Lab 02 complete!")
    else:
        print("  ❌ Fix the failing TODOs above and rerun.")
    print('═'*50)
    conn.close()


# ════════════════════════════════════════════════════════════════════════════
# SOCH (Answer ALOUD)
# ════════════════════════════════════════════════════════════════════════════
"""
Q1: ROW_NUMBER(), RANK(), DENSE_RANK() mein kya fark hai?
    Tied salaries ka example deke explain karo. (1,1,3 vs 1,1,2 vs 1,2,3)

Q2: "Find second-highest salary per department" — kaise solve karo?
    (DENSE_RANK() OVER (PARTITION BY dept_id ORDER BY salary DESC) = 2)
    RANK() kyon DENSE_RANK() se better nahi hai yahan?

Q3: LAG() aur LEAD() ka real-world use case kya hai?
    (MoM growth, comparing current vs previous period, detecting gaps)

Q4: Window function vs GROUP BY — kya difference hai?
    Kab window function prefer karoge aur kab GROUP BY?

Q5: PARTITION BY aur GROUP BY mein kya fark hai?
    (GROUP BY collapses rows; PARTITION BY keeps all rows, just groups the window)
"""

if __name__ == "__main__":
    run_tests()
