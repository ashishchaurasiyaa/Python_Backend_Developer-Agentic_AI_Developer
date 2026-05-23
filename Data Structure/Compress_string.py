# Problem: Compress a string using run-length encoding.


def compress_string(s):
    count = 1
    compressed = ""
    for i in range(len(s)-1):
        if s[i] == s[i+1]:
            count += 1
        else:
            compressed += s[i] + str(count)
            count = 1
    compressed += s[i] + str(count)
    return compressed
s = "aaaaabbbbbccc"
print(compress_string(s))