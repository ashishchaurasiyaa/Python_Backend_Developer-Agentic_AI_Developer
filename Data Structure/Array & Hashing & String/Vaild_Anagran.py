def isAnagram(a, b):
    if len(a) != len(b):
        return False

    countA, countB = {}, {}
    for i in range(len(a)):
        countA[a[i]] = countA.get(a[i], 0) + 1
        countB[b[i]] = countB.get(b[i], 0) + 1

    return countA == countB
s = "rat"
t = "car"
print(isAnagram(s, t))