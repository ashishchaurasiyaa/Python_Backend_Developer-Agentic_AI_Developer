"""
# Q3 — Generator pipeline
# numbers(n)      → 1 to n generate karo
# squares(gen)    → har number ka square
# evens(gen)      → sirf even squares
# Pipeline:
# result = evens(squares(numbers(20)))
# print(list(result))

"Generators are single-use iterators. Once consumed, they cannot be reused because they don’t store data — they generate it on the fly."
"Generator ko dubara use karna hai to dubara banana padega"
This pipeline demonstrates lazy evaluation where each transformation is applied step-by-step without storing intermediate results, making it memory efficient
Iterable kya hota hai?
Jo object loop ho sakta hai
__iter__() method hota hai
Iterator kya hota hai?
Jo ek-ek item return karta hai
Iterator = “object that gives next value one by one”
Generator kya hota hai?
Special type of iterator
yield use karta hai
lazy execution karta hai
Generator = “lazy iterator created using yield”
Har generator = iterator
Har iterator = generator
Generator vs Iterator (deep)
Iterator (manual)
tu khud class likhega
state manage karega
Generator
Python khud state manage karta hai
sirf yield likhna hota hai
8. Real-world analogy
Iterable = Warehouse
pura data stored
Iterator = Worker
ek-ek item la raha hai
Generator = Machine
demand pe item bana raha hai
An iterable is a collection that can return an iterator.
An iterator is an object that produces values one at a time using next().
A generator is a special kind of iterator implemented using yield, which provides
lazy evaluation and memory efficiency.
"""

def numbers(n):
    for i in range(1, n+1):
        yield i


def squares(gen):
    for i in gen:
        yield i*i


def evens(gen):
    for i in gen:
        if i % 2 == 0:
            yield i

numbers_gen = numbers(20)
squares_gen = squares(numbers_gen)
evens_gen = evens(squares_gen)
print(list(evens(squares(numbers(20)))))