"""23 — Game Theory & Randomized — Problems | 10 problems"""
from typing import List, Optional
from functools import lru_cache
import random, bisect

# P01. Predict the Winner [Medium][LC 486]
def predictTheWinner(nums: List[int]) -> bool:
    @lru_cache(maxsize=None)
    def dp(i,j):
        if i==j: return nums[i]
        return max(nums[i]-dp(i+1,j), nums[j]-dp(i,j-1))
    return dp(0,len(nums)-1)>=0
print("P01:",predictTheWinner([1,5,2]))       # False
print("P01:",predictTheWinner([1,5,233,7]))   # True

# P02. Stone Game [Easy][LC 877]
def stoneGame(piles: List[int]) -> bool: return True  # First player always wins
print("P02:",stoneGame([5,3,4,5]))  # True

# P03. Nim Game [Easy][LC 292]
def canWinNim(n: int) -> bool: return n%4!=0
print("P03:",canWinNim(4))  # False
print("P03:",canWinNim(5))  # True

# P04. Stone Game III [Hard][LC 1406]
def stoneGameIII(stoneValue: List[int]) -> str:
    n=len(stoneValue)
    @lru_cache(maxsize=None)
    def dp(i):
        if i>=n: return 0
        best=-float('inf')
        total=0
        for k in range(1,4):
            if i+k>n: break
            total+=stoneValue[i+k-1]
            best=max(best,total-dp(i+k))
        return best
    res=dp(0)
    return "Alice" if res>0 else "Bob" if res<0 else "Tie"
print("P04:",stoneGameIII([1,2,3,7]))  # "Bob"
print("P04:",stoneGameIII([1,2,3,-9]))  # "Alice"

# P05. Can I Win [Medium][LC 464]
def canIWin(maxChoosableInteger: int, desiredTotal: int) -> bool:
    if desiredTotal<=0: return True
    if maxChoosableInteger*(maxChoosableInteger+1)//2<desiredTotal: return False
    @lru_cache(maxsize=None)
    def dp(used,remaining):
        for i in range(1,maxChoosableInteger+1):
            if not (used>>i&1):
                if i>=remaining or not dp(used|(1<<i),remaining-i):
                    return True
        return False
    return dp(0,desiredTotal)
print("P05:",canIWin(10,11))  # False
print("P05:",canIWin(10,0))   # True

# P06. Shuffle an Array [Medium][LC 384]
class Solution384:
    def __init__(self,nums): self.orig=nums[:]; self.nums=nums[:]
    def reset(self): self.nums=self.orig[:]; return self.nums
    def shuffle(self):
        n=len(self.nums)
        for i in range(n-1,0,-1):
            j=random.randint(0,i); self.nums[i],self.nums[j]=self.nums[j],self.nums[i]
        return self.nums
s=Solution384([1,2,3]); print("P06 shuffle:",s.shuffle()); print("P06 reset:",s.reset())

# P07. Random Pick with Weight [Medium][LC 528]
class Solution528:
    def __init__(self,w):
        self.prefix=[0]*len(w)
        self.prefix[0]=w[0]
        for i in range(1,len(w)): self.prefix[i]=self.prefix[i-1]+w[i]
    def pickIndex(self):
        target=random.randint(1,self.prefix[-1])
        return bisect.bisect_left(self.prefix,target)
s528=Solution528([1,3]); picks=[s528.pickIndex() for _ in range(400)]
print("P07: index0≈100:",picks.count(0),"index1≈300:",picks.count(1))

# P08. Linked List Random Node [Medium][LC 382]
class ListNode:
    def __init__(self,val=0,next=None): self.val=val;self.next=next
class Solution382:
    def __init__(self,head):
        self.head=head
    def getRandom(self):
        res,node,i=self.head,self.head,1
        while node:
            if random.randint(1,i)==1: res=node
            node=node.next; i+=1
        return res.val
# Build list 1->2->3->4->5
head=ListNode(1,ListNode(2,ListNode(3,ListNode(4,ListNode(5)))))
s382=Solution382(head)
print("P08 random from list:",[s382.getRandom() for _ in range(5)])

# P09. Kth Largest Element [Medium][LC 215]
def findKthLargest(nums: List[int], k: int) -> int:
    def partition(lo,hi):
        p=random.randint(lo,hi); nums[p],nums[hi]=nums[hi],nums[p]
        pivot=nums[hi]; i=lo
        for j in range(lo,hi):
            if nums[j]>=pivot: nums[i],nums[j]=nums[j],nums[i]; i+=1
        nums[i],nums[hi]=nums[hi],nums[i]; return i
    lo,hi,target=0,len(nums)-1,k-1
    while lo<=hi:
        pp=partition(lo,hi)
        if pp==target: return nums[pp]
        elif pp<target: lo=pp+1
        else: hi=pp-1
    return -1
print("P09:",findKthLargest([3,2,1,5,6,4],2))  # 5

# P10. Random Point in Non-overlapping Rectangles [Medium][LC 497]
class Solution497:
    def __init__(self,rects):
        self.rects=rects
        areas=[(x2-x1+1)*(y2-y1+1) for x1,y1,x2,y2 in rects]
        self.prefix=[0]; s=0
        for a in areas: s+=a; self.prefix.append(s)
        self.total=s
    def pick(self):
        target=random.randint(1,self.total)
        idx=bisect.bisect_left(self.prefix,target)-1
        x1,y1,x2,y2=self.rects[idx]
        return [random.randint(x1,x2),random.randint(y1,y2)]
s497=Solution497([[-2,-2,-1,-1],[1,0,3,0]])
print("P10:",s497.pick())

"""
COMPLEXITY SUMMARY:
Predict Winner         O(n²)   O(n²) memoization
Stone Game             O(1)    O(1)  math insight
Nim Game               O(1)    O(1)  n%4
Stone Game III         O(n)    O(n)  DP last 3 choices
Can I Win              O(2^n)  O(2^n) bitmask DP
Shuffle Array          O(n)    O(n)  Fisher-Yates
Random Pick Weight     O(log n) O(n) prefix sum + bisect
Linked List Random     O(n)    O(1)  reservoir sampling
Kth Largest            O(n)avg O(1)  randomized quickselect
Random Rectangle       O(log n) O(n) prefix area + bisect
"""
