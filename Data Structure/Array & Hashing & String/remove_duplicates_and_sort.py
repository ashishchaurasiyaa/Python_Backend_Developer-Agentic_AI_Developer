def remove_duplicates_and_sort(arr):
    # Step 1: Remove Duplicates using a Dictionary (HashMap)
    unique_dict = {}
    for num in arr:
        unique_dict[num] = True  # Ensures uniqueness

    unique_list = list(unique_dict.keys())  # Convert back to list

    # Step 2: Implement Quick Sort
    def quick_sort(arr, low, high):
        if low < high:
            pi = partition(arr, low, high)
            quick_sort(arr, low, pi - 1)
            quick_sort(arr, pi + 1, high)

    def partition(arr, low, high):
        pivot = arr[high]
        i = low - 1
        for j in range(low, high):
            if arr[j] < pivot:
                i += 1
                arr[i], arr[j] = arr[j], arr[i]
        arr[i + 1], arr[high] = arr[high], arr[i + 1]
        return i + 1

    quick_sort(unique_list, 0, len(unique_list) - 1)

    return unique_list  # Sorted and Unique List

# Example Usage
arr = [4, 2, 9, 1, 7, 2, 5, 6, 1, 2, 8, 3, 9]
print(remove_duplicates_and_sort(arr))


"""
I removed duplicates using a dictionary, which ensures uniqueness in O(N) time.
Then, I implemented Quick Sort to efficiently sort the unique elements in O(U log U) time.
This gives an optimal overall complexity of O(N + U log U), making it well-suited for handling large datasets efficiently."
"""