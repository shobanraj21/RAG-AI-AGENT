
import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


class Settings:

    def __getattr__(self, name: str):
        key = name.upper()

        value = os.getenv(key)

        if value is None:
            raise RuntimeError(
                f"Missing required environment variable: {key}"
            )

        return value


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()