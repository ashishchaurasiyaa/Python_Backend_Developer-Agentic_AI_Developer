nums = [2,7,11,15]
target = 9
for i in range(len(nums)):
    for j in range(i+1 , len(nums)):
        if nums[i] + nums[j] == target:
            print([i, j])
            break

num = [2,7,11,15]
seen = {}
target = 9
for i, a in enumerate(num):
    check_nums = target - a
    if check_nums in seen:
        print([seen[check_nums] ,i])
    seen[a] = i