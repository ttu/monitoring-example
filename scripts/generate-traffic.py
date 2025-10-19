#!/usr/bin/env python3
"""
Traffic generator for WebStore monitoring demo
Simulates users from different countries browsing, adding to cart, and checking out
"""

import requests
import random
import time
import threading
from datetime import datetime

API_URL = "http://localhost:8000"
AUTH_TOKENS = ["user-token-123", "admin-token-456", "test-token-789"]

COUNTRIES = ["US", "UK", "DE", "FR", "JP", "BR", "IN"]

# Weight for actions
ACTION_WEIGHTS = {
    "browse": 0.4,
    "add_to_cart": 0.35,
    "checkout": 0.15,
    "view_cart": 0.05,
    "view_orders": 0.05,
}

def get_headers(token):
    return {"Authorization": f"Bearer {token}"}

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

class User:
    def __init__(self, user_id, country, is_authenticated=True):
        self.user_id = user_id
        self.country = country
        self.is_authenticated = is_authenticated
        self.token = None  # Will be set after authentication
        self.cart = []
        self.products = []

    def authenticate(self):
        """Authenticate and get token."""
        if not self.is_authenticated:
            log(f"User {self.user_id} ({self.country}): Anonymous user (browsing only)")
            return False

        # Use simple demo credentials
        credentials = [
            {"username": "user123", "password": "password123"},
            {"username": "admin", "password": "admin123"},
            {"username": "test", "password": "test123"},
        ]
        cred = random.choice(credentials)

        # Simulate authentication failures (~1%)
        if random.random() < 0.01:
            cred = {"username": cred["username"], "password": "wrong_password"}

        try:
            response = requests.post(
                f"{API_URL}/auth/login",
                json=cred,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data["token"]
                log(f"User {self.user_id} ({self.country}): Authenticated as {cred['username']}")
                return True
            else:
                log(f"User {self.user_id} ({self.country}): Authentication failed - {response.status_code}")
        except Exception as e:
            log(f"User {self.user_id} ({self.country}): Authentication error - {e}")

        # Fallback to old token method if authentication fails
        self.token = random.choice(AUTH_TOKENS)
        return False

    def fetch_products(self):
        try:
            response = requests.get(f"{API_URL}/{self.country.lower()}/products", timeout=5)
            if response.status_code == 200:
                self.products = response.json()
                log(f"User {self.user_id} ({self.country}): Fetched {len(self.products)} products")
                return True
        except Exception as e:
            log(f"User {self.user_id} ({self.country}): Failed to fetch products - {e}")
        return False

    def browse_products(self):
        if not self.products:
            self.fetch_products()

        if self.products:
            product = random.choice(self.products)
            try:
                response = requests.get(f"{API_URL}/{self.country.lower()}/products/{product['id']}", timeout=5)
                if response.status_code == 200:
                    log(f"User {self.user_id} ({self.country}): Browsing {product['name']}")
                    return True
            except Exception as e:
                log(f"User {self.user_id} ({self.country}): Failed to browse product - {e}")
        return False

    def add_to_cart(self):
        if not self.products:
            self.fetch_products()

        if self.products:
            product = random.choice(self.products)
            try:
                response = requests.post(
                    f"{API_URL}/cart/add",
                    json={
                        "product_id": product['id'],
                        "quantity": random.randint(1, 3),
                        "country": self.country
                    },
                    headers=get_headers(self.token),
                    timeout=5
                )
                if response.status_code == 200:
                    log(f"User {self.user_id} ({self.country}): Added {product['name']} to cart")
                    return True
                else:
                    log(f"User {self.user_id} ({self.country}): Failed to add to cart - {response.status_code}")
            except Exception as e:
                log(f"User {self.user_id} ({self.country}): Failed to add to cart - {e}")
        return False

    def view_cart(self):
        try:
            response = requests.get(
                f"{API_URL}/cart",
                headers=get_headers(self.token),
                timeout=5
            )
            if response.status_code == 200:
                cart_data = response.json()
                log(f"User {self.user_id} ({self.country}): Viewing cart with {len(cart_data.get('items', []))} items")
                return True
        except Exception as e:
            log(f"User {self.user_id} ({self.country}): Failed to view cart - {e}")
        return False

    def checkout(self):
        try:
            response = requests.post(
                f"{API_URL}/checkout",
                json={
                    "payment_method": random.choice(["credit_card", "debit_card", "paypal"]),
                    "country": self.country
                },
                headers=get_headers(self.token),
                timeout=10
            )
            if response.status_code == 200:
                order_data = response.json()
                log(f"User {self.user_id} ({self.country}): Checkout successful - Order {order_data.get('order_id')}")
                return True
            else:
                log(f"User {self.user_id} ({self.country}): Checkout failed - {response.status_code}")
        except Exception as e:
            log(f"User {self.user_id} ({self.country}): Checkout failed - {e}")
        return False

    def view_orders(self):
        try:
            response = requests.get(
                f"{API_URL}/orders",
                headers=get_headers(self.token),
                timeout=5
            )
            if response.status_code == 200:
                orders_data = response.json()
                log(f"User {self.user_id} ({self.country}): Viewing {len(orders_data.get('orders', []))} orders")
                return True
        except Exception as e:
            log(f"User {self.user_id} ({self.country}): Failed to view orders - {e}")
        return False

    def random_action(self):
        action = random.choices(
            list(ACTION_WEIGHTS.keys()),
            weights=list(ACTION_WEIGHTS.values())
        )[0]

        if action == "browse":
            return self.browse_products()
        elif action == "add_to_cart":
            return self.add_to_cart()
        elif action == "checkout":
            return self.checkout()
        elif action == "view_cart":
            return self.view_cart()
        elif action == "view_orders":
            return self.view_orders()

def user_session(user_id, country, duration_seconds, user_type="browser"):
    """
    Simulate a user session

    user_type:
    - "browser": Just browses products (50%)
    - "cart_abandoner": Adds to cart but doesn't checkout (30%)
    - "buyer": Authenticates and completes purchase (20%)
    """
    # Only buyers authenticate
    is_authenticated = (user_type == "buyer")
    user = User(user_id, country, is_authenticated)
    end_time = time.time() + duration_seconds

    # Step 1: Browse products (everyone does this)
    user.fetch_products()
    for _ in range(random.randint(2, 5)):
        user.browse_products()
        time.sleep(random.uniform(0.5, 1.5))

    # Step 2: Different behavior based on user type
    if user_type == "browser":
        # Just browse, no cart activity
        log(f"User {user_id} ({country}): Browser - viewing products only")
        while time.time() < end_time:
            user.browse_products()
            time.sleep(random.uniform(0.3, 0.8))

    elif user_type == "cart_abandoner":
        # Add items to cart but never checkout (simulates cart abandonment)
        log(f"User {user_id} ({country}): Cart abandoner - adding to cart but not checking out")

        # Need to authenticate to use cart
        user.is_authenticated = True
        user.authenticate()
        time.sleep(random.uniform(0.2, 0.5))

        # Add items to cart
        for _ in range(random.randint(1, 3)):
            user.add_to_cart()
            time.sleep(random.uniform(0.3, 0.8))

        # View cart but never checkout
        while time.time() < end_time:
            action = random.choice(["browse", "view_cart"])
            if action == "browse":
                user.browse_products()
            else:
                user.view_cart()
            time.sleep(random.uniform(0.3, 0.8))

    elif user_type == "buyer":
        # Complete purchase flow
        log(f"User {user_id} ({country}): Buyer - will complete checkout")
        user.authenticate()
        time.sleep(random.uniform(0.2, 0.5))

        # Add items to cart
        for _ in range(random.randint(1, 3)):
            user.add_to_cart()
            time.sleep(random.uniform(0.3, 0.8))

        # Perform random actions including checkout
        while time.time() < end_time:
            user.random_action()
            time.sleep(random.uniform(0.5, 1.5))

def generate_traffic(num_concurrent_users=5, session_duration=60):
    """Generate traffic with multiple concurrent users"""
    log(f"Starting traffic generation with {num_concurrent_users} concurrent users")
    log(f"Session duration: {session_duration} seconds")
    log(f"User mix: 50% browsers, 30% cart abandoners, 20% buyers")

    threads = []
    country_index = 0  # Round-robin index to ensure all countries get traffic

    try:
        while True:
            # Start new user sessions
            while len([t for t in threads if t.is_alive()]) < num_concurrent_users:
                # Use round-robin to ensure even distribution across all countries
                country = COUNTRIES[country_index % len(COUNTRIES)]
                country_index += 1

                user_id = f"user_{random.randint(1000, 9999)}"

                # Select user type: 50% browsers, 30% cart abandoners, 20% buyers
                rand = random.random()
                if rand < 0.50:
                    user_type = "browser"
                elif rand < 0.80:  # 0.50 to 0.80 = 30%
                    user_type = "cart_abandoner"
                else:  # 0.80 to 1.00 = 20%
                    user_type = "buyer"

                thread = threading.Thread(
                    target=user_session,
                    args=(user_id, country, session_duration, user_type)
                )
                thread.start()
                threads.append(thread)

                time.sleep(random.uniform(1, 3))

            # Clean up finished threads
            threads = [t for t in threads if t.is_alive()]
            time.sleep(5)

    except KeyboardInterrupt:
        log("\nStopping traffic generation...")
        log("Waiting for active sessions to complete...")
        for thread in threads:
            thread.join(timeout=10)
        log("Traffic generation stopped")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate traffic for WebStore")
    parser.add_argument(
        "--users",
        type=int,
        default=5,
        help="Number of concurrent users (default: 5)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Session duration in seconds (default: 60)"
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:8000",
        help="API URL (default: http://localhost:8000)"
    )

    args = parser.parse_args()
    API_URL = args.url

    log("=" * 60)
    log("WebStore Traffic Generator")
    log("=" * 60)
    log(f"API URL: {API_URL}")
    log(f"Concurrent Users: {args.users}")
    log(f"Session Duration: {args.duration}s")
    log("=" * 60)

    generate_traffic(args.users, args.duration)
