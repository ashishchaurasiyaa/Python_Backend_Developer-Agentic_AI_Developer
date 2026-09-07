"""
Given an array nums containing n distinct numbers in the range [0, n],
return the only number in the range that is missing from the array.
"""

nums = [9,6,4,2,3,5,7,0,1]
n = len(nums)
for i in range(0, n+1):
    if i not in nums:
        print(i)


def missing_num(nums):
    n = len(nums)
    for num in n:
        if num not in nums:
            return num
nums = [9,6,4,2,3,5,7,0,1]
print(missing_num(nums))