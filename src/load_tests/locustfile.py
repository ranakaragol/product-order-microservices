import os
import random
from typing import Any
from uuid import uuid4

from locust import HttpUser, between, task
from locust.exception import StopUser

DEFAULT_PASSWORD = "locust-pass-123"


def _build_unique_username(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


class AuthenticatedGatewayUser(HttpUser):
    """Registers and logs in once per virtual user, then reuses JWT for protected calls."""

    abstract = True

    wait_time = between(1, 3)
    host = os.getenv("LOCUST_HOST", "http://localhost:8000")

    username_prefix = "locust-user"
    fixed_username: str | None = None

    def on_start(self) -> None:
        self.username = self.fixed_username or _build_unique_username(self.username_prefix)
        self.password = DEFAULT_PASSWORD
        self.token = None

        self._register()
        self._login()

        if not self.token:
            raise StopUser("Login did not return a JWT token.")

    @property
    def auth_headers(self) -> dict[str, str]:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    def _register(self) -> None:
        payload = {"username": self.username, "password": self.password}

        with self.client.post(
            "/auth/register",
            name="POST /auth/register",
            json=payload,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                return

            # Very unlikely with UUID usernames, but fallback keeps user setup resilient.
            if response.status_code == 409:
                response.success()
                return

            response.failure(
                f"Register failed for {self.username}. Status={response.status_code}, Body={response.text[:200]}"
            )

    def _login(self) -> None:
        payload = {"username": self.username, "password": self.password}

        with self.client.post(
            "/auth/login",
            name="POST /auth/login",
            json=payload,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(
                    f"Login failed for {self.username}. Status={response.status_code}, Body={response.text[:200]}"
                )
                return

            data = self._json_or_none(response)
            token = data.get("token") if data else None
            if not token:
                response.failure("Login response does not include token field.")
                return

            self.token = token
            response.success()

    @staticmethod
    def _json_or_none(response) -> dict[str, Any] | None:
        try:
            data = response.json()
            if isinstance(data, dict):
                return data
        except Exception:
            return None
        return None


class ReadOnlyUser(AuthenticatedGatewayUser):
    """Read-heavy user: mostly product and order listing."""

    weight = 3
    username_prefix = "locust-ro"

    @task(5)
    def get_products(self) -> None:
        with self.client.get(
            "/products",
            name="GET /products",
            headers=self.auth_headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(
                    f"GET /products failed. Status={response.status_code}, Body={response.text[:200]}"
                )

    @task(4)
    def get_orders(self) -> None:
        with self.client.get(
            "/orders",
            name="GET /orders",
            headers=self.auth_headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(
                    f"GET /orders failed. Status={response.status_code}, Body={response.text[:200]}"
                )


class WriterUser(AuthenticatedGatewayUser):
    """Writer user: still read-focused, but occasionally creates an order."""

    weight = 1
    username_prefix = "locust-wr"
    fixed_username = "locust-writer"

    @task(5)
    def get_products(self) -> None:
        with self.client.get(
            "/products",
            name="GET /products",
            headers=self.auth_headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(
                    f"GET /products failed. Status={response.status_code}, Body={response.text[:200]}"
                )

    @task(3)
    def get_orders(self) -> None:
        with self.client.get(
            "/orders",
            name="GET /orders",
            headers=self.auth_headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(
                    f"GET /orders failed. Status={response.status_code}, Body={response.text[:200]}"
                )

    @task(1)
    def post_order(self) -> None:
        product_id = self._pick_product_id()

        payload = {
            "customer_id": self.username,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": random.randint(1, 3),
                    "unit_price": round(random.uniform(10.0, 200.0), 2),
                }
            ],
        }

        with self.client.post(
            "/orders",
            name="POST /orders",
            headers=self.auth_headers,
            json=payload,
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201):
                response.success()
                return

            if response.status_code in (401, 403):
                response.failure(
                    "POST /orders rejected by authorization policy. "
                    f"Status={response.status_code}, Body={response.text[:200]}"
                )
                return

            response.failure(
                f"POST /orders failed. Status={response.status_code}, Body={response.text[:200]}"
            )

    def _pick_product_id(self) -> str:
        with self.client.get(
            "/products",
            name="GET /products (for order seed)",
            headers=self.auth_headers,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(
                    f"Cannot seed order from products. Status={response.status_code}, Body={response.text[:200]}"
                )
                return "synthetic-product"

            try:
                products = response.json()
            except Exception:
                response.failure("GET /products returned non-JSON while seeding order payload.")
                return "synthetic-product"

            if isinstance(products, list) and products:
                first = products[0]
                if isinstance(first, dict) and first.get("id"):
                    response.success()
                    return str(first["id"])

            response.success()
            return "synthetic-product"
