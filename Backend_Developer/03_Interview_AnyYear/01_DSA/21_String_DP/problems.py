"""21 — String DP — Problems | 12 problems | Medium→Hard"""
from typing import List
from functools import lru_cache

# P01. Edit Distance [Hard][LC 72]
def minDistance(word1: str, word2: str) -> int:
    m,n=len(word1),len(word2); dp=list(range(n+1))
    for i in range(1,m+1):
        prev=dp[0]; dp[0]=i
        for j in range(1,n+1):
            temp=dp[j]
            dp[j]=prev if word1[i-1]==word2[j-1] else 1+min(prev,dp[j],dp[j-1])
            prev=temp
    return dp[n]
print("P01 edit_dist('horse','ros'):",minDistance("horse","ros"))  # 3

# P02. Longest Common Subsequence [Medium][LC 1143]
def longestCommonSubsequence(text1: str, text2: str) -> int:
    m,n=len(text1),len(text2); dp=[[0]*(n+1) for _ in range(m+1)]
    for i in range(1,m+1):
        for j in range(1,n+1):
            dp[i][j]=dp[i-1][j-1]+1 if text1[i-1]==text2[j-1] else max(dp[i-1][j],dp[i][j-1])
    return dp[m][n]
print("P02 LCS('abcde','ace'):",longestCommonSubsequence("abcde","ace"))  # 3

# P03. Longest Palindromic Subsequence [Medium][LC 516]
def longestPalindromeSubseq(s: str) -> int:
    n=len(s); dp=[[0]*n for _ in range(n)]
    for i in range(n): dp[i][i]=1
    for l in range(2,n+1):
        for i in range(n-l+1):
            j=i+l-1
            dp[i][j]=(dp[i+1][j-1]+2 if l>2 else 2) if s[i]==s[j] else max(dp[i+1][j],dp[i][j-1])
    return dp[0][n-1]
print("P03 LPS('bbbab'):",longestPalindromeSubseq("bbbab"))  # 4

# P04. Palindrome Partitioning II [Hard][LC 132]
def minCut(s: str) -> int:
    n=len(s)
    is_pal=[[False]*n for _ in range(n)]
    for i in range(n): is_pal[i][i]=True
    for l in range(2,n+1):
        for i in range(n-l+1):
            j=i+l-1
            is_pal[i][j]=(s[i]==s[j]) and (l==2 or is_pal[i+1][j-1])
    dp=[float('inf')]*n; dp[0]=0
    for i in range(1,n):
        if is_pal[0][i]: dp[i]=0; continue
        for j in range(1,i+1):
            if is_pal[j][i]: dp[i]=min(dp[i],dp[j-1]+1)
    return dp[n-1]
print("P04 minCut('aab'):",minCut("aab"))  # 1

# P05. Distinct Subsequences [Hard][LC 115]
def numDistinct(s: str, t: str) -> int:
    m,n=len(s),len(t); dp=[[0]*(n+1) for _ in range(m+1)]
    for i in range(m+1): dp[i][0]=1
    for i in range(1,m+1):
        for j in range(1,n+1):
            dp[i][j]=dp[i-1][j]+(dp[i-1][j-1] if s[i-1]==t[j-1] else 0)
    return dp[m][n]
print("P05 distinct_subseq('rabbbit','rabbit'):",numDistinct("rabbbit","rabbit"))  # 3

# P06. Interleaving String [Medium][LC 97]
def isInterleave(s1: str, s2: str, s3: str) -> bool:
    m,n=len(s1),len(s2)
    if m+n!=len(s3): return False
    dp=[[False]*(n+1) for _ in range(m+1)]; dp[0][0]=True
    for i in range(1,m+1): dp[i][0]=dp[i-1][0] and s1[i-1]==s3[i-1]
    for j in range(1,n+1): dp[0][j]=dp[0][j-1] and s2[j-1]==s3[j-1]
    for i in range(1,m+1):
        for j in range(1,n+1):
            dp[i][j]=(dp[i-1][j] and s1[i-1]==s3[i+j-1]) or (dp[i][j-1] and s2[j-1]==s3[i+j-1])
    return dp[m][n]
print("P06 isInterleave('aabcc','dbbca','aadbbcbcac'):",isInterleave("aabcc","dbbca","aadbbcbcac"))  # True

# P07. Word Break [Medium][LC 139]
def wordBreak(s: str, wordDict: List[str]) -> bool:
    ws=set(wordDict); n=len(s); dp=[False]*(n+1); dp[0]=True
    for i in range(1,n+1):
        for j in range(i):
            if dp[j] and s[j:i] in ws: dp[i]=True; break
    return dp[n]
print("P07 wordBreak('leetcode',['leet','code']):",wordBreak("leetcode",["leet","code"]))  # True

# P08. Regular Expression Matching [Hard][LC 10]
def isMatch(s: str, p: str) -> bool:
    m,n=len(s),len(p); dp=[[False]*(n+1) for _ in range(m+1)]; dp[0][0]=True
    for j in range(1,n+1):
        if p[j-1]=='*' and j>=2: dp[0][j]=dp[0][j-2]
    for i in range(1,m+1):
        for j in range(1,n+1):
            if p[j-1]=='*':
                dp[i][j]=dp[i][j-2]
                if p[j-2]=='.' or p[j-2]==s[i-1]: dp[i][j]|=dp[i-1][j]
            elif p[j-1]=='.' or p[j-1]==s[i-1]: dp[i][j]=dp[i-1][j-1]
    return dp[m][n]
print("P08 isMatch('aa','a*'):",isMatch("aa","a*"))  # True

# P09. Wildcard Matching [Hard][LC 44]
def isMatchWild(s: str, p: str) -> bool:
    m,n=len(s),len(p); dp=[[False]*(n+1) for _ in range(m+1)]; dp[0][0]=True
    for j in range(1,n+1): dp[0][j]=dp[0][j-1] and p[j-1]=='*'
    for i in range(1,m+1):
        for j in range(1,n+1):
            if p[j-1]=='*': dp[i][j]=dp[i-1][j] or dp[i][j-1]
            elif p[j-1]=='?' or p[j-1]==s[i-1]: dp[i][j]=dp[i-1][j-1]
    return dp[m][n]
print("P09 wildcard('adceb','*a*b'):",isMatchWild("adceb","*a*b"))  # True

# P10. Shortest Common Supersequence [Hard][LC 1092]
def shortestCommonSupersequence(str1: str, str2: str) -> str:
    m,n=len(str1),len(str2); dp=[[0]*(n+1) for _ in range(m+1)]
    for i in range(1,m+1):
        for j in range(1,n+1):
            dp[i][j]=dp[i-1][j-1]+1 if str1[i-1]==str2[j-1] else max(dp[i-1][j],dp[i][j-1])
    res=[]; i,j=m,n
    while i>0 and j>0:
        if str1[i-1]==str2[j-1]: res.append(str1[i-1]); i-=1; j-=1
        elif dp[i-1][j]>dp[i][j-1]: res.append(str1[i-1]); i-=1
        else: res.append(str2[j-1]); j-=1
    while i>0: res.append(str1[i-1]); i-=1
    while j>0: res.append(str2[j-1]); j-=1
    return "".join(reversed(res))
print("P10 SCS('abac','cab'):",shortestCommonSupersequence("abac","cab"))

# P11. Minimum ASCII Delete Sum [Medium][LC 712]
def minimumDeleteSum(s1: str, s2: str) -> int:
    m,n=len(s1),len(s2); dp=[[0]*(n+1) for _ in range(m+1)]
    for i in range(1,m+1): dp[i][0]=dp[i-1][0]+ord(s1[i-1])
    for j in range(1,n+1): dp[0][j]=dp[0][j-1]+ord(s2[j-1])
    for i in range(1,m+1):
        for j in range(1,n+1):
            dp[i][j]=dp[i-1][j-1] if s1[i-1]==s2[j-1] else min(dp[i-1][j]+ord(s1[i-1]),dp[i][j-1]+ord(s2[j-1]))
    return dp[m][n]
print("P11 minDeleteSum('sea','eat'):",minimumDeleteSum("sea","eat"))  # 231

# P12. Count Different Palindromic Subsequences [Hard][LC 730]
def countPalindromicSubsequences(s: str) -> int:
    MOD=10**9+7; n=len(s); dp=[[0]*n for _ in range(n)]
    for i in range(n): dp[i][i]=1
    for l in range(2,n+1):
        for i in range(n-l+1):
            j=i+l-1
            if s[i]!=s[j]: dp[i][j]=dp[i+1][j]+dp[i][j-1]-dp[i+1][j-1]
            else:
                lo,hi=i+1,j-1
                while lo<=hi and s[lo]!=s[i]: lo+=1
                while lo<=hi and s[hi]!=s[j]: hi-=1
                if lo>hi: dp[i][j]=dp[i+1][j-1]*2+2
                elif lo==hi: dp[i][j]=dp[i+1][j-1]*2+1
                else: dp[i][j]=dp[i+1][j-1]*2-dp[lo+1][hi-1]
            dp[i][j]%=MOD
    return dp[0][n-1]
print("P12 countPalSubseq('bccb'):",countPalindromicSubsequences("bccb"))  # 6

"""
COMPLEXITY SUMMARY:
Edit Distance              O(m×n) O(n)   1D space optimization
LCS                        O(m×n) O(m×n) 2D DP
Longest Palindrome Subseq  O(n²)  O(n²)  diagonal DP
Palindrome Partition II    O(n²)  O(n²)  precompute isPalin + min cuts
Distinct Subsequences      O(m×n) O(m×n) choose/skip DP
Interleaving String        O(m×n) O(m×n) 2D boolean DP
Word Break                 O(n²k) O(n)   1D DP + set lookup
Regex Matching             O(m×n) O(m×n) star = zero or more
Wildcard Matching          O(m×n) O(m×n) * = any sequence
Shortest Common Superseq   O(m×n) O(m×n) LCS + reconstruction
Min ASCII Delete Sum       O(m×n) O(m×n) cost-weighted LCS
Count Palindromic Subseqs  O(n²)  O(n²)  interval DP
"""
