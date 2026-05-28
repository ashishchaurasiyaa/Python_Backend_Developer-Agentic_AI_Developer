
"""
By the end of this lecture you will understand:
1. What is Concurrency
2. What is Parallelism
3. Difference between both
4. Real world scenarios
5. Python modules for both
6. Basic code implementation

Note: Golden Rule: "If your task is WAITING → Use Concurrency (threading)""If your task is COMPUTING → Use Parallelism (multiprocessing)

📌 CHAPTER 1 — Introduction
What are they?
Quest-> Concurrency and Parallelism are two ways to handle multiple tasks in a program.
Ans-> Both have their own use cases,choose based on the situation

Where are they used?
Real World Frameworks:
→ FastAPI    → Uses asyncio (Concurrency)
→ NumPy      → Uses multiprocessing (Parallelism)
→ Scrapy     → Uses threading (Concurrency)
→ TensorFlow → Uses multiprocessing (Parallelism)

 CHAPTER 2 — Concurrency
 Concurrency means handling multiple tasks at once by switching between them so rapidly that it appears simultaneous —
 but only ONE task is actually running at any given moment.
 Simple Analogy:
 🧑 ONE WAITER — 3 TABLES

Table 1 → Takes order ✍️
Table 2 → Takes order ✍️
Table 3 → Takes order ✍️

Waiter switches so fast between tables
that all customers feel served at once!

KEY: Still ONE waiter, ONE person
"""