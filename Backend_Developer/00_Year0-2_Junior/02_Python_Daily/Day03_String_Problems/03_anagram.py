word1 = input("Enter first word: ").lower()
word2 = input("Enter second word: ").lower()

if len(word1) != len(word2):
    print("Not Anagram!")
else:
    freq = {}
    for char in word1:
        freq[char] = freq.get(char, 0) + 1

    for char in word2:
        if char in freq and freq[char] > 0:
            freq[char] -= 1
        else:
            print("Not Anagram!")
            break
    else:
        print("Anagram!")