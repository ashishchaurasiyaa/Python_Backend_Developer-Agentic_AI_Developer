arr = [3, 1, 4, 1, 5, 9, 2, 6]
freq = {}
for num in arr:
    freq[num] = freq.get(num, 0) + 1
print(freq)


