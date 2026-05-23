class InvalidChaiError(Exception): pass

def bill(flavor, cups):
    menu = {"masala": 20, "ginger": 40}

    try:
        if flavor not in menu:
            raise InvalidChaiError("That chai is not available")
        if not isinstance(cups, int):
            raise TypeError("Number of cups must be an integer")
        total = cups * menu[flavor]
        print(f"Your bill for {cups} cups of {flavor} chai: ₹{total}")
    except Exception as e:
        print("Error:", e)
    finally:
        print("Thank you for visiting ChaiCode!")

bill("mint", 2)
bill("masala", "three")
bill("ginger", 3)