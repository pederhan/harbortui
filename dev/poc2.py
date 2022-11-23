import abc
import asyncio
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generic, List, Optional, TypeVar

from harborapi import HarborAsyncClient
from harborapi.ext.api import get_artifact_vulnerabilities
from harborapi.ext.artifact import ArtifactInfo
from harborapi.ext.report import ArtifactReport
from harborapi.models.scanner import Severity
from textual import log
from textual.app import App, ComposeResult
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, Checkbox, Footer, Header, Input, Static

from harbortui.config import load_config

T = TypeVar("T")

config = load_config()
harbor_client = HarborAsyncClient(**config.harbor.credentials, timeout=20, logging=True)


async def get_artifacts() -> List[ArtifactInfo]:
    try:
        with open("artifacts.json") as f:
            loop = asyncio.get_event_loop()
            artifacts = await loop.run_in_executor(None, json.load, f)
            # artifacts = json.load(f)
        assert isinstance(artifacts, list), "artifacts.json must contain a list"
        if not artifacts:
            raise ValueError("Empty list of artifacts")
        artifacts = [ArtifactInfo(**a) for a in artifacts]
    except (ValueError, json.JSONDecodeError):
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
    """A filter which can be applied to an ArtifactReport.

    Each filter contains a callable (method) which takes an ArtifactReport and
    a value and returns a new ArtifactReport.

    The value of `method` is usually a method of the ArtifactReport class,
    but it can be any callable with the signature
    (ArtifactReport, Any) -> ArtifactReport.
    """

    name: str
    method: Callable[[ArtifactReport, str], ArtifactReport]
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


_filters = [
    InputFilter(name="CVE", method=ArtifactReport.with_cve),
    InputFilter(name="Description", method=ArtifactReport.with_description),
    InputFilter(name="Package", method=ArtifactReport.with_package),
    InputFilter(name="Repository", method=ArtifactReport.with_repository),
]
FILTERS = {f.name: f for f in _filters}


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
                id=f"filter-input-{self.filter.name}",
                placeholder=self.filter.default,
            )
        elif self.filter.type == FilterType.SWITCH:
            yield Checkbox(
                id=f"filter-switch-{self.filter.name}",
                placeholder=self.filter.default,
            )
        # TODO: selection group
        # elif self.filter.type == FilterType.SELECTION:
        #     pass

    # @property
    # def value(self) -> Any:

    class Updated(Message):
        pass


class DropdownButton(Button):
    """A button for sorting the artifact list"""

    # TODO: make this more general?

    def __init__(self, label: str, **kwargs):
        kwargs["id"] = f"sort-{label.casefold().replace(' ', '-')}"
        super().__init__(label, **kwargs)

    def on_click(self, event: Message) -> None:
        self.app.sort_by = self.name

    class Updated(Message):
        pass


class Dropdown(Container):
    """A dropdown menu"""

    COMPONENT_CLASSES = {
        "dropdown-menu",
    }

    options = reactive([])  # type: List[DropdownButton]
    selected = reactive(None)  # type: Optional[DropdownButton]

    def compose(self) -> ComposeResult:
        yield Static("Sort by")

    def watch_selected(self, value: DropdownButton) -> None:
        # do some stuff when the selected option changes
        pass

    def on_click(self, event: Message) -> None:
        log("clicked dropdown")


class DropdownOptions(Grid):
    pass


class SortDropdown(Dropdown):
    options = reactive(
        [
            DropdownButton("None"),
            DropdownButton("Severity"),
            DropdownButton("Date"),
            DropdownButton("Name"),
        ]
    )  # type: List[DropdownButton]

    def compose(self) -> ComposeResult:
        yield DropdownOptions(
            *self.options,
        )

    def on_button_pressed(self, event: DropdownButton.Pressed) -> None:
        if isinstance(event.sender, DropdownButton):
            self.selected = event.sender
            event.stop()


class ArtifactResult(Button):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class FilterPanel(Container):
    filters = reactive([], layout=True)

    def compose(self) -> ComposeResult:
        yield Vertical(
            Horizontal(Static("Filters"), classes="panel-header"),
            Vertical(
                *(
                    FilterField(filter, id=f"filter-field-{name}")
                    for name, filter in FILTERS.items()
                ),
                classes="panel-content",
            ),
            classes="panel-container",
        )


class TitleCount(Static):
    count = reactive(0)

    def render(self) -> str:
        return f"{self.renderable} ({self.count})"

    # def watch_count(self, value: int) -> None:
    #     self.refresh(repaint=True, layout=True)


class ResultPanel(Container):
    report = reactive(None)  # type: ArtifactReport

    def compose(self) -> ComposeResult:
        yield Vertical(
            Horizontal(
                TitleCount("Results"),
                # SortDropdown(id="result-sort"),
                classes="panel-header",
            ),
            self._get_content_container(),
            classes="panel-container",
        )

    def _get_content_container(self) -> Container:
        if self.report is None:
            results = []
        else:
            results = (
                ArtifactResult(a.name_with_digest) for a in self.report.artifacts
            )
        return Vertical(*results, classes="panel-content", id="result-panel-content")

    def watch_report(self, value: ArtifactReport) -> None:
        if value is None or self.report is None:
            return
        old_content = self.query_one("#result-panel-content", Vertical)

        # TODO: this is a hack to clear the panel
        # How to do this properly?

        # Update the list of artifacts
        new_content = self._get_content_container()
        self.query_one(".panel-container", Vertical).mount(new_content)
        old_content.remove()

        # Update the result count
        count = self.query_one(TitleCount)
        count.count = len(self.report.artifacts)
        # count.refresh(repaint=True)  # redundant?


class Title(Static):
    pass


class VulnApp(App):
    report = reactive(None, layout=True)  # type: Optional[ArtifactReport]
    filters = reactive([], layout=True)

    CSS_PATH = "poc.css"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Grid(
            FilterPanel(),
            ResultPanel(),
            classes="main",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        log("button pressed")

    def on_artifact_result_pressed(self, event: ArtifactResult.Pressed) -> None:
        log(f"artifact pressed")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        def get_filter(filter_field: FilterField) -> Optional[FilterField]:
            value = filter_field.query_one(Input).value
            if not value:
                return None
            id = filter_field.id.rsplit("-")[-1]
            if not FILTERS.get(id):
                log(f"Unknown filter {id}")
            return filter_field

        panel = self.query_one(ResultPanel)
        filter_fields = self.query(FilterField)

        # maybe it's overkill to run this in a thread?
        # The refresh of the panel will block for much longer than the filtering
        async def filter_and_refresh(
            self,
            panel: ResultPanel,
            filters: List[FilterField],
        ) -> None:
            def apply_filters(report: ArtifactReport) -> ArtifactReport:
                report = self.report
                for filter_field in filters:
                    value = filter_field.query_one(Input).value
                    report = filter_field.filter.method(report, value)
                return report

            loop = asyncio.get_event_loop()
            report = await loop.run_in_executor(None, apply_filters, filters)
            panel.report = report  # update the report panel
            # self.refresh()

        # Get the filter inputs that have values
        filters = [f for f in map(get_filter, filter_fields) if f]

        asyncio.create_task(filter_and_refresh(self, panel, filters))
        # panel.report = self.report.with_cve(event.value)
        self.refresh()

    async def on_mount(self) -> None:
        asyncio.create_task(self.fetch_artifacts())

    async def fetch_artifacts(self) -> None:
        artifacts = await get_artifacts()
        self.report = ArtifactReport(artifacts)
        self.query_one(ResultPanel).report = self.report
        self.refresh(layout=True)


app = VulnApp()
app.run()
