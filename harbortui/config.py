import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypedDict, Union

import tomli
from loguru import logger
from pydantic import BaseModel as PydanticBaseModel
from pydantic import BaseSettings, Field, root_validator, validator
from pydantic.fields import ModelField
from rich.console import Console, ConsoleOptions, RenderResult
from rich.table import Column, Table

from .dirs import CONFIG_DIR

CONFIG_FILE = CONFIG_DIR / "config.toml"


def load_toml_file(config_file: Path) -> Dict[str, Any]:
    """Load a TOML file and return the contents as a dict.

    Parameters
    ----------
    config_file : Path,
        Path to the TOML file to load.

    Returns
    -------
    Dict[str, Any]
        A TOML file as a dictionary
    """
    conf = tomli.loads(config_file.read_text())
    return conf


class BaseModel(PydanticBaseModel):
    """Base model shared by all config models."""

    # https://pydantic-docs.helpmanual.io/usage/model_config/#change-behaviour-globally

    @root_validator(pre=True)
    def _pre_root_validator(cls, values: dict) -> dict:
        """Checks for unknown fields and logs a warning if any are found.

        Since we use `extra = "allow"`, it can be useful to check for unknown
        fields and log a warning if any are found, otherwise they will be
        silently ignored.

        See: Config class below.
        """
        clsname = getattr(cls, "__name__", str(cls))
        for key in values:
            if key not in cls.__fields__:
                logger.warning(
                    "{}: Got unknown config key {!r}.",
                    clsname,
                    key,
                )
        return values

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Rich console representation of the model.

        Returns a table with the model's fields and values.

        If the model has a nested model, the nested model's table representation
        is printed after the main table. Should support multiple levels of
        nested models, but not tested.

        See: https://rich.readthedocs.io/en/latest/protocol.html#console-render
        """
        try:
            name = self.__name__  # type: ignore # this is populated by Pydantic
        except AttributeError:
            name = self.__class__.__name__
        table = Table(
            Column(
                header="Setting", justify="left", style="green", header_style="bold"
            ),
            Column(header="Value", style="blue", justify="left"),
            Column(header="Description", style="yellow", justify="left"),
            title=f"[bold]{name}[/bold]",
            title_style="magenta",
            title_justify="left",
        )
        subtables = []
        for field_name, field in self.__fields__.items():
            # Try to use field title if available
            field_title = field.field_info.title or field_name

            attr = getattr(self, field_name)
            try:
                # issubclass is prone to TypeError, so we use try/except
                if issubclass(field.type_, BaseModel):
                    subtables.append(attr)
                    continue
            except:
                pass
            table.add_row(field_title, str(attr), field.field_info.description)

        if table.rows:
            yield table
        yield from subtables

    class Config:
        # Allow for future fields to be added to the config file without
        # breaking older versions of LDAP2Zabbix
        extra = "allow"


def init_config_dir() -> None:
    """Create the config directory if it does not exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


class HarborCredentialsKwargs(TypedDict):
    url: str
    username: Optional[str]
    secret: Optional[str]
    credentials: Optional[str]
    credentials_file: Optional[Path]


class HarborSettings(BaseModel):
    url: str = ""
    username: Optional[str] = None
    secret: Optional[str] = None
    credentials_file: Optional[Path] = None
    credentials_base64: Optional[str] = None

    @property
    def can_authenticate(self) -> bool:
        if not self.url:  # url is required
            return False

        # One of these methods is required
        if self.username and self.secret:
            return True
        elif self.credentials_base64:
            return True
        elif self.credentials_file:
            return True
        else:
            return False

    @property
    def credentials(self) -> HarborCredentialsKwargs:
        """Fetches kwargs that can be passed to HarborAsyncClient for
        user authentication.

        Returns
        -------
        HarborCredentialsKwargs
            A dictionary with either base64 credentials, username and password
            or a path to a credentials file.
        """
        return HarborCredentialsKwargs(
            url=self.url,
            username=self.username,
            secret=self.secret,
            credentials=self.credentials_base64,
            credentials_file=self.credentials_file,
        )


class LogLevel(Enum):
    """Enum for log levels."""

    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @classmethod
    def _missing_(cls, value: object) -> "LogLevel":
        """Convert string to enum value.

        Raises
        ------
        ValueError
            If the value is not a valid log level.
        """
        if not isinstance(value, str):
            raise TypeError(f"Expected str, got {type(value)}")
        for member in cls:
            if member.value == value.upper():
                return member
        raise ValueError(f"{value} is not a valid log level.")

    def __str__(self) -> str:
        """Return the enum value as a string."""
        return self.value


class LoggingSettings(BaseModel):
    enabled: bool = True
    structlog: bool = False
    level: LogLevel = LogLevel.INFO


class HarborTUIConfig(BaseModel):
    harbor: HarborSettings = Field(default_factory=HarborSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    config_file: Optional[Path] = None  # set by `from_file()` if loaded from file

    @classmethod
    def from_file(cls, config_file: Path = CONFIG_FILE) -> "HarborTUIConfig":
        """Create a Config object from a TOML file.

        Parameters
        ----------
        config_file : Path
            Path to the TOML file.
            If `None`, the default configuration file is used.

        Returns
        -------
        Config
            A Config object.
        """
        if not config_file.exists():
            raise FileNotFoundError(f"Config file {config_file} does not exist.")
        config = load_toml_file(config_file)
        return cls(**config, config_file=config_file)  # type: ignore # mypy bug until Self type is supported


def load_config() -> Optional[HarborTUIConfig]:
    """Load the config file."""
    try:
        return HarborTUIConfig.from_file()
    except Exception as e:
        logger.error("Could not load config file: {}", e)
        return None
