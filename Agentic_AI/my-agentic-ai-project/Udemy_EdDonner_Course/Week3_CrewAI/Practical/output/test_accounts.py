from accounts import Account, get_share_price
import unittest

class TestAccount(unittest.TestCase):

    def test_init(self):
        account = Account(100000.0)
        self.assertEqual(account.balance, 100000.0)
        self.assertEqual(account.total_deposits, 100000.0)
        self.assertEqual(account.holdings, {})

    def test_deposit(self):
        account = Account(100000.0)
        account.deposit(50000.0)
        self.assertEqual(account.balance, 150000.0)
        self.assertEqual(account.total_deposits, 150000.0)

    def test_withdraw(self):
        account = Account(100000.0)
        account.withdraw(50000.0)
        self.assertEqual(account.balance, 50000.0)
        with self.assertRaises(ValueError):
            account.withdraw(60000.0)

    def test_buy(self):
        account = Account(100000.0)
        account.buy("AAPL", 10)
        self.assertEqual(account.balance, 100000.0 - 1500.0)
        self.assertEqual(account.holdings, {"AAPL": 10})
        with self.assertRaises(ValueError):
            account.buy("AAPL", 1000)

    def test_sell(self):
        account = Account(100000.0)
        account.buy("AAPL", 10)
        account.sell("AAPL", 5)
        self.assertEqual(account.balance, 100000.0 - 1500.0 + 750.0)
        self.assertEqual(account.holdings, {"AAPL": 5})
        with self.assertRaises(ValueError):
            account.sell("AAPL", 10)
        with self.assertRaises(ValueError):
            account.sell("TSLA", 5)

    def test_report_holdings(self):
        account = Account(100000.0)
        account.buy("AAPL", 10)
        account.buy("TSLA", 5)
        self.assertEqual(account.report_holdings(), {"AAPL": 10, "TSLA": 5})

    def test_compute_portfolio_value(self):
        account = Account(100000.0)
        account.buy("AAPL", 10)
        account.buy("TSLA", 5)
        self.assertEqual(account.compute_portfolio_value(), 100000.0 - 1500.0 - 4000.0 + 1500.0 + 4000.0)

    def test_compute_profit_loss(self):
        account = Account(100000.0)
        account.buy("AAPL", 10)
        account.buy("TSLA", 5)
        self.assertEqual(account.compute_profit_loss(), 0.0)

if __name__ == '__main__':
    unittest.main()
