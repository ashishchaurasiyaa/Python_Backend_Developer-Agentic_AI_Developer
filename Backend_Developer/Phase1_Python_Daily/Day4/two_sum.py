def two_sum(nums, target):
    nums.sort()
    left = 0
    right = len(nums) - 1

    while left < right:
        sum = nums[left] + nums[right]
        if sum == target:
            return [left, right]
        elif sum < target:
            left += 1
        else:
            right -= 1

    return []

nums = [2, 7, 11, 15, 1, 3, 4,9]
target = 10
print(two_sum(nums, target))
print(two_sum(nums, 6))
print(two_sum(nums, 10))
print(two_sum(nums, 20))

# Two pointer sirf **sorted array** pe kaam karta hai!

# Hash map approch

def two_sum_hash_map(nums, target):
    nums_dict = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in nums_dict:
            return [nums_dict[complement], i]
        nums_dict[num] = i
    return []
nums = [2, 7, 11, 15, 1, 3, 4,9]
print(two_sum_hash_map(nums, 10))   # [0, ?]
print(two_sum_hash_map(nums, 9))    # [0, 1]
print(two_sum_hash_map(nums, 100))  # []