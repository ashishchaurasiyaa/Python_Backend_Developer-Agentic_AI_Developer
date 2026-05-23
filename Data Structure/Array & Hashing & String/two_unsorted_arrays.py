def merge_and_sort_unique(arr1, arr2):
    # Step 1: Merge both arrays
    merged = arr1 + arr2

    # Step 2: Remove duplicates using a dictionary (hashing)
    unique_dict = {}  # Using dictionary keys to ensure uniqueness
    for num in merged:
        unique_dict[num] = True

    unique_list = list(unique_dict.keys())  # Get unique elements

    # Step 3: Implement Bubble Sort (since we can't use built-in sort)
    n = len(unique_list)
    for i in range(n):
        for j in range(0, n - i - 1):
            if unique_list[j] > unique_list[j + 1]:
                unique_list[j], unique_list[j + 1] = unique_list[j + 1], unique_list[j]

    return unique_list


# Example Usage
arr1 = [4, 2, 9, 1, 7, 2]
arr2 = [5, 6, 1, 2, 8, 3, 9]

print(merge_and_sort_unique(arr1, arr2))

"""
We merge the two arrays in O(N + M), remove duplicates using a dictionary in O(N + M),
and sort the unique elements using Bubble Sort in O(U²). The final time complexity is O(N + M + U²).
This approach ensures correctness while keeping it simple without using built-in functions.
"""
