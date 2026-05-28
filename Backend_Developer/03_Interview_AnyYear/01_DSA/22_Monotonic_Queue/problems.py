"""22 — Monotonic Queue — Problems | 10 problems | Medium→Hard"""
from typing import List
from collections import deque
import heapq

# P01. Sliding Window Maximum [Hard][LC 239]
def maxSlidingWindow(nums: List[int], k: int) -> List[int]:
    dq,res=deque(),[]
    for i,n in enumerate(nums):
        while dq and nums[dq[-1]]<=n: dq.pop()
        dq.append(i)
        if dq[0]<=i-k: dq.popleft()
        if i>=k-1: res.append(nums[dq[0]])
    return res
print("P01:",maxSlidingWindow([1,3,-1,-3,5,3,6,7],3))  # [3,3,5,5,6,7]

# P02. Sliding Window Minimum (custom)
def minSlidingWindow(nums: List[int], k: int) -> List[int]:
    dq,res=deque(),[]
    for i,n in enumerate(nums):
        while dq and nums[dq[-1]]>=n: dq.pop()
        dq.append(i)
        if dq[0]<=i-k: dq.popleft()
        if i>=k-1: res.append(nums[dq[0]])
    return res
print("P02:",minSlidingWindow([2,1,5,2,3,2,4,1],3))

# P03. Longest Continuous Subarray With Absolute Diff Limit [Medium][LC 1438]
def longestSubarray(nums: List[int], limit: int) -> int:
    mx,mn,left,res=deque(),deque(),0,0
    for right,n in enumerate(nums):
        while mx and nums[mx[-1]]<=n: mx.pop()
        while mn and nums[mn[-1]]>=n: mn.pop()
        mx.append(right); mn.append(right)
        while nums[mx[0]]-nums[mn[0]]>limit:
            left+=1
            if mx[0]<left: mx.popleft()
            if mn[0]<left: mn.popleft()
        res=max(res,right-left+1)
    return res
print("P03:",longestSubarray([8,2,4,7],4))  # 2
print("P03:",longestSubarray([10,1,2,4,7,2],5))  # 4

# P04. Jump Game VI [Hard][LC 1696]
def maxResult(nums: List[int], k: int) -> int:
    n=len(nums); dp=[0]*n; dp[0]=nums[0]; dq=deque([0])
    for i in range(1,n):
        while dq and dq[0]<i-k: dq.popleft()
        dp[i]=nums[i]+dp[dq[0]]
        while dq and dp[dq[-1]]<=dp[i]: dq.pop()
        dq.append(i)
    return dp[-1]
print("P04:",maxResult([1,-1,-2,4,-7,3],2))  # 7

# P05. Max Value of Equation [Hard][LC 1499]
# yi+yj+|xi-xj| where xi-xj<=k. Maximize yi+yj+xi-xj = (yi-xi) + (yj+xj)
# For each j, maximize (yi-xi) for previous i where xj-xi<=k
def findMaxValueOfEquation(points: List[List[int]], k: int) -> int:
    dq=deque(); res=-float('inf')
    for x,y in points:
        while dq and x-dq[0][1]>k: dq.popleft()
        if dq: res=max(res,y+x+dq[0][0])
        while dq and dq[-1][0]<=y-x: dq.pop()
        dq.append((y-x,x))
    return res
print("P05:",findMaxValueOfEquation([[1,3],[2,0],[5,10],[6,-10]],1))  # 4

# P06. Shortest Subarray with Sum at Least K [Hard][LC 862]
def shortestSubarray(nums: List[int], k: int) -> int:
    n=len(nums); prefix=[0]*(n+1)
    for i in range(n): prefix[i+1]=prefix[i]+nums[i]
    dq=deque(); res=float('inf')
    for i in range(n+1):
        while dq and prefix[i]-prefix[dq[0]]>=k:
            res=min(res,i-dq.popleft())
        while dq and prefix[dq[-1]]>=prefix[i]: dq.pop()
        dq.append(i)
    return res if res!=float('inf') else -1
print("P06:",shortestSubarray([2,-1,2],3))  # 3
print("P06:",shortestSubarray([1,2],4))     # -1

# P07. Maximum Sum of Two Non-overlapping Subarrays [Medium][LC 1031]
def maxSumTwoNoOverlap(nums: List[int], firstLen: int, secondLen: int) -> int:
    n=len(nums); pre=[0]*(n+1)
    for i in range(n): pre[i+1]=pre[i]+nums[i]
    def solve(L,M):
        res=maxL=0
        for i in range(L+M,n+1):
            maxL=max(maxL,pre[i-M]-pre[i-M-L])
            res=max(res,maxL+pre[i]-pre[i-M])
        return res
    return max(solve(firstLen,secondLen),solve(secondLen,firstLen))
print("P07:",maxSumTwoNoOverlap([0,6,5,2,2,5,1,9,4],1,2))  # 20

# P08. Constrained Subsequence Sum [Hard][LC 1425]
def constrainedSubsetSum(nums: List[int], k: int) -> int:
    n=len(nums); dp=nums[:]; dq=deque()
    for i in range(n):
        if dq: dp[i]=max(dp[i],dp[i]+dq[0])
        while dq and dq[0]<=0: dq.popleft() if dq[0]<=0 else None
        while dq and dp[dq[-1] if isinstance(dq[-1],int) else 0]<=dp[i]: dq.pop() if dq else None
        # Simplified version using values directly
        pass
    # Clean implementation
    dp2=nums[:]; dq2=deque()
    for i in range(n):
        dp2[i]+=max(0,dq2[0] if dq2 else 0)
        while dq2 and dq2[-1]<=dp2[i]: dq2.pop()
        dq2.append(dp2[i])
        if len(dq2)>k: dq2.popleft()
    return max(dp2)
print("P08:",constrainedSubsetSum([10,2,-10,5,20],2))  # 37

# P09. Number of Sub-arrays of Size K with Average >= Threshold [Medium][LC 1343]
def numOfSubarrays(arr: List[int], k: int, threshold: int) -> int:
    window_sum=sum(arr[:k]); count=1 if window_sum>=k*threshold else 0
    for i in range(k,len(arr)):
        window_sum+=arr[i]-arr[i-k]
        if window_sum>=k*threshold: count+=1
    return count
print("P09:",numOfSubarrays([2,2,2,2,5,5,5,8],3,4))  # 3

# P10. Maximum Number of Robots Within Budget [Hard][LC 2398]
def maximumRobots(chargeTimes: List[int], runningCosts: List[int], budget: int) -> int:
    dq=deque(); total=0; left=0; res=0
    for right in range(len(chargeTimes)):
        total+=runningCosts[right]
        while dq and chargeTimes[dq[-1]]<=chargeTimes[right]: dq.pop()
        dq.append(right)
        while dq and chargeTimes[dq[0]]+(right-left+1)*total>budget:
            total-=runningCosts[left]
            if dq[0]==left: dq.popleft()
            left+=1
        res=max(res,right-left+1)
    return res
print("P10:",maximumRobots([3,6,1,3,4],[2,1,3,4,5],25))  # 3

"""
COMPLEXITY SUMMARY:
Sliding Window Max/Min        O(n)   O(k)   monotonic deque
Longest Subarray Abs Diff     O(n)   O(n)   two deques
Jump Game VI                  O(n)   O(k)   deque DP optimization
Max Value of Equation         O(n)   O(n)   deque + sliding constraint
Shortest Subarray Sum ≥ K     O(n)   O(n)   prefix sum + deque
Max Sum Two Non-overlap        O(n)   O(n)   prefix max + two pass
Constrained Subsequence Sum    O(n)   O(k)   deque DP
Count Subarrays Avg≥Threshold  O(n)   O(1)   sliding sum
Max Robots in Budget           O(n)   O(n)   deque + two pointer
"""
