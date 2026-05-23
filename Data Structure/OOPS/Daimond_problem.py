def print_diamond(n):
    # Upper half of the diamond
    for i in range(n):
        # Print leading spaces
        for j in range(n - i - 1):
            print(" ", end="")
        # Print stars
        for k in range(2 * i + 1):
            print("*", end="")
        # Move to the next line
        print()

    # Lower half of the diamond
    for i in range(n - 2, -1, -1):
        # Print leading spaces
        for j in range(n - i - 1):
            print(" ", end="")
        # Print stars
        for k in range(2 * i + 1):
            print("*", end="")
        # Move to the next line
        print()

# Example usage:
n = int(input("Enter the value of n: "))
print_diamond(n)
