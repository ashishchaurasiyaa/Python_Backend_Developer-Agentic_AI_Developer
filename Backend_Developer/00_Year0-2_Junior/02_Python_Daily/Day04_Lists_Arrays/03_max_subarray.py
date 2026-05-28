# Maximum sum subarray of size K

# nums = [2, 1, 5, 1, 3, 2]
# k = 3
# max_sum = 0
#
# for i in range(len(nums) - k + 1):
#     window_sum = 0
#     for j in range(i, i + k):
#         window_sum += nums[j]
#     max_sum = max(max_sum, window_sum)
#
# print(max_sum)

nums = [1, 12, -5, -6, 50, 3]
k = 4

# Pehli window ka sum
window_sum = sum(nums[:k])
max_sum = window_sum

for i in range(k, len(nums)):
    window_sum += nums[i]        # naya element add
    window_sum -= nums[i - k]    # pehla element hatao
    max_sum = max(max_sum, window_sum)

print(max_sum)

# 643. Maximum Average Subarray I

nums = [1, 12, -5, -6, 50, 3]
k = 4

# Pehli window ka sum
window_sum = sum(nums[:k])
max_sum = window_sum

for i in range(k, len(nums)):
    window_sum += nums[i]        # naya element add
    window_sum -= nums[i - k]    # pehla element hatao
    max_sum = max(max_sum, window_sum)

print(max_sum/k)