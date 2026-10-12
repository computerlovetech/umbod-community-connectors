# Nemlig

Inspired by Mark Ruvald's [nemlig_cli](https://github.com/eisbaw/nemlig_cli).

## Configuration

Enter this JSON as the secret `UMBOD_CONNECTOR_CONFIG` environment variable in Umbod Desktop:

```json
{"username":"YOUR_EMAIL","password":"YOUR_PASSWORD"}
```

An optional `timeout_seconds` (default 30, maximum 120) controls HTTP requests. The SDK models both login fields as secrets. The connector performs the reference CLI's anti-forgery/token/login flow and refreshes both tokens after login. Session cookies and tokens remain in memory for the duration of a tool call.

Enable `account_status` to verify login and basket access. The check authenticates and reads the basket; it does not call `AddToBasket`. Login retains the reference protocol's existing-basket merge flags.

## Tools

| Tool | Behavior |
| --- | --- |
| `account_status` | Check account login and basket access |
| `search_products` | Search with `query`, `limit`, and `skip`, using current delivery context |
| `product_details` | Resolve a product ID and retrieve its full product page JSON |
| `basket_get` | Read the current basket |
| `basket_set_quantity` | Set the **final** quantity; zero removes the product |
| `order_history` | List orders with `skip` and `take` |
| `order_details` | Read a past order by its numeric ID |

Example: calling `basket_set_quantity(product_id="123", quantity=2)` requests a final quantity of two, even if the basket already contains one. This tool is the connector's only explicit basket mutation and can be disabled independently in Umbod.

Search returns the full response: products are under `Products.Products`. Product details return the original page response; look for a `productdetailspot` element in `content`. Orders and baskets also preserve provider JSON.

Select a delivery slot on nemlig.com if the account has none. The connector uses the current catalog timestamp and slot returned by the provider; it does not reuse the reference CLI's hardcoded historical fallback slot.

No checkout, camera/fridge, meal planner, local grocery list, budget, or Google Sheets tools are included. No live account has been tested for this release.
