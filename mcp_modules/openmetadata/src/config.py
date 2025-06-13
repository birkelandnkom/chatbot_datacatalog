from dataclasses import dataclass
import os


@dataclass
class Config:
    OPENMETADATA_HOST: str | None = None
    OPENMETADATA_JWT_TOKEN: str | None = None
    OPENMETADATA_USERNAME: str | None = None
    OPENMETADATA_PASSWORD: str | None = None

    @classmethod
    def from_env(cls) -> "Config":
        if not os.getenv("OPENMETADATA_HOST"):
            raise ValueError("OPENMETADATA_HOST is not set")
        if not os.getenv("OPENMETADATA_JWT_TOKEN") and not (
            os.getenv("OPENMETADATA_USERNAME") and os.getenv("OPENMETADATA_PASSWORD")
        ):
            raise ValueError(
                "Either OPENMETADATA_JWT_TOKEN or OPENMETADATA_USERNAME and OPENMETADATA_PASSWORD must be set"
            )

        return cls(
            OPENMETADATA_HOST=os.getenv("OPENMETADATA_HOST"),
            OPENMETADATA_JWT_TOKEN=os.getenv("OPENMETADATA_JWT_TOKEN"),
            OPENMETADATA_USERNAME=os.getenv("OPENMETADATA_USERNAME"),
            OPENMETADATA_PASSWORD=os.getenv("OPENMETADATA_PASSWORD"),
        )
