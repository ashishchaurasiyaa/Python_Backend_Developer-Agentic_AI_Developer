def kadane(nums):
    current = nums[0]
    max_sum = nums[0]
    for num in nums[1:]:
        current = max(num, current + num)
        max_sum = max(max_sum, current)
    return max_sum

nums = [-2, 1, -3, 4, -1, 2, 1, -5, 4]
print(kadane(nums))