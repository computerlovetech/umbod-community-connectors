"""Nemlig account operations. No meal-planning, camera or local inventory features."""

from typing import Annotated

from pydantic import Field
from umbod_sdk.connectors.plugin_api import Connector

from .admin_configuration import NemligConfiguration
from .api_client import NemligClient
from .configuration_check import check_configuration

connector = Connector(
    id="nemlig",
    name="Nemlig",
    configuration=NemligConfiguration,
    description="Community Nemlig account connector inspired by Mark Ruvald's nemlig_cli.",
    capability_description=(
        "Search products, read product details and order history, "
        "inspect your basket and set or remove basket quantities."
    ),
)
connector.configuration_check(check_configuration)
Product = Annotated[
    str, Field(min_length=1, description="Nemlig product ID, obtained from search.")
]


@connector.tool(description="Verify configured Nemlig account credentials and basket access.")
def account_status(configuration: NemligConfiguration):
    result = check_configuration(configuration)
    return {"valid": result.valid, "message": result.message}


@connector.tool(
    description="Search Nemlig products using the account's current delivery slot and catalog."
)
def search_products(
    query: Annotated[str, Field(min_length=1, description="Product search text.")],
    configuration: NemligConfiguration,
    limit: Annotated[int, Field(ge=1, le=100, description="Number of results.")] = 10,
    skip: Annotated[int, Field(ge=0, description="Results to skip.")] = 0,
):
    with NemligClient(configuration) as client:
        return client.search(query, limit, skip)


@connector.tool(description="Read detailed product page JSON, including productdetailspot content.")
def product_details(product_id: Product, configuration: NemligConfiguration):
    with NemligClient(configuration) as client:
        return client.product(product_id)


@connector.tool(description="Read your current Nemlig shopping basket.")
def basket_get(configuration: NemligConfiguration):
    with NemligClient(configuration) as client:
        return client.basket()


@connector.tool(
    description=(
        "Set the final quantity of a product in your Nemlig basket. "
        "Zero removes it; this is not an increment and does not check out."
    )
)
def basket_set_quantity(
    product_id: Product,
    quantity: Annotated[
        int, Field(ge=0, description="Final basket quantity; zero removes the product.")
    ],
    configuration: NemligConfiguration,
):
    with NemligClient(configuration) as client:
        return client.set_quantity(product_id, quantity)


@connector.tool(description="Read a page of your Nemlig order history.")
def order_history(
    configuration: NemligConfiguration,
    skip: Annotated[int, Field(ge=0, description="Orders to skip.")] = 0,
    take: Annotated[int, Field(ge=1, le=100, description="Orders per page.")] = 10,
):
    with NemligClient(configuration) as client:
        return client.history(skip, take)


@connector.tool(description="Read line items and details of a past Nemlig order.")
def order_details(
    order_id: Annotated[int, Field(gt=0, description="Order ID from order history.")],
    configuration: NemligConfiguration,
):
    with NemligClient(configuration) as client:
        return client.order(order_id)
