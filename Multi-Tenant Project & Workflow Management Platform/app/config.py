from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str 
    secret_key: str 
    algorithm: str 
    access_token_expire_minutes: int 
    refresh_token_expire_days: int 
    upload_directory: str 
    max_upload_size_bytes: int 
    allow_public_registration: bool = True

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()