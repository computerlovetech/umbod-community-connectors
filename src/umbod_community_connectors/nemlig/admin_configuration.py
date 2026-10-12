from pydantic import ConfigDict, Field, SecretStr
from umbod_sdk.connectors.proxies import Model


class NemligConfiguration(Model):
    model_config = ConfigDict(extra="forbid")
    username: SecretStr = Field(description="Nemlig account email.", min_length=1)
    password: SecretStr = Field(description="Nemlig account password.", min_length=1)
    timeout_seconds: float = Field(default=30, gt=0, le=120)
