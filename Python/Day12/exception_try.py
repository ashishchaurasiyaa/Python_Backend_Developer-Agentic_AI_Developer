chai_menu = {"masla": 30, "ginger":40}

try:
    chai_menu["elachi"]
except KeyError:
    print(f"The Key that you are tying to access does not exits")
print("Hello Chai code")
