import importlib
import json

import httpx
import pytest

from umbod_community_connectors import nemlig
from umbod_community_connectors.http import AuthenticationError, ConnectorError
from umbod_community_connectors.nemlig.admin_configuration import NemligConfiguration
from umbod_community_connectors.nemlig.api_client import NemligClient
from umbod_community_connectors.server import bind_tool

CONFIG = NemligConfiguration(username="fixture@example.org", password="fixture-password")


class Provider:
    def __init__(self, login_ok=True, slot=True, product_url="milk-123"):
        self.calls = []
        self.login_ok = login_ok
        self.slot = slot
        self.product_url = product_url
        self.token_calls = 0
        self.xsrf_calls = 0

    def __call__(self, request):
        self.calls.append(request)
        path = request.url.path
        assert request.headers["X-Correlation-Id"]
        if path == "/webapi/AntiForgery":
            self.xsrf_calls += 1
            return httpx.Response(
                200,
                json={"Value": f"xsrf-{self.xsrf_calls}"},
                headers={"Set-Cookie": "fixture=session; Path=/"},
            )
        if path == "/webapi/Token":
            self.token_calls += 1
            return httpx.Response(200, json={"access_token": f"token-{self.token_calls}"})
        if path == "/webapi/login":
            assert request.headers["Authorization"] == "Bearer token-1"
            assert request.headers["X-XSRF-TOKEN"] == "xsrf-1"
            assert "fixture=session" in request.headers["Cookie"]
            assert json.loads(request.content) == {
                "Username": "fixture@example.org",
                "Password": "fixture-password",
                "CheckForExistingProducts": True,
                "DoMerge": True,
                "AppInstalled": False,
                "SaveExistingBasket": False,
            }
            return httpx.Response(
                200, json={"RedirectUrl": "/"} if self.login_ok else {"Message": "bad password"}
            )
        assert request.headers["Authorization"] == "Bearer token-2"
        assert request.headers["X-XSRF-TOKEN"] == "xsrf-2"
        if path == "/webapi/v2/AppSettings/Website":
            return httpx.Response(200, json={"CombinedProductsAndSitecoreTimestamp": "catalog-1"})
        if path == "/":
            return httpx.Response(
                200,
                json={
                    "Settings": {
                        "TimeslotUtc": "future-slot" if self.slot else None,
                        "DeliveryZoneId": 7,
                        "UserId": "user-1",
                    }
                },
            )
        if path == "/searchgateway/api/search":
            assert request.url.host == "webapi.prod.knl.nemlig.it"
            assert "fixture=session" not in request.headers.get("cookie", "")
            assert request.url.params["timeslotUtc"] == "future-slot"
            assert request.url.params["timestamp"] == "catalog-1"
            assert request.url.params["deliveryZoneId"] == "7"
            assert request.url.params["includeFavorites"] == "user-1"
            return httpx.Response(
                200,
                json={
                    "Products": {"Products": [{"Id": "123", "Url": self.product_url}]},
                    "metadata": "preserved",
                },
            )
        if path == "/milk-123":
            assert request.url.params["t"] == "future-slot"
            return httpx.Response(
                200, json={"content": [{"TemplateName": "productdetailspot", "data": "original"}]}
            )
        return httpx.Response(200, json={"raw": "provider-response"})


def install(monkeypatch, provider):
    monkeypatch.setattr(
        nemlig, "NemligClient", lambda cfg: NemligClient(cfg, httpx.MockTransport(provider))
    )


@pytest.mark.parametrize(
    "tool,args,path",
    [
        ("basket_get", {}, "/webapi/basket/GetBasket"),
        ("basket_set_quantity", {"product_id": "123", "quantity": 0}, "/webapi/basket/AddToBasket"),
        ("basket_set_quantity", {"product_id": "123", "quantity": 3}, "/webapi/basket/AddToBasket"),
        ("order_history", {"skip": 10, "take": 5}, "/webapi/order/GetBasicOrderHistory"),
        ("order_details", {"order_id": 42}, "/webapi/v2/order/GetOrderHistory/42"),
    ],
)
def test_account_operations(monkeypatch, tool, args, path):
    provider = Provider()
    install(monkeypatch, provider)
    assert bind_tool(getattr(nemlig, tool), CONFIG)(**args) == {"raw": "provider-response"}
    assert [r.url.path for r in provider.calls[:5]] == [
        "/webapi/AntiForgery",
        "/webapi/Token",
        "/webapi/login",
        "/webapi/Token",
        "/webapi/AntiForgery",
    ]
    request = provider.calls[-1]
    assert request.url.path == path
    if tool == "basket_set_quantity":
        assert request.method == "POST"
        assert json.loads(request.content) == {
            "ProductId": "123",
            "quantity": args["quantity"],
            "AffectPartialQuantity": False,
            "disableQuantityValidation": False,
        }
    else:
        assert request.method == "GET"
    if tool == "order_history":
        assert dict(request.url.params) == {"skip": "10", "take": "5"}


def test_search_preserves_full_response(monkeypatch):
    provider = Provider()
    install(monkeypatch, provider)
    result = nemlig.search_products("mælk", CONFIG, limit=4, skip=8)
    assert result["metadata"] == "preserved"
    query = provider.calls[-1].url.params
    assert query["query"] == "mælk"
    assert query["take"] == "4"
    assert query["skip"] == "8"


def test_product_details(monkeypatch):
    provider = Provider()
    install(monkeypatch, provider)
    result = nemlig.product_details("123", CONFIG)
    assert result["content"][0]["data"] == "original"
    assert provider.token_calls == 2  # One login flow for this operation.


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/steal",
        "//evil.example/steal",
        "\\evil.example",
        "http://www.nemlig.com/item",
    ],
)
def test_product_urls_cannot_exfiltrate_credentials(url):
    provider = Provider(product_url=url)
    with NemligClient(CONFIG, httpx.MockTransport(provider)) as client:
        with pytest.raises(ConnectorError, match="unexpected product URL"):
            client.product("123")
    assert all(
        r.url.host in ("www.nemlig.com", "webapi.prod.knl.nemlig.it") for r in provider.calls
    )


def test_missing_slot_never_uses_expired_hardcoded_fallback():
    provider = Provider(slot=False)
    with NemligClient(CONFIG, httpx.MockTransport(provider)) as client:
        with pytest.raises(ConnectorError, match="delivery slot"):
            client.search("milk", 10, 0)
    assert not any("searchgateway" in r.url.path for r in provider.calls)


@pytest.mark.parametrize("valid", [True, False])
def test_configuration_checks(monkeypatch, valid):
    checks = importlib.import_module("umbod_community_connectors.nemlig.configuration_check")
    provider = Provider(login_ok=valid)
    monkeypatch.setattr(
        checks, "NemligClient", lambda cfg: NemligClient(cfg, httpx.MockTransport(provider))
    )
    result = nemlig.account_status(CONFIG)
    assert result["valid"] is valid
    assert "fixture-password" not in str(result)
    assert not any("AddToBasket" in r.url.path for r in provider.calls)


def test_network_check_failure(monkeypatch):
    checks = importlib.import_module("umbod_community_connectors.nemlig.configuration_check")

    def handler(request):
        raise httpx.ConnectError("fixture-password", request=request)

    monkeypatch.setattr(
        checks, "NemligClient", lambda cfg: NemligClient(cfg, httpx.MockTransport(handler))
    )
    result = nemlig.account_status(CONFIG)
    assert result["valid"] is False
    assert "fixture-password" not in str(result)


def test_failed_login_stops_before_account_operation():
    provider = Provider(login_ok=False)
    with NemligClient(CONFIG, httpx.MockTransport(provider)) as client:
        with pytest.raises(AuthenticationError):
            client.set_quantity("123", 3)
    assert len(provider.calls) == 3
