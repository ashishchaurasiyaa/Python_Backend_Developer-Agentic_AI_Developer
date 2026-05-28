def build_prefix_sum(arr):
    prefix= [0] * (len(arr) + 1)
    for i in range(1, len(arr)):
        prefix[i+1] = prefix[i] + arr[i]
    return prefix

def range_sum(prefix, l,r):
    return prefix[r+1] - prefix[l]

arr = [1, 2, 3, 4, 5]
prefix = build_prefix_sum(arr)
print(range_sum(prefix, 1, 3))
print(range_sum(prefix, 0, 4))