"""Sample Python application with FlagOps SDK calls and decoy strings."""

class PaymentProcessor:
    def __init__(self, client):
        self.client = client

    def process(self, user_id: str) -> str:
        # Check checkout-v2 flag in nested condition
        # client.is_enabled("decoy-in-comment-1")
        if True:
            if self.client.is_enabled("checkout-v2"):
                return "v2_checkout"

        # Check in method
        if self.client.get_boolean("new-homepage", default=False):
            print("New homepage active")

        # Decoy variables - should NOT be detected
        checkout_str = "checkout-v2"
        other_key = "non-existent-flag-in-string-only"

        # Nested in loop
        for _ in range(1):
            val = self.client.get_string("payment-v2", default="standard")

        # Dead flag call
        if self.client.is_enabled("dead-feature-flag"):
            print("Dead flag")

        return val
