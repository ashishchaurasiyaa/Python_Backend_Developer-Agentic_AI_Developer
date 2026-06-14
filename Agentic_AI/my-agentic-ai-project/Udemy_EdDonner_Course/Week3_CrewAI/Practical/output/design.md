# accounts.py Module Design Document
## Overview
The `accounts.py` module provides a simple `Account` class for a trading simulation platform. It allows users to create an account with an initial deposit, deposit and withdraw funds, buy and sell shares, report holdings, and compute the total portfolio value and profit/loss.

## Account Class
### `class Account`
The `Account` class represents a user's trading account.

#### `def __init__(self, initial_deposit: float) -> None`
Initializes an `Account` object with an initial deposit.

#### `def deposit(self, amount: float) -> None`
Deposits funds into the account.

#### `def withdraw(self, amount: float) -> None`
Withdraws funds from the account, raising a `ValueError` if the withdrawal amount exceeds the balance.

#### `def buy(self, symbol: str, quantity: int) -> None`
Buys shares of a specified stock, raising a `ValueError` if the account balance is insufficient or if the symbol is unknown.

#### `def sell(self, symbol: str, quantity: int) -> None`
Sells shares of a specified stock, raising a `ValueError` if the account does not hold sufficient shares or if the symbol is unknown.

#### `def report_holdings(self) -> dict[str, int]`
Returns a dictionary of the account's current holdings, where each key is a stock symbol and each value is the quantity held.

#### `def compute_portfolio_value(self) -> float`
Computes the total value of the account's holdings, using the current share prices.

#### `def compute_profit_loss(self) -> float`
Computes the profit/loss of the account, compared to the total deposits made.

## Module-Level Function
### `def get_share_price(symbol: str) -> float`
Returns the fixed share price for a given symbol, raising a `ValueError` if the symbol is unknown.

## Edge Cases and Exceptions
*   Attempting to withdraw more funds than the account balance raises a `ValueError`.
*   Attempting to buy shares without sufficient account balance raises a `ValueError`.
*   Attempting to sell shares without holding sufficient shares raises a `ValueError`.
*   Passing an unknown symbol to `buy`, `sell`, or `get_share_price` raises a `ValueError`.

## Implementation Notes
The `Account` class will use a dictionary to store the account's holdings, where each key is a stock symbol and each value is the quantity held. The `get_share_price` function will use a dictionary to map symbols to fixed share prices.

Example usage:
```python
account = Account(1000.0)
account.deposit(500.0)
account.buy("AAPL", 5)
account.sell("AAPL", 2)
print(account.report_holdings())
print(account.compute_portfolio_value())
print(account.compute_profit_loss())
```
