class Account:
    def __init__(self, initial_deposit: float) -> None:
        """
        Initializes an Account object with an initial deposit.

        Args:
            initial_deposit (float): The initial deposit amount.
        """
        self.balance = initial_deposit
        self.holdings = {}
        self.total_deposits = initial_deposit

    def deposit(self, amount: float) -> None:
        """
        Deposits funds into the account.

        Args:
            amount (float): The amount to deposit.
        """
        self.balance += amount
        self.total_deposits += amount

    def withdraw(self, amount: float) -> None:
        """
        Withdraws funds from the account, raising a ValueError if the withdrawal amount exceeds the balance.

        Args:
            amount (float): The amount to withdraw.
        """
        if amount > self.balance:
            raise ValueError("Insufficient balance")
        self.balance -= amount

    def buy(self, symbol: str, quantity: int) -> None:
        """
        Buys shares of a specified stock, raising a ValueError if the account balance is insufficient or if the symbol is unknown.

        Args:
            symbol (str): The stock symbol.
            quantity (int): The number of shares to buy.
        """
        share_price = get_share_price(symbol)
        total_cost = share_price * quantity
        if total_cost > self.balance:
            raise ValueError("Insufficient balance")
        if symbol in self.holdings:
            self.holdings[symbol] += quantity
        else:
            self.holdings[symbol] = quantity
        self.balance -= total_cost

    def sell(self, symbol: str, quantity: int) -> None:
        """
        Sells shares of a specified stock, raising a ValueError if the account does not hold sufficient shares or if the symbol is unknown.

        Args:
            symbol (str): The stock symbol.
            quantity (int): The number of shares to sell.
        """
        if symbol not in self.holdings:
            raise ValueError("Unknown symbol")
        if quantity > self.holdings[symbol]:
            raise ValueError("Insufficient shares")
        share_price = get_share_price(symbol)
        total_revenue = share_price * quantity
        self.holdings[symbol] -= quantity
        if self.holdings[symbol] == 0:
            del self.holdings[symbol]
        self.balance += total_revenue

    def report_holdings(self) -> dict[str, int]:
        """
        Returns a dictionary of the account's current holdings, where each key is a stock symbol and each value is the quantity held.

        Returns:
            dict[str, int]: The account's holdings.
        """
        return self.holdings.copy()

    def compute_portfolio_value(self) -> float:
        """
        Computes the total value of the account's holdings, using the current share prices.

        Returns:
            float: The total portfolio value.
        """
        portfolio_value = self.balance
        for symbol, quantity in self.holdings.items():
            portfolio_value += get_share_price(symbol) * quantity
        return portfolio_value

    def compute_profit_loss(self) -> float:
        """
        Computes the profit/loss of the account, compared to the total deposits made.

        Returns:
            float: The profit/loss.
        """
        return self.compute_portfolio_value() - self.total_deposits


def get_share_price(symbol: str) -> float:
    """
    Returns the fixed share price for a given symbol, raising a ValueError if the symbol is unknown.

    Args:
        symbol (str): The stock symbol.

    Returns:
        float: The share price.
    """
    share_prices = {
        "AAPL": 150.0,
        "TSLA": 800.0,
        "GOOGL": 2500.0
    }
    if symbol not in share_prices:
        raise ValueError("Unknown symbol")
    return share_prices[symbol]
