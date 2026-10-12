from umbod_sdk.connectors.plugin_api import ConfigurationCheckResult

from umbod_community_connectors.http import AuthenticationError, ConnectorError

from .admin_configuration import NemligConfiguration
from .api_client import NemligClient


def check_configuration(configuration: NemligConfiguration) -> ConfigurationCheckResult:
    try:
        with NemligClient(configuration) as client:
            client.basket()
    except AuthenticationError as error:
        return ConfigurationCheckResult.invalid(
            str(error), field_messages={"password": "Check your Nemlig login."}
        )
    except ConnectorError as error:
        return ConfigurationCheckResult.invalid(str(error))
    return ConfigurationCheckResult.valid()
