"""
You are given an array prices where prices[i] is the price of a given stock on the ith day.

You want to maximize your profit by choosing a single day to buy one stock and choosing a different day in the future to sell that stock.

Return the maximum profit you can achieve from this transaction. If you cannot achieve any profit, return 0.
"""

prices = [7,1,5,3,6,4]

min_prices = prices[0]
max_profit = 0
for price in prices:
    if price < min_prices:
        min_prices = price
    else:
        max_profit = max(max_profit, price - min_prices)
print(max_profit)


prices = [7,1,5,3,6,4]
min_prices = prices[0]
max_profit = 0
for price in prices:
    if price < min_prices:
        min_prices = price
    else:
        profit = price - min_prices
        if profit > max_profit:
            max_profit = profit
print(max_profit)