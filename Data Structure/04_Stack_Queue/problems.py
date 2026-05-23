"""
╔══════════════════════════════════════════════════════════════════╗
║           STACK & QUEUE — 12 LeetCode-Style Problems             ║
╚══════════════════════════════════════════════════════════════════╝
"""

from typing import List, Optional
from collections import deque

# ══════════════════════════════════════════════════════════════════
# Problem 1: Valid Parentheses (LC 20)
# ══════════════════════════════════════════════════════════════════
def isValid(s: str) -> bool:
    """
    Given a string s containing '(', ')', '{', '}', '[', ']',
    determine if the input string is valid.
    Valid means: brackets are closed in the correct order.

    Approach: Use a stack. Push opening brackets.
    On closing bracket, check stack top matches.

    Example:
      "()[]{}" → True
      "([)]"   → False
      "{[]}"   → True
    """
    stack = []
    mapping = {')': '(', ']': '[', '}': '{'}
    for ch in s:
        if ch in '([{':
            stack.append(ch)
        else:
            if not stack or stack[-1] != mapping[ch]:
                return False
            stack.pop()
    return not stack

print("=== Valid Parentheses ===")
print(isValid("()[]{}"))  # True
print(isValid("([)]"))    # False
print(isValid("{[]}"))    # True
# Time: O(n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 2: Min Stack (LC 155)
# ══════════════════════════════════════════════════════════════════
class MinStack:
    """
    Design a stack that supports push, pop, top, and retrieving the
    minimum element in constant time.

    Approach: Store (value, current_min) pairs so each stack state
    remembers the minimum at that point in time.

    Example:
      push(-2), push(0), push(-3)
      getMin() → -3
      pop()
      top()    → 0
      getMin() → -2
    """
    def __init__(self):
        self.stack = []  # (val, min_at_this_point)

    def push(self, val: int) -> None:
        cur_min = min(val, self.stack[-1][1]) if self.stack else val
        self.stack.append((val, cur_min))

    def pop(self) -> None:
        self.stack.pop()

    def top(self) -> int:
        return self.stack[-1][0]

    def getMin(self) -> int:
        return self.stack[-1][1]

print("\n=== Min Stack ===")
ms = MinStack()
ms.push(-2); ms.push(0); ms.push(-3)
print(ms.getMin())  # -3
ms.pop()
print(ms.top())     # 0
print(ms.getMin())  # -2
# Time: O(1) all ops | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 3: Evaluate Reverse Polish Notation (LC 150)
# ══════════════════════════════════════════════════════════════════
def evalRPN(tokens: List[str]) -> int:
    """
    Evaluate the value of an arithmetic expression in Reverse Polish Notation.
    Valid operators: +, -, *, /. Division truncates toward zero.

    Approach: Stack. Numbers → push. Operator → pop two, compute, push.

    Example:
      ["2","1","+","3","*"] → 9   ((2+1)*3)
      ["4","13","5","/","+"] → 6  (4+(13/5))
    """
    stack = []
    for tok in tokens:
        if tok not in {'+', '-', '*', '/'}:
            stack.append(int(tok))
        else:
            b, a = stack.pop(), stack.pop()
            if tok == '+': stack.append(a + b)
            elif tok == '-': stack.append(a - b)
            elif tok == '*': stack.append(a * b)
            elif tok == '/': stack.append(int(a / b))
    return stack[0]

print("\n=== Evaluate RPN ===")
print(evalRPN(["2","1","+","3","*"]))     # 9
print(evalRPN(["4","13","5","/","+"]))    # 6
print(evalRPN(["10","6","9","3","+","-11","*","/","*","17","+","5","+"]))  # 22
# Time: O(n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 4: Generate Parentheses (LC 22)
# ══════════════════════════════════════════════════════════════════
def generateParenthesis(n: int) -> List[str]:
    """
    Given n pairs of parentheses, generate all combinations of
    well-formed parentheses.

    Approach: Backtracking with a stack/string.
    - Can add '(' if open count < n
    - Can add ')' if close count < open count

    Example: n=3 → ["((()))","(()())","(())()","()(())","()()()"]
    """
    result = []
    def backtrack(s, open_cnt, close_cnt):
        if len(s) == 2 * n:
            result.append(s)
            return
        if open_cnt < n:
            backtrack(s + '(', open_cnt + 1, close_cnt)
        if close_cnt < open_cnt:
            backtrack(s + ')', open_cnt, close_cnt + 1)
    backtrack("", 0, 0)
    return result

print("\n=== Generate Parentheses ===")
print(generateParenthesis(3))
# Time: O(4^n / sqrt(n)) Catalan | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 5: Daily Temperatures (LC 739) — Monotonic Stack
# ══════════════════════════════════════════════════════════════════
def dailyTemperatures(temperatures: List[int]) -> List[int]:
    """
    Given an array of daily temperatures, return an array where
    answer[i] = number of days until a warmer temperature.
    If no future warmer day exists, answer[i] = 0.

    Approach: Monotonic decreasing stack (stores indices).
    When we find a warmer day, pop and record the gap.

    Example:
      [73,74,75,71,69,72,76,73] → [1,1,4,2,1,1,0,0]
    """
    n = len(temperatures)
    answer = [0] * n
    stack = []  # indices of temperatures waiting for a warmer day

    for i, temp in enumerate(temperatures):
        while stack and temp > temperatures[stack[-1]]:
            j = stack.pop()
            answer[j] = i - j
        stack.append(i)

    return answer

print("\n=== Daily Temperatures ===")
print(dailyTemperatures([73,74,75,71,69,72,76,73]))  # [1,1,4,2,1,1,0,0]
print(dailyTemperatures([30,40,50,60]))               # [1,1,1,0]
# Time: O(n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 6: Car Fleet (LC 853)
# ══════════════════════════════════════════════════════════════════
def carFleet(target: int, position: List[int], speed: List[int]) -> int:
    """
    n cars going to the same destination. Car at position[i] has speed[i].
    A car that catches up to a slower car forms a fleet (moves at slower speed).
    Return the number of car fleets that arrive at destination.

    Approach: Sort by position descending. Compute time to reach target.
    If current car's time <= top of stack, it joins that fleet.
    Otherwise it's a new fleet (push to stack).

    Example:
      target=12, position=[10,8,0,5,3], speed=[2,4,1,1,3] → 3
    """
    pairs = sorted(zip(position, speed), reverse=True)
    stack = []  # stores arrival times (fleets)

    for pos, spd in pairs:
        time = (target - pos) / spd
        if not stack or time > stack[-1]:
            stack.append(time)  # new fleet
        # else: merges into the fleet ahead (time <= top), don't push

    return len(stack)

print("\n=== Car Fleet ===")
print(carFleet(12, [10,8,0,5,3], [2,4,1,1,3]))  # 3
print(carFleet(10, [3], [3]))                     # 1
# Time: O(n log n) sorting | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 7: Largest Rectangle in Histogram (LC 84) — Monotonic Stack
# ══════════════════════════════════════════════════════════════════
def largestRectangleArea(heights: List[int]) -> int:
    """
    Given an array of bar heights (width=1 each), find the largest
    rectangle area in the histogram.

    Approach: Monotonic increasing stack.
    - Push index when height increases (can extend left).
    - When height decreases, pop and compute area using current index as right
      boundary and new stack top as left boundary.
    - Append 0 sentinel to flush remaining stack.

    Example:
      [2,1,5,6,2,3] → 10
    """
    stack = []  # (index, height) - index = start of this bar's reach
    max_area = 0
    heights = heights + [0]  # sentinel to flush stack

    for i, h in enumerate(heights):
        start = i
        while stack and h < stack[-1][1]:
            idx, height = stack.pop()
            width = i - idx
            max_area = max(max_area, height * width)
            start = idx  # current bar can extend back to popped bar's start
        stack.append((start, h))

    return max_area

print("\n=== Largest Rectangle in Histogram ===")
print(largestRectangleArea([2,1,5,6,2,3]))  # 10
print(largestRectangleArea([2,4]))           # 4
# Time: O(n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 8: Implement Queue using Stacks (LC 232)
# ══════════════════════════════════════════════════════════════════
class MyQueue:
    """
    Implement a FIFO queue using only two stacks.

    Approach:
      stack_in: receives all pushes
      stack_out: provides pops (in reversed order = FIFO)

    When popping/peeking, if stack_out is empty, pour all from stack_in.
    Amortized O(1) per operation.

    Example:
      push(1), push(2), peek() → 1, pop() → 1, empty() → False
    """
    def __init__(self):
        self.stack_in = []   # for push
        self.stack_out = []  # for pop/peek

    def push(self, x: int) -> None:
        self.stack_in.append(x)

    def _transfer(self):
        if not self.stack_out:
            while self.stack_in:
                self.stack_out.append(self.stack_in.pop())

    def pop(self) -> int:
        self._transfer()
        return self.stack_out.pop()

    def peek(self) -> int:
        self._transfer()
        return self.stack_out[-1]

    def empty(self) -> bool:
        return not self.stack_in and not self.stack_out

print("\n=== Implement Queue using Stacks ===")
mq = MyQueue()
mq.push(1); mq.push(2)
print(mq.peek())   # 1
print(mq.pop())    # 1
print(mq.empty())  # False
# Time: O(1) amortized | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 9: Sliding Window Maximum (LC 239) — Monotonic Deque
# ══════════════════════════════════════════════════════════════════
def maxSlidingWindow(nums: List[int], k: int) -> List[int]:
    """
    Return the maximum value in each sliding window of size k.

    Approach: Monotonic decreasing deque (stores indices).
    - Remove front if it's out of window.
    - Remove rear while rear element < current (can't be max).
    - Front is always the current window's maximum.

    Example:
      nums=[1,3,-1,-3,5,3,6,7], k=3 → [3,3,5,5,6,7]
    """
    dq = deque()   # monotonic decreasing: stores indices
    result = []

    for i in range(len(nums)):
        # Remove out-of-window indices from front
        if dq and dq[0] < i - k + 1:
            dq.popleft()
        # Maintain decreasing order: remove smaller elements from rear
        while dq and nums[i] >= nums[dq[-1]]:
            dq.pop()
        dq.append(i)
        # Window is fully formed
        if i >= k - 1:
            result.append(nums[dq[0]])

    return result

print("\n=== Sliding Window Maximum ===")
print(maxSlidingWindow([1,3,-1,-3,5,3,6,7], 3))  # [3,3,5,5,6,7]
print(maxSlidingWindow([1], 1))                    # [1]
# Time: O(n) | Space: O(k)

# ══════════════════════════════════════════════════════════════════
# Problem 10: Decode String (LC 394)
# ══════════════════════════════════════════════════════════════════
def decodeString(s: str) -> str:
    """
    Given an encoded string, return its decoded version.
    Format: k[encoded_string] means repeat encoded_string k times.

    Approach: Stack-based. When we see '[', push (current_str, current_num).
    When we see ']', pop and repeat current string.

    Example:
      "3[a]2[bc]"    → "aaabcbc"
      "3[a2[c]]"     → "accaccacc"
      "2[abc]3[cd]ef" → "abcabccdcdcdef"
    """
    stack = []
    current_str = ""
    current_num = 0

    for ch in s:
        if ch.isdigit():
            current_num = current_num * 10 + int(ch)
        elif ch == '[':
            stack.append((current_str, current_num))
            current_str = ""
            current_num = 0
        elif ch == ']':
            prev_str, num = stack.pop()
            current_str = prev_str + num * current_str
        else:
            current_str += ch

    return current_str

print("\n=== Decode String ===")
print(decodeString("3[a]2[bc]"))     # aaabcbc
print(decodeString("3[a2[c]]"))      # accaccacc
print(decodeString("2[abc]3[cd]ef")) # abcabccdcdcdef
# Time: O(max_k * n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 11: Basic Calculator II (LC 227)
# ══════════════════════════════════════════════════════════════════
def calculate(s: str) -> int:
    """
    Implement a basic calculator to evaluate a string expression
    containing +, -, *, / (no parentheses, integers only).

    Approach: Stack-based.
    - Track current number and last operator.
    - On + or -: push number (with sign) onto stack.
    - On * or /: pop top, compute with current number, push result.
    - At end: sum the stack.

    Example:
      "3+2*2" → 7
      " 3/2 " → 1
      " 3+5 / 2 " → 5
    """
    stack = []
    num = 0
    op = '+'
    s = s.strip()

    for i, ch in enumerate(s):
        if ch.isdigit():
            num = num * 10 + int(ch)
        if ch in '+-*/' or i == len(s) - 1:
            if op == '+':
                stack.append(num)
            elif op == '-':
                stack.append(-num)
            elif op == '*':
                stack.append(stack.pop() * num)
            elif op == '/':
                stack.append(int(stack.pop() / num))  # truncate toward 0
            op = ch
            num = 0

    return sum(stack)

print("\n=== Basic Calculator II ===")
print(calculate("3+2*2"))     # 7
print(calculate(" 3/2 "))     # 1
print(calculate(" 3+5 / 2 ")) # 5
# Time: O(n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 12: Trapping Rain Water (LC 42) — Stack Approach
# ══════════════════════════════════════════════════════════════════
def trap(height: List[int]) -> int:
    """
    Given n non-negative integers representing elevation map,
    compute how much water can be trapped after raining.

    Stack Approach:
    - Maintain a decreasing stack of bar indices.
    - When we find a bar taller than the top, we found a valley.
    - Water = width * min(left_wall, right_wall) - bottom_height

    Example:
      [0,1,0,2,1,0,1,3,2,1,2,1] → 6
      [4,2,0,3,2,5] → 9
    """
    stack = []
    water = 0

    for i, h in enumerate(height):
        while stack and h > height[stack[-1]]:
            bottom_idx = stack.pop()
            if not stack:
                break
            left_idx = stack[-1]
            width = i - left_idx - 1
            bounded_height = min(height[left_idx], h) - height[bottom_idx]
            water += width * bounded_height
        stack.append(i)

    return water

print("\n=== Trapping Rain Water ===")
print(trap([0,1,0,2,1,0,1,3,2,1,2,1]))  # 6
print(trap([4,2,0,3,2,5]))               # 9
# Time: O(n) | Space: O(n)

print("\n✓ All 12 Stack & Queue problems solved!")
