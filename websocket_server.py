import asyncio
import websockets
import json
from collections import defaultdict

class DataIngestion:
    """
    Handles stock data ingestion and publishing to a message broker.
    """
    def __init__(self, message_broker):
        self.message_broker = message_broker  # Simulated message broker

    async def ingest_stock_data(self, stock_data):
        """
        Ingests stock data and publishes it to the message broker.
        """
        await self.message_broker.publish(stock_data)

class MessageBroker:
    """
    Simulated message broker using asyncio queues.
    """
    def __init__(self):
        self.topics = defaultdict(asyncio.Queue)

    async def publish(self, stock_data):
        """
        Publishes stock data to the corresponding topic queue.
        """
        stock_symbol = stock_data["symbol"]
        await self.topics[stock_symbol].put(stock_data)

    async def subscribe(self, stock_symbol):
        """
        Subscribes to a topic queue for a specific stock symbol.
        """
        return self.topics[stock_symbol]

class SubscriptionManager:
    """
    Manages client subscriptions.
    """
    def __init__(self):
        self.subscriptions = defaultdict(set)

    def subscribe(self, client_id, stock_symbol):
        """
        Adds a client to the subscription list for a stock symbol.
        """
        self.subscriptions[stock_symbol].add(client_id)

    def unsubscribe(self, client_id, stock_symbol):
        """
        Removes a client from the subscription list for a stock symbol.
        """
        if client_id in self.subscriptions[stock_symbol]:
            self.subscriptions[stock_symbol].remove(client_id)

    def get_subscribed_clients(self, stock_symbol):
        """
        Retrieves the list of clients subscribed to a stock symbol.
        """
        return self.subscriptions[stock_symbol]

class WebSocketHandler:
    """
    Handles WebSocket connections and real-time delivery of stock data.
    """
    def __init__(self, subscription_manager, message_broker):
        self.subscription_manager = subscription_manager
        self.message_broker = message_broker
        self.clients = {}

    async def handle_connection(self, websocket, path):
        """
        Handles a WebSocket connection for a client.
        """
        client_id = id(websocket)
        self.clients[client_id] = websocket
        try:
            async for message in websocket:
                data = json.loads(message)
                if data["action"] == "subscribe":
                    self.subscription_manager.subscribe(client_id, data["stock"])
                elif data["action"] == "unsubscribe":
                    self.subscription_manager.unsubscribe(client_id, data["stock"])
        finally:
            del self.clients[client_id]

    async def push_updates(self):
        """
        Sends stock updates to subscribed clients.
        """
        while True:
            for stock_symbol, clients in self.subscription_manager.subscriptions.items():
                queue = await self.message_broker.subscribe(stock_symbol)
                while not queue.empty():
                    stock_data = await queue.get()
                    for client_id in clients:
                        if client_id in self.clients:
                            websocket = self.clients[client_id]
                            await websocket.send(json.dumps(stock_data))

async def main():
    # Simulated components
    message_broker = MessageBroker()
    subscription_manager = SubscriptionManager()
    ingestion_service = DataIngestion(message_broker)
    web_socket_handler = WebSocketHandler(subscription_manager, message_broker)

    # Start WebSocket server
    server = websockets.serve(web_socket_handler.handle_connection, "localhost", 6789)
    print("WebSocket server is running on ws://localhost:6789")

    # Simulate stock data ingestion
    async def simulate_stock_data():
        stocks = ["AAPL", "GOOG", "AMZN", "MSFT"]
        while True:
            for stock in stocks:
                stock_data = {
                    "symbol": stock,
                    "price": round(100 + 20 * asyncio.get_event_loop().time() % 1, 2),
                }
                await ingestion_service.ingest_stock_data(stock_data)
                await asyncio.sleep(1)

    # Run tasks
    await asyncio.gather(server, web_socket_handler.push_updates(), simulate_stock_data())

if __name__ == "__main__":
    asyncio.run(main())
