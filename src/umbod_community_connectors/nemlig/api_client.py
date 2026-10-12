"""Nemlig account protocol; independent implementation from documented CLI observations."""

import uuid
from urllib.parse import urlsplit

import httpx

from umbod_community_connectors.http import AuthenticationError, ConnectorError, request_json

from .admin_configuration import NemligConfiguration

BASE = "https://www.nemlig.com"
SEARCH = "https://webapi.prod.knl.nemlig.it/searchgateway/api/search"


class NemligClient:
    def __init__(self, configuration: NemligConfiguration, transport=None):
        self.configuration = configuration
        self.authenticated = False
        self.http = httpx.Client(
            timeout=configuration.timeout_seconds,
            transport=transport,
            follow_redirects=False,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
                ),
                "Device-Size": "desktop",
                "Platform": "web",
                "Version": "11.201.0",
                "Referer": BASE + "/",
            },
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.http.close()

    def request(self, method, path, **kwargs):
        self.http.headers["X-Correlation-Id"] = str(uuid.uuid4())
        return request_json(self.http, method, BASE + path, **kwargs)

    def tokens(self):
        anti = self.request("GET", "/webapi/AntiForgery")
        token = self.request("GET", "/webapi/Token")
        if (
            not isinstance(anti, dict)
            or not anti.get("Value")
            or not isinstance(token, dict)
            or not token.get("access_token")
        ):
            raise AuthenticationError("Nemlig did not return authentication tokens.")
        self.http.headers["X-XSRF-TOKEN"] = anti["Value"]
        self.http.headers["Authorization"] = "Bearer " + token["access_token"]

    def login(self):
        if self.authenticated:
            return
        self.tokens()
        result = self.request(
            "POST",
            "/webapi/login",
            headers={"Referer": BASE + "/login?returnUrl=%2F"},
            json={
                "Username": self.configuration.username.get_secret_value(),
                "Password": self.configuration.password.get_secret_value(),
                "CheckForExistingProducts": True,
                "DoMerge": True,
                "AppInstalled": False,
                "SaveExistingBasket": False,
            },
        )
        if not isinstance(result, dict) or "RedirectUrl" not in result:
            raise AuthenticationError("Nemlig login failed; check account credentials.")
        # Reacquire both tokens for the authenticated cookie session.
        token = self.request("GET", "/webapi/Token")
        if not isinstance(token, dict) or not token.get("access_token"):
            raise AuthenticationError("Nemlig did not return an authenticated token.")
        self.http.headers["Authorization"] = "Bearer " + token["access_token"]
        anti = self.request("GET", "/webapi/AntiForgery")
        if not isinstance(anti, dict) or not anti.get("Value"):
            raise AuthenticationError("Nemlig did not return an authenticated anti-forgery token.")
        self.http.headers["X-XSRF-TOKEN"] = anti["Value"]
        self.authenticated = True

    def get(self, path, **kwargs):
        self.login()
        return self.request("GET", path, **kwargs)

    def page_settings(self):
        app = self.get("/webapi/v2/AppSettings/Website")
        page = self.get("/", params={"GetAsJson": "1", "d": "1"})
        settings = page.get("Settings", {})
        if not settings.get("TimeslotUtc") or not app.get("CombinedProductsAndSitecoreTimestamp"):
            raise ConnectorError(
                "Nemlig returned no current delivery slot or catalog timestamp; "
                "select a delivery slot on nemlig.com."
            )
        return app, settings

    def search(self, query, limit, skip):
        app, settings = self.page_settings()
        params = {
            "query": query,
            "take": limit,
            "skip": skip,
            "recipeCount": 0,
            "timestamp": app["CombinedProductsAndSitecoreTimestamp"],
            "timeslotUtc": settings["TimeslotUtc"],
            "deliveryZoneId": settings.get("DeliveryZoneId", 1),
        }
        if settings.get("UserId"):
            params["includeFavorites"] = settings["UserId"]
        return request_json(
            self.http, "GET", SEARCH, params=params, headers={"X-Correlation-Id": str(uuid.uuid4())}
        )

    def product(self, product_id):
        result = self.search(product_id, 5, 0)
        products = result.get("Products", {}).get("Products", [])
        path = next((p.get("Url") for p in products if str(p.get("Id")) == product_id), None)
        if not isinstance(path, str) or not path:
            raise ConnectorError("No product with that ID was found.")
        # Product URLs come from remote data. Never send credentials to another host.
        parsed = urlsplit(path)
        if parsed.scheme or parsed.netloc or "\\" in path or path.startswith("//"):
            raise ConnectorError("Nemlig returned an unexpected product URL.")
        _, settings = self.page_settings()
        return self.get(
            "/" + path.lstrip("/"),
            params={"GetAsJson": "1", "t": settings["TimeslotUtc"], "d": "1"},
        )

    def basket(self):
        return self.get("/webapi/basket/GetBasket")

    def set_quantity(self, product_id, quantity):
        self.login()
        return self.request(
            "POST",
            "/webapi/basket/AddToBasket",
            json={
                "ProductId": product_id,
                "quantity": quantity,
                "AffectPartialQuantity": False,
                "disableQuantityValidation": False,
            },
        )

    def history(self, skip, take):
        return self.get("/webapi/order/GetBasicOrderHistory", params={"skip": skip, "take": take})

    def order(self, order_id):
        return self.get(f"/webapi/v2/order/GetOrderHistory/{order_id}")
