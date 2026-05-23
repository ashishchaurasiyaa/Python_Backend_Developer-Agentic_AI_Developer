arr = [1,2,3,4,5]
#time complexity O(1)
# Search x in arr -> 0(n)
# Insert   arr.append()  → O(1) amortized
# Insert   arr.insert(i) → O(n)
# Delete   arr.pop()     → O(1)
# Delete   arr.pop(i)    → O(n)


arr = [3, 1, 4, 5, 9, 2, 6]

print(arr[0])
print(arr[-1])
print(arr[1:3])
print(arr[::-1])
print(len(arr))
print(min(arr))
print(max(arr))
print(sum(arr))

# 2D Arrays:

matrix =[
    [1,2,3],
    [4,5,6],
    [7,8,9]
]

print(matrix[1][2])
for row in matrix:
    for val in row:
        print(val, end=" ")

rows, cols = 3, 4
grid = [[0] * cols for _ in range(rows)]
print(grid)

# Two pointer = do variables jo array mein alag positions track karte hain

# Types:
# 1: Opposite ends -> left = 0, right = n - 1 (inward)
# 2: Same direction -> slow=0, fast=0 (outward)
# 3: Two arrays     -> i=0, j=0

# Opposite ends:

# Sorted array mein pair find karo jiska sum = target

def two_sum_sorted(arr, target):
    left =0
    right = len(arr) - 1

    while left < right:
        curr = arr[left] + arr[right]

        if curr == target:
            return [left, right]
        elif curr < target:
            left += 1
        else:
            right -= 1

    return []
arr = [1, 2, 3, 4, 6, 8, 11]
print(two_sum_sorted(arr, 10))



# Same Direction(Fast/Slow):

def remove_duplicates(arr):
    if not arr:
        return 0

    slow = 0
    for fast in range(1, len(arr)):
        if arr[fast] != arr[slow]:
            slow += 1
            arr[slow] = arr[fast]

    return slow + 1
arr = [1, 1, 2, 2, 3, 4, 4, 5]
n = remove_duplicates(arr)
print(arr[:n])


# Hour 3 — Sliding Window Pattern
def max_sum_subarray(arr, k):
    window_sum = sum(arr[:k])
    max_sum = window_sum

    for i in range(k, len(arr)):
        window_sum += arr[i]
        window_sum -= arr[i-k]
        max_sum = max(max_sum, window_sum)
    return max_sum

arr = [1, 2, 3, 4, 5, 6, 7, 8, 9]
print(max_sum_subarray(arr, 3))