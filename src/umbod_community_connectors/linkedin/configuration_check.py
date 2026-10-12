from umbod_sdk.connectors.plugin_api import ConfigurationCheckResult

from umbod_community_connectors.http import AuthenticationError, ConnectorError

from .admin_configuration import LinkedInConfiguration
from .api_client import LinkedInClient


def check_configuration(configuration: LinkedInConfiguration) -> ConfigurationCheckResult:
    try:
        with LinkedInClient(configuration) as client:
            result = client.me()
            if not isinstance(result, dict) or not result.get("miniProfile"):
                raise ConnectorError("Account response is missing profile data.")
    except AuthenticationError as error:
        return ConfigurationCheckResult.invalid(
            str(error), field_messages={"li_at": "Check your session cookies."}
        )
    except ConnectorError as error:
        return ConfigurationCheckResult.invalid(str(error))
    return ConfigurationCheckResult.valid()
