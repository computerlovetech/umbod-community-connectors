"""HTTP errors intentionally exclude response bodies, request URLs and credentials."""

import httpx


class ConnectorError(RuntimeError):
    """A provider rejected a request or returned an unsupported response."""


class AuthenticationError(ConnectorError):
    pass


class UnavailableError(ConnectorError):
    pass


def request_json(client: httpx.Client, method: str, url: str, **kwargs):
    try:
        response = client.request(method, url, **kwargs)
    except httpx.RequestError:
        raise UnavailableError("Provider could not be reached; check the connection.") from None
    if response.status_code in (401, 403):
        raise AuthenticationError("Provider rejected access; check credentials and account access.")
    if not response.is_success:
        raise ConnectorError(f"Provider returned HTTP {response.status_code}; request not retried.")
    if not response.content:
        return None
    try:
        result = response.json()
    except ValueError:
        raise ConnectorError(
            "Provider returned a non-JSON response; the session may have expired."
        ) from None
    if isinstance(result, dict) and result.get("errors"):
        raise ConnectorError("Provider reported a GraphQL error; request not retried.")
    return result
