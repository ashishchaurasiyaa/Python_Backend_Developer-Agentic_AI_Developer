"""20 — Matrix / 2D Grid — Problems | 12 problems | Easy→Hard"""
from typing import List
from collections import deque

DIRS4 = [(0,1),(0,-1),(1,0),(-1,0)]

def valid(r,c,rows,cols): return 0<=r<rows and 0<=c<cols

# P01. Rotate Image [Medium][LC 48]
def rotate(matrix: List[List[int]]) -> None:
    n = len(matrix)
    for i in range(n):
        for j in range(i+1,n): matrix[i][j],matrix[j][i]=matrix[j][i],matrix[i][j]
    for row in matrix: row.reverse()
m=[[1,2,3],[4,5,6],[7,8,9]]; rotate(m); print("P01:",m)

# P02. Spiral Matrix [Medium][LC 54]
def spiralOrder(matrix: List[List[int]]) -> List[int]:
    res=[]; top,bot,left,right=0,len(matrix)-1,0,len(matrix[0])-1
    while top<=bot and left<=right:
        for c in range(left,right+1): res.append(matrix[top][c]); top+=1
        for r in range(top,bot+1): res.append(matrix[r][right]); right-=1
        if top<=bot:
            for c in range(right,left-1,-1): res.append(matrix[bot][c]); bot-=1
        if left<=right:
            for r in range(bot,top-1,-1): res.append(matrix[r][left]); left+=1
    return res
print("P02:",spiralOrder([[1,2,3],[4,5,6],[7,8,9]]))

# P03. Set Matrix Zeroes [Medium][LC 73]
def setZeroes(matrix: List[List[int]]) -> None:
    rows,cols=len(matrix),len(matrix[0])
    fr=any(matrix[0][c]==0 for c in range(cols))
    fc=any(matrix[r][0]==0 for r in range(rows))
    for r in range(1,rows):
        for c in range(1,cols):
            if matrix[r][c]==0: matrix[r][0]=matrix[0][c]=0
    for r in range(1,rows):
        for c in range(1,cols):
            if matrix[r][0]==0 or matrix[0][c]==0: matrix[r][c]=0
    if fr:
        for c in range(cols): matrix[0][c]=0
    if fc:
        for r in range(rows): matrix[r][0]=0
m=[[1,1,1],[1,0,1],[1,1,1]]; setZeroes(m); print("P03:",m)

# P04. Number of Islands [Medium][LC 200]
def numIslands(grid: List[List[str]]) -> int:
    rows,cols,count=len(grid),len(grid[0]),0
    def dfs(r,c):
        if not valid(r,c,rows,cols) or grid[r][c]!='1': return
        grid[r][c]='0'
        for dr,dc in DIRS4: dfs(r+dr,c+dc)
    for r in range(rows):
        for c in range(cols):
            if grid[r][c]=='1': dfs(r,c); count+=1
    return count
print("P04:",numIslands([['1','1','0','0'],['1','1','0','0'],['0','0','1','0'],['0','0','0','1']]))

# P05. Max Area of Island [Medium][LC 695]
def maxAreaOfIsland(grid: List[List[int]]) -> int:
    rows,cols=len(grid),len(grid[0])
    def dfs(r,c):
        if not valid(r,c,rows,cols) or grid[r][c]==0: return 0
        grid[r][c]=0
        return 1+sum(dfs(r+dr,c+dc) for dr,dc in DIRS4)
    return max((dfs(r,c) for r in range(rows) for c in range(cols) if grid[r][c]),default=0)
print("P05:",maxAreaOfIsland([[0,0,1,0,0,0,0,1,0,0,0,0,0],[0,0,0,0,0,0,0,1,1,1,0,0,0],[0,1,1,0,1,0,0,0,0,0,0,0,0]]))

# P06. Surrounded Regions [Medium][LC 130]
def solve(board: List[List[str]]) -> None:
    if not board: return
    rows,cols=len(board),len(board[0])
    def dfs(r,c):
        if not valid(r,c,rows,cols) or board[r][c]!='O': return
        board[r][c]='S'
        for dr,dc in DIRS4: dfs(r+dr,c+dc)
    for r in range(rows):
        for c in range(cols):
            if (r in(0,rows-1) or c in(0,cols-1)) and board[r][c]=='O': dfs(r,c)
    for r in range(rows):
        for c in range(cols):
            if board[r][c]=='O': board[r][c]='X'
            elif board[r][c]=='S': board[r][c]='O'
b=[['X','X','X','X'],['X','O','O','X'],['X','X','O','X'],['X','O','X','X']]
solve(b); print("P06:",b)

# P07. Rotting Oranges [Medium][LC 994]
def orangesRotting(grid: List[List[int]]) -> int:
    rows,cols=len(grid),len(grid[0])
    q=deque(); fresh=0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c]==2: q.append((r,c,0))
            elif grid[r][c]==1: fresh+=1
    time=0
    while q:
        r,c,t=q.popleft(); time=max(time,t)
        for dr,dc in DIRS4:
            nr,nc=r+dr,c+dc
            if valid(nr,nc,rows,cols) and grid[nr][nc]==1:
                grid[nr][nc]=2; fresh-=1; q.append((nr,nc,t+1))
    return time if fresh==0 else -1
print("P07:",orangesRotting([[2,1,1],[1,1,0],[0,1,1]]))

# P08. 01 Matrix [Medium][LC 542]
def updateMatrix(mat: List[List[int]]) -> List[List[int]]:
    rows,cols=len(mat),len(mat[0])
    dist=[[float('inf')]*cols for _ in range(rows)]
    q=deque()
    for r in range(rows):
        for c in range(cols):
            if mat[r][c]==0: dist[r][c]=0; q.append((r,c))
    while q:
        r,c=q.popleft()
        for dr,dc in DIRS4:
            nr,nc=r+dr,c+dc
            if valid(nr,nc,rows,cols) and dist[nr][nc]>dist[r][c]+1:
                dist[nr][nc]=dist[r][c]+1; q.append((nr,nc))
    return dist
print("P08:",updateMatrix([[0,0,0],[0,1,0],[1,1,1]]))

# P09. Search a 2D Matrix [Medium][LC 74]
def searchMatrix(matrix: List[List[int]], target: int) -> bool:
    rows,cols=len(matrix),len(matrix[0]); lo,hi=0,rows*cols-1
    while lo<=hi:
        mid=(lo+hi)//2; val=matrix[mid//cols][mid%cols]
        if val==target: return True
        elif val<target: lo=mid+1
        else: hi=mid-1
    return False
print("P09:",searchMatrix([[1,3,5,7],[10,11,16,20],[23,30,34,60]],3))

# P10. Word Search [Medium][LC 79]
def exist(board: List[List[str]], word: str) -> bool:
    rows,cols=len(board),len(board[0])
    def dfs(r,c,idx):
        if idx==len(word): return True
        if not valid(r,c,rows,cols) or board[r][c]!=word[idx]: return False
        tmp,board[r][c]=board[r][c],'#'
        found=any(dfs(r+dr,c+dc,idx+1) for dr,dc in DIRS4)
        board[r][c]=tmp
        return found
    return any(dfs(r,c,0) for r in range(rows) for c in range(cols))
print("P10:",exist([['A','B','C','E'],['S','F','C','S'],['A','D','E','E']],'ABCCED'))

# P11. Pacific Atlantic Water Flow [Medium][LC 417]
def pacificAtlantic(heights: List[List[int]]) -> List[List[int]]:
    rows,cols=len(heights),len(heights[0])
    def bfs(starts):
        visited=set(starts); q=deque(starts)
        while q:
            r,c=q.popleft()
            for dr,dc in DIRS4:
                nr,nc=r+dr,c+dc
                if valid(nr,nc,rows,cols) and (nr,nc) not in visited and heights[nr][nc]>=heights[r][c]:
                    visited.add((nr,nc)); q.append((nr,nc))
        return visited
    pac=bfs([(0,c) for c in range(cols)]+[(r,0) for r in range(rows)])
    atl=bfs([(rows-1,c) for c in range(cols)]+[(r,cols-1) for r in range(rows)])
    return [[r,c] for r in range(rows) for c in range(cols) if (r,c) in pac and (r,c) in atl]
print("P11 count:",len(pacificAtlantic([[1,2,2,3,5],[3,2,3,4,4],[2,4,5,3,1],[6,7,1,4,5],[5,1,1,2,4]])))

# P12. Minimum Path Sum [Medium][LC 64]
def minPathSum(grid: List[List[int]]) -> int:
    rows,cols=len(grid),len(grid[0])
    for r in range(rows):
        for c in range(cols):
            if r==0 and c==0: continue
            elif r==0: grid[r][c]+=grid[r][c-1]
            elif c==0: grid[r][c]+=grid[r-1][c]
            else: grid[r][c]+=min(grid[r-1][c],grid[r][c-1])
    return grid[rows-1][cols-1]
print("P12:",minPathSum([[1,3,1],[1,5,1],[4,2,1]]))

"""
COMPLEXITY SUMMARY:
Rotate Image           O(n²)   O(1)   transpose + reverse rows
Spiral Matrix          O(m×n)  O(1)   4-boundary shrink
Set Matrix Zeroes      O(m×n)  O(1)   first row/col as markers
Number of Islands      O(m×n)  O(m×n) DFS flood fill
Max Area of Island     O(m×n)  O(m×n) DFS with count
Surrounded Regions     O(m×n)  O(m×n) DFS from border O's
Rotting Oranges        O(m×n)  O(m×n) multi-source BFS
01 Matrix              O(m×n)  O(m×n) multi-source BFS from 0s
Search 2D Matrix       O(log mn) O(1) binary search flat
Word Search            O(m×n×4^L) O(L) DFS backtracking
Pacific Atlantic        O(m×n)  O(m×n) BFS from both oceans
Min Path Sum           O(m×n)  O(1)   DP in-place
"""
