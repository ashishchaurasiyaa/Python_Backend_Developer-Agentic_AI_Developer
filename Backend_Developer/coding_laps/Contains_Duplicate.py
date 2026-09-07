nums = [1,2,3]
print(len(nums) != len(set(nums)))

nums = [1,1,1,3,3,4,3,2,4,2]
nums.sort()
for i in range(len(nums)):
    if nums[i] == nums[i-1]:
        print(True)
        break


nums = [1,2, 3]
seen = {}
for num in nums:
    if num in seen:
        print(True)
    seen[num] = True
else:
    print(False)
