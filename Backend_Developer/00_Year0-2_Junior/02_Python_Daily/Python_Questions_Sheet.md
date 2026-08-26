# Python Questions Sheet — Basic to Advanced
> Har topic ke questions hain. Answer socho, phir verify karo.
> `[ ]` = practice nahi hua | `[x]` = ho gaya

---

## LEVEL 1 — BASIC

---

### 1. Variables & Data Types

- [ ] 1. Python mein kitne basic data types hain? Naam batao.
- [ ] 2. `type()` function kya return karta hai?
- [ ] 3. `int`, `float`, `str`, `bool` mein kya difference hai?
- [ ] 4. `x = 5` aur `x = 5.0` mein kya fark hai memory mein?
- [ ] 5. `True + True` ka result kya hoga aur kyun?
- [ ] 6. `None` kya hota hai? Kab use karte hain?
- [ ] 7. Dynamic typing kya hoti hai? Python mein kaise kaam karti hai?
- [ ] 8. `is` aur `==` mein kya difference hai?
- [ ] 9. `id()` function kya karta hai?
- [ ] 10. Integer caching kya hota hai Python mein? (-5 to 256)

---

### 2. Operators

- [ ] 11. `//` aur `/` mein kya fark hai?
- [ ] 12. `%` operator kya karta hai? Example do.
- [ ] 13. `**` operator kya hai?
- [ ] 14. `and`, `or`, `not` kab short-circuit karte hain?
- [ ] 15. `3 < 5 > 2` — Python mein yeh valid hai? Result kya hoga?
- [ ] 16. `+=` aur `=` mein kya fark hai mutable objects ke liye?
- [ ] 17. Bitwise operators `&`, `|`, `^`, `~`, `<<`, `>>` kya karte hain?
- [ ] 18. `x = x or default` pattern kab use karte hain?

---

### 3. Strings

- [ ] 19. String immutable kyun hoti hai Python mein?
- [ ] 20. `'hello'[1:4]` ka output kya hoga?
- [ ] 21. `'hello'[::-1]` kya karega?
- [ ] 22. String concatenation `+` aur `join()` mein kya fark hai performance mein?
- [ ] 23. `f-string` kya hota hai? Example do.
- [ ] 24. `strip()`, `lstrip()`, `rstrip()` mein kya fark hai?
- [ ] 25. `split()` aur `split(' ')` mein kya fark hai?
- [ ] 26. `find()` aur `index()` mein kya difference hai?
- [ ] 27. `upper()`, `lower()`, `title()`, `capitalize()` kaise alag hain?
- [ ] 28. `replace()` method original string change karta hai kya?
- [ ] 29. Multiline string kaise banate hain?
- [ ] 30. `'abc' * 3` ka output kya hoga?

---

### 4. Lists

- [ ] 31. List aur tuple mein kya fundamental difference hai?
- [ ] 32. `append()` aur `extend()` mein kya fark hai?
- [ ] 33. `insert(index, value)` kaam kaise karta hai?
- [ ] 34. `remove()` aur `pop()` mein kya difference hai?
- [ ] 35. `list.sort()` aur `sorted(list)` mein kya fark hai?
- [ ] 36. Shallow copy aur deep copy mein kya fark hai?
- [ ] 37. `copy1 = original` — yeh copy hai ya reference? Kyun?
- [ ] 38. Nested list ka element kaise access karte hain?
- [ ] 39. List comprehension kya hoti hai? Example do.
- [ ] 40. `[0] * 5` kya banata hai? Nested list ke saath kya problem hoti hai?
- [ ] 41. `enumerate()` kya karta hai? Example do.
- [ ] 42. `zip()` kya karta hai? Unequal lists pe kya hota hai?
- [ ] 43. `list.count(x)` kya karta hai?
- [ ] 44. `in` operator list mein kaise kaam karta hai? Time complexity?
- [ ] 45. Negative indexing kya hota hai?

---

### 5. Tuples

- [ ] 46. Tuple immutable kyun hota hai? Kab use karte hain?
- [ ] 47. Single element tuple kaise banate hain? `(5)` aur `(5,)` mein kya fark hai?
- [ ] 48. Tuple unpacking kya hota hai? Example do.
- [ ] 49. `*` operator tuple unpacking mein kaise kaam karta hai?
- [ ] 50. Named tuple kya hota hai? Kab useful hai?
- [ ] 51. Tuple of lists — kya tuple change ho sakta hai? Explain karo.

---

### 6. Sets

- [ ] 52. Set mein duplicates kyun nahi hote?
- [ ] 53. Set ordered hota hai ya unordered?
- [ ] 54. `add()` aur `update()` mein kya fark hai?
- [ ] 55. `union()`, `intersection()`, `difference()`, `symmetric_difference()` kya karte hain?
- [ ] 56. `in` operator set mein kaise kaam karta hai? Time complexity?
- [ ] 57. Frozenset kya hota hai? Kab use karte hain?
- [ ] 58. List se set banao — duplicates hatane ka fastest tarika?

---

### 7. Dictionaries

- [ ] 59. Dictionary key kya ho sakta hai? Kya list key ban sakta hai?
- [ ] 60. `dict['key']` aur `dict.get('key')` mein kya fark hai?
- [ ] 61. `dict.get('key', default)` kab useful hai?
- [ ] 62. `keys()`, `values()`, `items()` kya return karte hain?
- [ ] 63. Dictionary iterate karne ke tarike batao.
- [ ] 64. `update()` method kya karta hai?
- [ ] 65. Dictionary comprehension kya hoti hai? Example do.
- [ ] 66. `del dict['key']` aur `dict.pop('key')` mein kya fark hai?
- [ ] 67. `setdefault()` method kya karta hai?
- [ ] 68. Python 3.7+ mein dictionary insertion order maintain karta hai kya?
- [ ] 69. Dictionary merge karne ke tarike — `|` operator (Python 3.9+).

---

### 8. Control Flow

- [ ] 70. `for` loop aur `while` loop kab prefer karte hain?
- [ ] 71. `break`, `continue`, `pass` mein kya difference hai?
- [ ] 72. `for...else` aur `while...else` kab execute hota hai?
- [ ] 73. Nested loop mein bahar waale loop se kaise nikalen?
- [ ] 74. `range(start, stop, step)` kaise kaam karta hai?
- [ ] 75. `range(10)` list hai ya object? Kya fark padta hai?

---

### 9. Functions

- [ ] 76. Positional aur keyword arguments mein kya fark hai?
- [ ] 77. `*args` kya hota hai? Example do.
- [ ] 78. `**kwargs` kya hota hai? Example do.
- [ ] 79. Default argument ka trap kya hota hai mutable objects ke saath?
- [ ] 80. Function ek object hai Python mein — iska kya matlab hai?
- [ ] 81. `return` ke baad code execute hota hai kya?
- [ ] 82. Multiple values return kaise karte hain?
- [ ] 83. Lambda function kya hoti hai? Kab use karte hain?
- [ ] 84. `map()`, `filter()` kaise kaam karte hain?
- [ ] 85. First-class function kya hoti hai?

---

## LEVEL 2 — INTERMEDIATE

---

### 10. Scope & Closures

- [ ] 86. LEGB rule kya hota hai? (Local, Enclosing, Global, Built-in)
- [ ] 87. `global` keyword kab use karte hain?
- [ ] 88. `nonlocal` keyword kab use karte hain?
- [ ] 89. Closure kya hoti hai? Example do.
- [ ] 90. Closure aur class mein kab kya prefer karte hain?
- [ ] 91. Late binding closure kya hota hai? Yeh ek common bug kyun hai?

---

### 11. OOP — Classes & Objects

- [ ] 92. Class aur object mein kya fark hai?
- [ ] 93. `__init__` method kya karta hai?
- [ ] 94. `self` parameter kya hota hai? Kyun zaroori hai?
- [ ] 95. Instance variable aur class variable mein kya fark hai?
- [ ] 96. `@classmethod` aur `@staticmethod` mein kya fark hai?
- [ ] 97. `@property` decorator kya karta hai?
- [ ] 98. Encapsulation kya hai? `_var` aur `__var` mein kya fark hai?
- [ ] 99. `__str__` aur `__repr__` mein kya fark hai?
- [ ] 100. Dunder/Magic methods kya hote hain? 5 examples do.

---

### 12. OOP — Inheritance & Polymorphism

- [ ] 101. Inheritance kya hai? `super()` kab use karte hain?
- [ ] 102. Method overriding kya hota hai?
- [ ] 103. Multiple inheritance kya hoti hai?
- [ ] 104. MRO (Method Resolution Order) kya hota hai? C3 linearization?
- [ ] 105. `isinstance()` aur `issubclass()` kya karte hain?
- [ ] 106. Abstract class kya hoti hai? `abc` module se kaise banate hain?
- [ ] 107. Duck typing kya hoti hai? Python mein kaise kaam karti hai?
- [ ] 108. Mixin kya hota hai? Kab use karte hain?

---

### 13. Exception Handling

- [ ] 109. `try/except/else/finally` ka flow kya hota hai?
- [ ] 110. `else` block exception handling mein kab run hota hai?
- [ ] 111. `finally` block kab run hota hai?
- [ ] 112. Custom exception kaise banate hain?
- [ ] 113. `raise` aur `raise from` mein kya fark hai?
- [ ] 114. Multiple exceptions ek `except` mein kaise handle karte hain?
- [ ] 115. Bare `except:` kyun dangerous hota hai?
- [ ] 116. Exception hierarchy kya hoti hai? `BaseException` vs `Exception`?

---

### 14. Iterators & Generators

- [ ] 117. Iterable aur iterator mein kya fark hai?
- [ ] 118. `__iter__` aur `__next__` kya karte hain?
- [ ] 119. Generator function kya hoti hai? `yield` kya karta hai?
- [ ] 120. Generator expression kya hoti hai? List comprehension se kya fark?
- [ ] 121. `next()` function kya karta hai?
- [ ] 122. Generator lazy hota hai — iska kya matlab hai?
- [ ] 123. `yield from` kya karta hai?
- [ ] 124. Infinite generator kaise banate hain? Example do.
- [ ] 125. Generator aur list mein memory difference kya hota hai?

---

### 15. Decorators

- [ ] 126. Decorator kya hota hai? Basic concept explain karo.
- [ ] 127. Decorator bina `@` syntax ke kaise likhte hain?
- [ ] 128. `functools.wraps` kyun zaroori hota hai decorator mein?
- [ ] 129. Arguments wala decorator kaise banate hain?
- [ ] 130. Stacked decorators kaise kaam karte hain? Order kya hota hai?
- [ ] 131. Class-based decorator kaise banate hain?
- [ ] 132. `@staticmethod`, `@classmethod`, `@property` internally decorator hain — explain karo.

---

### 16. Context Managers

- [ ] 133. `with` statement kya karta hai?
- [ ] 134. `__enter__` aur `__exit__` kya karte hain?
- [ ] 135. `contextlib.contextmanager` decorator se context manager kaise banate hain?
- [ ] 136. `__exit__` mein exception suppress kaise karte hain?
- [ ] 137. Multiple context managers ek `with` mein kaise use karte hain?

---

### 17. File I/O

- [ ] 138. File open karne ke modes kya hain? (`r`, `w`, `a`, `rb`, etc.)
- [ ] 139. `with open()` kyun prefer karte hain direct `open()` se?
- [ ] 140. `read()`, `readline()`, `readlines()` mein kya fark hai?
- [ ] 141. Large file efficiently kaise read karte hain?
- [ ] 142. Binary file aur text file mein kya fark hai?

---

### 18. Comprehensions

- [ ] 143. List, Dict, Set comprehension ka syntax likho.
- [ ] 144. Nested comprehension kaise likhte hain?
- [ ] 145. Comprehension mein condition kahan lagti hai?
- [ ] 146. Generator expression aur list comprehension mein kab kya prefer karte hain?

---

## LEVEL 3 — ADVANCED

---

### 19. Memory Management

- [ ] 147. Python mein memory management kaise hoti hai?
- [ ] 148. Reference counting kya hota hai?
- [ ] 149. Garbage collector kab kaam karta hai Python mein?
- [ ] 150. Circular reference kya hota hai? GC ise kaise handle karta hai?
- [ ] 151. `__del__` method kab call hota hai?
- [ ] 152. Memory leak Python mein kab ho sakta hai?
- [ ] 153. `sys.getsizeof()` kya karta hai?

---

### 20. Functools Module

- [ ] 154. `functools.partial` kya karta hai? Example do.
- [ ] 155. `functools.reduce()` kaise kaam karta hai?
- [ ] 156. `functools.lru_cache` kya karta hai? Kab use karte hain?
- [ ] 157. `functools.cache` aur `lru_cache` mein kya fark hai?
- [ ] 158. `functools.wraps` kyun use karte hain?
- [ ] 159. `functools.total_ordering` kya karta hai?

---

### 21. Itertools Module

- [ ] 160. `itertools.chain()` kya karta hai?
- [ ] 161. `itertools.product()` kya karta hai? Nested loop se kaise alag hai?
- [ ] 162. `itertools.combinations()` aur `itertools.permutations()` mein kya fark hai?
- [ ] 163. `itertools.groupby()` kaise kaam karta hai? Sorted hona zaroori kyun hai?
- [ ] 164. `itertools.islice()` kab useful hai?
- [ ] 165. `itertools.cycle()` kya karta hai?

---

### 22. Collections Module

- [ ] 166. `collections.defaultdict` kya hota hai? Regular dict se kya fark?
- [ ] 167. `collections.Counter` kya karta hai? `most_common()` kya return karta hai?
- [ ] 168. `collections.deque` kya hai? List se kab better hai?
- [ ] 169. `collections.OrderedDict` Python 3.7+ mein relevant hai kya? Kyun?
- [ ] 170. `collections.namedtuple` kab use karte hain?

---

### 23. Typing & Type Hints

- [ ] 171. Type hints kya hote hain? Runtime pe enforce hote hain kya?
- [ ] 172. `Optional[str]` ka matlab kya hai?
- [ ] 173. `Union[int, str]` kya hota hai? `int | str` (Python 3.10+) se kya fark?
- [ ] 174. `List[int]` aur `list[int]` mein kya fark hai?
- [ ] 175. `TypeVar` kab use karte hain?
- [ ] 176. `Protocol` kya hota hai? Abstract class se kaise alag hai?
- [ ] 177. `Any` type kab use karna chahiye?
- [ ] 178. `TypedDict` kya hota hai?

---

### 24. Dataclasses

- [ ] 179. `@dataclass` decorator kya karta hai?
- [ ] 180. `field()` function kab use karte hain?
- [ ] 181. `frozen=True` kya karta hai dataclass mein?
- [ ] 182. `__post_init__` kab run hota hai?
- [ ] 183. Dataclass vs NamedTuple vs regular class — kab kya prefer karo?
- [ ] 184. Dataclass inheritance kaise kaam karta hai?

---

### 25. Concurrency — Threading

- [ ] 185. Thread kya hota hai? Process se kya fark?
- [ ] 186. GIL (Global Interpreter Lock) kya hai? CPU-bound vs IO-bound pe kya impact?
- [ ] 187. `threading.Thread` kaise banate hain?
- [ ] 188. `daemon=True` thread kya hota hai?
- [ ] 189. Race condition kya hoti hai? Example do.
- [ ] 190. `threading.Lock` kaise kaam karta hai?
- [ ] 191. `threading.Event` kab use karte hain?
- [ ] 192. `ThreadPoolExecutor` kab prefer karte hain direct Thread se?

---

### 26. Concurrency — Multiprocessing

- [ ] 193. Multiprocessing threading se kab better hota hai?
- [ ] 194. `Process` vs `Pool` mein kya fark hai?
- [ ] 195. Processes ke beech data share kaise karte hain?
- [ ] 196. `Queue` vs `Pipe` mein kya fark hai?
- [ ] 197. `ProcessPoolExecutor` kya karta hai?

---

### 27. Async / Await

- [ ] 198. Async programming kya hoti hai? Threading se kab better hai?
- [ ] 199. `async def` aur regular `def` mein kya fark hai?
- [ ] 200. `await` kya karta hai? Kahan use kar sakte hain?
- [ ] 201. Event loop kya hota hai? Kaise kaam karta hai?
- [ ] 202. `asyncio.gather()` kya karta hai?
- [ ] 203. `asyncio.create_task()` aur `await coroutine` mein kya fark hai?
- [ ] 204. Coroutine kya hoti hai?
- [ ] 205. `async for` aur `async with` kab use karte hain?
- [ ] 206. Async generator kya hota hai?
- [ ] 207. Blocking code async mein kaise handle karte hain? (`run_in_executor`)

---

### 28. Metaclasses & Descriptors

- [ ] 208. Metaclass kya hota hai? `type` kya hai Python mein?
- [ ] 209. `__new__` aur `__init__` mein kya fark hai?
- [ ] 210. Custom metaclass kaise banate hain?
- [ ] 211. Descriptor kya hota hai? `__get__`, `__set__`, `__delete__` kya karte hain?
- [ ] 212. Data descriptor aur non-data descriptor mein kya fark hai?
- [ ] 213. `__slots__` kya karta hai? Kab use karte hain?

---

### 29. Python Internals

- [ ] 214. Python bytecode kya hota hai? `dis` module se kaise dekhte hain?
- [ ] 215. `.pyc` files kya hoti hain?
- [ ] 216. `__name__ == '__main__'` kyun use karte hain?
- [ ] 217. Import system kaise kaam karta hai? `sys.modules` kya hai?
- [ ] 218. Circular imports se kaise bachte hain?
- [ ] 219. `__all__` kya hota hai module mein?
- [ ] 220. `globals()` aur `locals()` kya return karte hain?

---

### 30. Design Patterns in Python

- [ ] 221. Singleton pattern Python mein kaise implement karte hain?
- [ ] 222. Factory pattern kya hota hai? Example do.
- [ ] 223. Observer pattern kaise implement karte hain?
- [ ] 224. Strategy pattern kya hota hai?
- [ ] 225. `__new__` method Singleton mein kaise use karte hain?

---

### 31. Testing

- [ ] 226. Unit test kya hota hai? Integration test se kya fark?
- [ ] 227. `unittest` vs `pytest` — kya prefer karte hain aur kyun?
- [ ] 228. Mock kya hota hai? `unittest.mock` kaise kaam karta hai?
- [ ] 229. `@patch` decorator kya karta hai?
- [ ] 230. Fixture kya hota hai pytest mein?
- [ ] 231. `assert` kya karta hai? Production mein kyun disable ho sakta hai?

---

### 32. Performance & Profiling

- [ ] 232. `cProfile` se code kaise profile karte hain?
- [ ] 233. `timeit` module kab use karte hain?
- [ ] 234. List comprehension `for` loop se fast kyun hoti hai?
- [ ] 235. String concatenation loop mein slow kyun hoti hai? Solution kya hai?
- [ ] 236. `__slots__` performance kyun improve karta hai?
- [ ] 237. NumPy Python list se fast kyun hota hai?

---

## BONUS — Tricky Questions (Interview Favorites)

- [ ] 238. `[] == []` aur `[] is []` ka result kya hoga?
- [ ] 239. `a = [1,2,3]; b = a; b.append(4)` — `a` kya hoga?
- [ ] 240. Mutable default argument trap — kya galat hai is code mein?
  ```
  def add(item, lst=[]):
      lst.append(item)
      return lst
  ```
- [ ] 241. `0.1 + 0.2 == 0.3` — True hai ya False? Kyun?
- [ ] 242. `list(range(10))` aur `[*range(10)]` mein kya fark hai?
- [ ] 243. `x = y = []` — kya yeh do alag lists hain?
- [ ] 244. `print(type(lambda: None))` kya output dega?
- [ ] 245. Generator already exhausted ho toh kya hota hai?
- [ ] 246. `sorted()` aur `.sort()` mein kya return difference hai?
- [ ] 247. Python mein `switch` statement kyun nahi hota? Alternative kya hai?
- [ ] 248. `__init__.py` file kya kaam karti hai?
- [ ] 249. Walrus operator `:=` kya karta hai? Python 3.8+
- [ ] 250. `dict` aur `set` dono hash table use karte hain — performance impact?

---

## Progress Tracker

| Level | Total | Done |
|---|---|---|
| Basic (1-75) | 75 | — |
| Intermediate (76-145) | 70 | — |
| Advanced (146-237) | 92 | — |
| Bonus (238-250) | 13 | — |
| **Total** | **250** | **—** |

---

> **Strategy:**
> - Ek topic ke questions padho
> - Apne words mein answer socho (code mat likho)
> - Agar stuck ho → us Day ka file open karo
> - `[ ]` ko `[x]` karo jab confident ho
