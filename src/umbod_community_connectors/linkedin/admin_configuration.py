import json

from pydantic import ConfigDict, Field, SecretStr, model_validator
from umbod_sdk.connectors.proxies import Model


class LinkedInConfiguration(Model):
    model_config = ConfigDict(extra="forbid")
    li_at: SecretStr = Field(description="LinkedIn li_at session cookie.")
    jsessionid: SecretStr | None = Field(
        default=None, description="Browser JSESSIONID cookie, if available."
    )
    browser_cookies: SecretStr | None = Field(
        default=None,
        description="Optional JSON object of LinkedIn browser cookies; needed for some writes.",
    )
    timeout_seconds: float = Field(default=30, gt=0, le=120)

    @model_validator(mode="after")
    def validate_cookies(self):
        cookies = {"li_at": self.li_at.get_secret_value()}
        if not cookies["li_at"]:
            raise ValueError("li_at must not be empty")
        if self.browser_cookies is not None:
            try:
                additional = json.loads(self.browser_cookies.get_secret_value())
            except ValueError:
                raise ValueError("browser_cookies must be a JSON object of strings") from None
            if not isinstance(additional, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in additional.items()
            ):
                raise ValueError("browser_cookies must be a JSON object of strings")
            cookies.update(additional)
        if self.jsessionid:
            cookies["JSESSIONID"] = self.jsessionid.get_secret_value()
        for name, value in cookies.items():
            if not name or any(c in name for c in "\r\n;= ") or any(c in value for c in "\r\n;"):
                raise ValueError("Invalid cookie name or value")
        return self
