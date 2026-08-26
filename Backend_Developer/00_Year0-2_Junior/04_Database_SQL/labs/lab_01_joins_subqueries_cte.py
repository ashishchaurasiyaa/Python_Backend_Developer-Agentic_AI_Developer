"""
Lab 01 — JOINs, Subqueries & CTEs
════════════════════════════════════════════════════════════════════════════════

ARCHITECTURE — JOIN produces a Cartesian product then filters:

    employees × departments → filter on e.dept_id = d.id
    ┌────────────────┐         ┌──────────────┐
    │ employees (e)  │ ──JOIN──│ departments  │
    │ id  name  dept │         │ id   name    │
    └────────────────┘         └──────────────┘

JOIN TYPES:
  INNER JOIN  — only matching rows from BOTH tables
  LEFT JOIN   — all rows from LEFT + matching from right (NULL for no match)
  RIGHT JOIN  — all rows from RIGHT + matching from left (rarely used; swap tables instead)
  FULL OUTER  — all rows from both, NULLs where no match
  SELF JOIN   — table joined to itself (manager/employee hierarchy)
  CROSS JOIN  — every row × every row (no ON clause; use sparingly)

SUBQUERY vs CTE vs JOIN:
  Subquery  — inline, good for one-time filters
  CTE       — named, reusable within the query, readable
  JOIN      — fastest when you need columns from both tables

INTERVIEW ANSWER:
  "JOIN duplicate rows tab aate hain jab right side mein ek row se multiple
   rows match hoti hain — jaise ek order ke multiple items. DISTINCT ya
   GROUP BY se remove karte hain, ya sirf zaroori columns JOIN karte hain."

TASK:
  1. TODO 1: INNER JOIN — employees with their department name
  2. TODO 2: LEFT JOIN — all departments, even with no employees
  3. TODO 3: Self JOIN — find each employee's manager name
  4. TODO 4: Subquery — employees earning above average salary
  5. TODO 5: EXISTS — departments that HAVE at least one employee
  6. TODO 6: CTE — top earner per department
  7. TODO 7: Correlated subquery — for each employee, count their projects

RUN: python lab_01_joins_subqueries_cte.py

Prereq: none — uses Python's built-in sqlite3
"""

import sqlite3

# ════════════════════════════════════════════════════════════════════════════
# SCHEMA + SEED DATA (do not modify)
# ════════════════════════════════════════════════════════════════════════════

def setup_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE departments (
            id   INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE employees (
            id        INTEGER PRIMARY KEY,
            name      TEXT NOT NULL,
            dept_id   INTEGER REFERENCES departments(id),
            manager_id INTEGER REFERENCES employees(id),
            salary    REAL NOT NULL
        );

        CREATE TABLE projects (
            id      INTEGER PRIMARY KEY,
            name    TEXT NOT NULL,
            emp_id  INTEGER REFERENCES employees(id)
        );

        -- Departments (one with no employees — tests LEFT JOIN)
        INSERT INTO departments VALUES (1,'Engineering'),(2,'Marketing'),(3,'HR');

        -- Employees
        INSERT INTO employees VALUES
            (1,'Alice',  1, NULL, 95000),   -- Engineering, no manager (CEO)
            (2,'Bob',    1, 1,    80000),   -- Engineering, manager=Alice
            (3,'Carol',  1, 1,    75000),   -- Engineering, manager=Alice
            (4,'Dave',   2, NULL, 70000),   -- Marketing, no manager
            (5,'Eve',    2, 4,    65000);   -- Marketing, manager=Dave
        -- HR (dept 3) has no employees

        -- Projects
        INSERT INTO projects VALUES
            (1,'Alpha',  1),(2,'Beta', 1),(3,'Gamma', 2),
            (4,'Delta',  4),(5,'Epsilon', 4),(6,'Zeta', 4);
    """)
    conn.commit()
    return conn


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — INNER JOIN: employees with their department name
# ════════════════════════════════════════════════════════════════════════════
"""
Write a query that returns:
  emp_name, dept_name, salary
For all employees — only those who HAVE a department.

Hint:
  SELECT e.name AS emp_name, d.name AS dept_name, e.salary
  FROM employees e
  INNER JOIN departments d ON e.dept_id = d.id
  ORDER BY e.salary DESC;

Expected: 5 rows (Alice, Bob, Carol, Dave, Eve)
"""

def get_employees_with_dept(conn: sqlite3.Connection) -> list[dict]:
    raise NotImplementedError(
        "TODO 1: INNER JOIN employees with departments"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — LEFT JOIN: all departments, even with no employees
# ════════════════════════════════════════════════════════════════════════════
"""
Write a query that returns ALL departments and the count of their employees.
Departments with no employees should show count = 0.

Hint:
  SELECT d.name AS dept_name, COUNT(e.id) AS emp_count
  FROM departments d
  LEFT JOIN employees e ON e.dept_id = d.id
  GROUP BY d.id, d.name
  ORDER BY d.name;

Expected: 3 rows (Engineering=3, HR=0, Marketing=2)
"""

def get_dept_employee_counts(conn: sqlite3.Connection) -> list[dict]:
    raise NotImplementedError(
        "TODO 2: LEFT JOIN departments with employees, GROUP BY dept, COUNT(e.id)"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — Self JOIN: find each employee's manager name
# ════════════════════════════════════════════════════════════════════════════
"""
Self JOIN: join employees table to itself to get manager names.

  e  = employee
  m  = manager (same table, aliased)

Hint:
  SELECT e.name AS employee, m.name AS manager
  FROM employees e
  LEFT JOIN employees m ON e.manager_id = m.id
  ORDER BY e.name;

Expected: 5 rows. Alice and Dave have NULL manager (they are top-level).
"""

def get_employees_with_managers(conn: sqlite3.Connection) -> list[dict]:
    raise NotImplementedError(
        "TODO 3: Self JOIN employees e LEFT JOIN employees m ON e.manager_id = m.id"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 4 — Subquery: employees earning above average salary
# ════════════════════════════════════════════════════════════════════════════
"""
Use a scalar subquery to find employees whose salary > average salary.

Hint:
  SELECT name, salary
  FROM employees
  WHERE salary > (SELECT AVG(salary) FROM employees)
  ORDER BY salary DESC;

Average = (95000+80000+75000+70000+65000)/5 = 77000
Expected: Alice (95000), Bob (80000)
"""

def get_above_average_earners(conn: sqlite3.Connection) -> list[dict]:
    raise NotImplementedError(
        "TODO 4: WHERE salary > (SELECT AVG(salary) FROM employees)"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 5 — EXISTS: departments that HAVE at least one employee
# ════════════════════════════════════════════════════════════════════════════
"""
Use EXISTS to find departments with at least one employee.

Hint:
  SELECT d.name
  FROM departments d
  WHERE EXISTS (
      SELECT 1 FROM employees e WHERE e.dept_id = d.id
  )
  ORDER BY d.name;

Expected: Engineering, Marketing (NOT HR — HR has no employees)
"""

def get_departments_with_employees(conn: sqlite3.Connection) -> list[dict]:
    raise NotImplementedError(
        "TODO 5: WHERE EXISTS (SELECT 1 FROM employees WHERE dept_id = d.id)"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 6 — CTE: top earner per department
# ════════════════════════════════════════════════════════════════════════════
"""
Use a CTE to find the highest-paid employee in each department.

Pattern:
  WITH dept_max AS (
      SELECT dept_id, MAX(salary) AS max_salary
      FROM employees
      GROUP BY dept_id
  )
  SELECT e.name, e.salary, d.name AS dept_name
  FROM employees e
  JOIN dept_max dm ON e.dept_id = dm.dept_id AND e.salary = dm.max_salary
  JOIN departments d ON e.dept_id = d.id
  ORDER BY e.salary DESC;

Expected: Alice (Engineering, 95000), Dave (Marketing, 70000)
"""

def get_top_earner_per_dept(conn: sqlite3.Connection) -> list[dict]:
    raise NotImplementedError(
        "TODO 6: WITH dept_max AS (...) SELECT top earner per dept"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 7 — Correlated Subquery: project count per employee
# ════════════════════════════════════════════════════════════════════════════
"""
A correlated subquery references the outer query's row in the inner query.
For each employee, count how many projects they have.

Hint:
  SELECT
      e.name,
      (SELECT COUNT(*) FROM projects p WHERE p.emp_id = e.id) AS project_count
  FROM employees e
  ORDER BY project_count DESC, e.name;

Expected:
  Alice=2, Dave=3, Bob=1, Carol=0, Eve=0
  (Alice has projects 1+2, Dave has 4+5+6, Bob has 3)
"""

def get_project_counts(conn: sqlite3.Connection) -> list[dict]:
    raise NotImplementedError(
        "TODO 7: Correlated subquery — (SELECT COUNT(*) FROM projects p WHERE p.emp_id = e.id)"
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
    print("\n── TODO 1: INNER JOIN ──")
    rows = get_employees_with_dept(conn)
    check("1a. 5 employees returned", len(rows) == 5,
          f"Expected 5 rows, got {len(rows)}")
    check("1b. has emp_name + dept_name columns",
          rows and "emp_name" in rows[0].keys() and "dept_name" in rows[0].keys(),
          f"Got columns: {list(rows[0].keys()) if rows else 'empty'}")
    check("1c. Alice in Engineering",
          any(r["emp_name"] == "Alice" and r["dept_name"] == "Engineering" for r in rows),
          "Alice+Engineering row missing")

    # ── TODO 2 ──────────────────────────────────────────────────────────────
    print("\n── TODO 2: LEFT JOIN + GROUP BY ──")
    rows = get_dept_employee_counts(conn)
    check("2a. 3 departments returned", len(rows) == 3,
          f"Expected 3, got {len(rows)}")
    by_dept = {r["dept_name"]: r["emp_count"] for r in rows}
    check("2b. Engineering=3",    by_dept.get("Engineering") == 3,   f"Got {by_dept}")
    check("2c. HR=0 (LEFT JOIN)", by_dept.get("HR") == 0,            f"Got {by_dept}")
    check("2d. Marketing=2",      by_dept.get("Marketing") == 2,     f"Got {by_dept}")

    # ── TODO 3 ──────────────────────────────────────────────────────────────
    print("\n── TODO 3: Self JOIN ──")
    rows = get_employees_with_managers(conn)
    check("3a. 5 rows returned", len(rows) == 5, f"Expected 5, got {len(rows)}")
    by_emp = {r["employee"]: r["manager"] for r in rows}
    check("3b. Alice has NULL manager",  by_emp.get("Alice") is None,
          f"Alice's manager: {by_emp.get('Alice')}")
    check("3c. Bob's manager is Alice",  by_emp.get("Bob") == "Alice",
          f"Bob's manager: {by_emp.get('Bob')}")
    check("3d. Eve's manager is Dave",   by_emp.get("Eve") == "Dave",
          f"Eve's manager: {by_emp.get('Eve')}")

    # ── TODO 4 ──────────────────────────────────────────────────────────────
    print("\n── TODO 4: Subquery — above-average salary ──")
    rows = get_above_average_earners(conn)
    names = [r["name"] for r in rows]
    check("4a. 2 employees above average (77000)",
          len(rows) == 2, f"Expected 2, got {len(rows)}: {names}")
    check("4b. Alice in result",  "Alice" in names, f"Got: {names}")
    check("4c. Bob in result",    "Bob" in names,   f"Got: {names}")
    check("4d. Carol NOT in result", "Carol" not in names, f"Carol (75000) below avg")

    # ── TODO 5 ──────────────────────────────────────────────────────────────
    print("\n── TODO 5: EXISTS ──")
    rows = get_departments_with_employees(conn)
    names = [r["name"] for r in rows]
    check("5a. 2 departments have employees", len(rows) == 2,
          f"Expected 2, got {len(rows)}")
    check("5b. Engineering in result",  "Engineering" in names, f"Got: {names}")
    check("5c. Marketing in result",    "Marketing" in names,   f"Got: {names}")
    check("5d. HR NOT in result (no employees)", "HR" not in names, f"Got: {names}")

    # ── TODO 6 ──────────────────────────────────────────────────────────────
    print("\n── TODO 6: CTE — top earner per dept ──")
    rows = get_top_earner_per_dept(conn)
    check("6a. 2 rows (one per dept with employees)",
          len(rows) == 2, f"Expected 2, got {len(rows)}")
    by_dept = {r["dept_name"]: r["name"] for r in rows}
    check("6b. Alice is Engineering top earner",
          by_dept.get("Engineering") == "Alice", f"Got: {by_dept}")
    check("6c. Dave is Marketing top earner",
          by_dept.get("Marketing") == "Dave",   f"Got: {by_dept}")

    # ── TODO 7 ──────────────────────────────────────────────────────────────
    print("\n── TODO 7: Correlated subquery — project counts ──")
    rows = get_project_counts(conn)
    by_emp = {r["name"]: r["project_count"] for r in rows}
    check("7a. 5 employees in result", len(rows) == 5, f"Got {len(rows)}")
    check("7b. Dave has 3 projects", by_emp.get("Dave") == 3, f"Got: {by_emp}")
    check("7c. Alice has 2 projects", by_emp.get("Alice") == 2, f"Got: {by_emp}")
    check("7d. Carol has 0 projects", by_emp.get("Carol") == 0, f"Got: {by_emp}")

    # ── Summary ─────────────────────────────────────────────────────────────
    print(f"\n{'═'*50}")
    print(f"  {passed} passed  |  {failed} failed")
    if failed == 0:
        print("  ✅ ALL PASS — Lab 01 complete!")
    else:
        print("  ❌ Fix the failing TODOs above and rerun.")
    print('═'*50)
    conn.close()


# ════════════════════════════════════════════════════════════════════════════
# SOCH (Answer ALOUD)
# ════════════════════════════════════════════════════════════════════════════
"""
Q1: INNER JOIN aur LEFT JOIN mein kya fark hai?
    Kab LEFT JOIN zaroori hota hai? (HR dept — no employees — wouldn't appear in INNER)

Q2: JOIN se duplicate rows kab aate hain?
    Example: ek order ke 5 line-items. Order JOIN line_items = 5 rows per order.
    Kaise prevent karo? (Only select order columns + aggregate line-items)

Q3: Subquery vs CTE vs JOIN — kab kya prefer karo?
    (CTE = readable, reusable; JOIN = fastest for column access; subquery = one-off filters)

Q4: EXISTS vs IN — kya fark hai performance mein?
    (EXISTS short-circuits on first match; IN evaluates all; EXISTS usually faster)

Q5: Correlated subquery slow kyon ho sakta hai?
    (Outer query ki har row ke liye inner query execute hoti hai — N+1 problem in SQL)
    Fix karo: JOIN ya window function use karo.
"""

if __name__ == "__main__":
    run_tests()
