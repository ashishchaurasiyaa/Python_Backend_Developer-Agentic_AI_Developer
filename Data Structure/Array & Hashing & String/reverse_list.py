def reverse_list(lst):
    left, right = 0 , len(lst)-1
    while left <= right:
        lst[left], lst[right] = lst[right], lst[left]
        left += 1
        right -= 1
    return lst

numbers = [1,2,3,4,5]
print(reverse_list(numbers))
