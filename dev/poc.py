import abc
import asyncio
import json
import pickle
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generic, List, Optional, TypeVar

from harborapi import HarborAsyncClient
from harborapi.ext.api import get_artifact_vulnerabilities
from harborapi.ext.artifact import ArtifactInfo
from harborapi.ext.report import ArtifactReport
from harborapi.models.scanner import Severity
from textual.app import App, ComposeResult
from textual.containers import Container, Grid
from textual.reactive import reactive
from textual.widgets import Checkbox, Footer, Header, Input, Static

from harbortui.config import load_config

T = TypeVar("T")

config = load_config()
harbor_client = HarborAsyncClient(**config.harbor.credentials, timeout=20, logging=True)


async def get_artifacts() -> List[ArtifactInfo]:
    try:
        with open("artifacts.json") as f:
            artifacts = json.load(f)
        assert isinstance(artifacts, list), "artifacts.json must contain a list"
        if not artifacts:
            raise ValueError("Empty pickle file")
        artifacts = [ArtifactInfo(**a) for a in artifacts]
    except:
        artifacts = await get_artifact_vulnerabilities(harbor_client, exc_ok=True)
        with open("artifacts.json", "w") as f:
            json.dump([a.dict() for a in artifacts], f, indent=4)
    return artifacts


class FilterType(Enum):
    INPUT = "input"
    SWITCH = "switch"
    SELECTION = "selection"


@dataclass
class Filter(abc.ABC):
    """A filter which can be applied to a list of artifacts."""

    name: str
    method: Callable[[ArtifactReport, Any], ArtifactReport]
    default: Any
    type: FilterType
    value: Any = None  # the current value of the filter

    # TODO: add method for validating defaults for subclasses

    def __post_init__(self):
        if self.value is None:
            self.value = self.default

    @abc.abstractmethod
    def validate(self) -> bool:
        """Validates the value of the filter"""
        pass


@dataclass
class InputFilter(Filter):
    type: FilterType = FilterType.INPUT
    default: str = ""
    regex: Optional[Any] = None

    def validate(self) -> bool:
        if self.regex is None:
            return True
        return self.regex.match(self.default) is not None


@dataclass
class SwitchFilter(Filter, Generic[T]):
    default: T
    type: FilterType = FilterType.SWITCH
    options: List[T] = field(default_factory=list)

    def validate(self) -> bool:
        return self.default in self.options


@dataclass
class SelectionFilter(Filter):
    type: FilterType = FilterType.SELECTION
    default: List[str] = field(default_factory=list)
    options: Optional[List[str]] = None  # selection options
    value: List[str] = field(default_factory=list)

    def validate(self) -> bool:
        return all(o in self.options for o in self.value)


class FilterPanel(Container):
    filters = reactive([], layout=True)

    def __init__(self, filters: List[Filter], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.filters = filters

    def compose(self) -> ComposeResult:
        yield Static("Filters"),
        yield Container(filter for filter in self.filters)


class FilterField(Container):
    """The name of the filter and its input"""

    def __init__(self, filter: Filter, **kwargs):
        kwargs["id"] = f"filter-{filter.name}"
        super().__init__(**kwargs)
        self.filter = filter

    def compose(self) -> ComposeResult:
        yield Static(f"{self.filter.name}: ")
        if self.filter.type == FilterType.INPUT:
            yield Input(
                id=f"filter-{self.filter.name}-input",
                placeholder=self.filter.default,
            )
        elif self.filter.type == FilterType.SWITCH:
            yield Checkbox(
                id=f"filter-{self.filter.name}-switch",
                placeholder=self.filter.default,
            )
        # TODO: selection group
        # elif self.filter.type == FilterType.SELECTION:
        #     pass


class Title(Static):
    pass


class FilterSelection(Container):
    """A selection of filters that can be applied to a list of artifacts."""

    filters = reactive([], layout=True)

    def __init__(self, filters: List[Filter], *args, **kwargs) -> None:
        self.filters = filters

    def compose(self) -> ComposeResult:
        yield Title("Add Filter")
        yield Grid(FilterField(f) for f in self.filters)


class Sidebar(Container):
    def compose(self) -> ComposeResult:
        yield Title("Textual Demo")
        yield FilterSelection()


class ResultPanel(Container):
    results: reactive[Optional[ArtifactReport]] = reactive(None, layout=True)
    report: reactive(Optional[ArtifactReport]) = reactive(None)

    def __init__(self, report: ArtifactReport, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.report = report
        if not self.results:
            self.results = report.artifacts

    def compose(self) -> ComposeResult:
        yield Title("Results")
        if self.report is None:
            contents = Static("No results")
        else:
            pass
        yield Container(
            id="results-list",
        )

    def watch_report(
        self, old: Optional[ArtifactReport], new: Optional[ArtifactReport]
    ) -> None:
        if old is None and new is not None:
            self.report = new
            if not self.results:
                self.results = new


class MainGrid(Grid):
    pass


class VulnApp(App):
    report = reactive(None, layout=True)  # type: Optional[ArtifactReport]
    filters = reactive([], layout=True)

    CSS_PATH = "poc.css"

    def compose(self) -> ComposeResult:
        yield Header()
        yield MainGrid()
        yield Footer()

    async def on_mount(self) -> None:
        asyncio.create_task(self.fetch_artifacts())

    async def init_filters(self) -> None:
        if self.report is None:
            return
        self.filters = [
            SelectionFilter(
                "Severity",
                value=[Severity.high],
                default=list(Severity),
                options=list(Severity),
                method=self.report.filter_severity,
            ),
            InputFilter("CVE", default="", method=self.report.with_cve),
            InputFilter("Package", default="", method=self.report.with_package),
            InputFilter("Description", default="", method=self.report.with_description),
        ]

    async def fetch_artifacts(self) -> None:
        artifacts = await get_artifacts()
        self.report = ArtifactReport(artifacts)
        self.init_filters()
        self.query_one(MainGrid).mount(
            FilterPanel(self.filters, id="filter-panel"),
            ResultPanel(self.report, id="results-panel"),
        )
        self.refresh(layout=True)


app = VulnApp()
app.run()
