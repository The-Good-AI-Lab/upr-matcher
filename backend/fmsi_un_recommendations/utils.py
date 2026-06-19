from collections.abc import Iterable
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final
from zipfile import BadZipFile, ZipFile, is_zipfile

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from openai import OpenAI
from pypdf import PdfReader

try:
    from pydantic_ai import Agent
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.output import PromptedOutput
    from pydantic_ai.providers.openrouter import OpenRouterProvider
except ImportError:  # pragma: no cover - handled at runtime
    Agent = None  # type: ignore[assignment]
    OpenAIModel = None  # type: ignore[assignment]
    OpenRouterProvider = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from pydantic_ai.models.openai import OpenAIChatModel as OpenAIChatModelType
else:  # pragma: no cover
    OpenAIChatModelType = Any

from .settings import Settings

settings = Settings()
OLE_COMPOUND_DOCUMENT_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
TARGET_ID_RE = re.compile(r"\b\d{2,3}\.\d{1,3}\b")


def _normalize_cell_text(value: str) -> str:
    return value.strip().replace("\xa0", " ")


def _header_groups(headers: list[str]) -> list[tuple[str, list[int]]]:
    counts: dict[str, int] = {}
    groups: list[tuple[str, list[int], str]] = []
    for index, header in enumerate(headers, start=1):
        base = header or f"Column {index}"
        if groups and groups[-1][2] == base:
            groups[-1][1].append(index - 1)
            continue
        counts[base] = counts.get(base, 0) + 1
        name = base
        if counts[base] > 1:
            name = f"{base} {counts[base]}"
        groups.append((name, [index - 1], base))
    return [(name, indexes) for name, indexes, _ in groups]


def _headers_to_groups(headers: list[str]) -> list[tuple[str, list[int]]]:
    groups: list[tuple[str, list[int]]] = []
    for index, header in enumerate(headers):
        groups.append((header, [index]))
    return groups


def _merge_grouped_cells(cells: list[str], indexes: list[int]) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for index in indexes:
        if index >= len(cells):
            continue
        value = cells[index]
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return "\n\n".join(values)


def _grouped_row_to_dict(cells: list[str], groups: list[tuple[str, list[int]]]) -> dict[str, str]:
    row_data: dict[str, str] = {}
    for header, indexes in groups:
        row_data[header] = _merge_grouped_cells(cells, indexes)
    return row_data


def _fallback_headers(width: int) -> list[str]:
    if width <= 0:
        return []
    return ["Recommendation", *[f"Column {index}" for index in range(2, width + 1)]]


def _is_section_metadata_row(cells: list[str]) -> bool:
    if not cells:
        return False
    first_cell = cells[0].lower()
    return first_cell.startswith("theme") or first_cell.startswith("right or area")


def _has_target_id(cells: list[str]) -> bool:
    return any(TARGET_ID_RE.search(cell) for cell in cells)


def _require_docx_package(path: Path) -> None:
    ext = path.suffix.lower()
    if ext not in {".doc", ".docx"}:
        raise ValueError(f"Unsupported Word document type: {ext}")
    with path.open("rb") as handle:
        if handle.read(len(OLE_COMPOUND_DOCUMENT_MAGIC)) == OLE_COMPOUND_DOCUMENT_MAGIC:
            raise ValueError(
                f"Legacy .doc files are not supported: {path}. Convert the file to .docx before upload."
            )
    if not is_zipfile(path):
        if ext == ".doc":
            raise ValueError(
                f"Legacy .doc files are not supported: {path}. Convert the file to .docx before upload."
            )
        raise ValueError(f"Invalid .docx file: {path} is not a readable WordprocessingML package.")
    try:
        with ZipFile(path) as archive:
            if "word/document.xml" not in archive.namelist():
                raise ValueError(f"Invalid Word document: {path} does not contain word/document.xml.")
    except BadZipFile as exc:
        raise ValueError(f"Invalid Word document: {path} is not a readable zip package.") from exc


def _load_docx_document(path: Path) -> Document:
    _require_docx_package(path)
    return Document(path)


def _require_openrouter_key() -> str:
    if not settings.openrouter_api_key:
        raise ValueError(
            "OPENROUTER_API_KEY is not set. Please export it in your environment before running this command."
        )
    return settings.openrouter_api_key


def get_openrouter_client() -> OpenAI:
    # Resilience: the OpenAI SDK retries transient transport errors, 429, and 5xx
    # with exponential backoff. Default max_retries is 2; raise it and bound the
    # per-request time so a hung connection fails fast and is retried instead of
    # crashing the job. Covers both chat (extraction) and embeddings.
    return OpenAI(
        base_url=settings.agent_base_url,
        api_key=_require_openrouter_key(),
        max_retries=5,
        timeout=120.0,
    )


_chat_model: OpenAIChatModelType | None = None


def prompt_openrouter(prompt: str) -> str:
    client = get_openrouter_client()
    response = client.chat.completions.create(model=settings.model, messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content


def message_openrouter(messages: list[dict]) -> str:
    client = get_openrouter_client()
    response = client.chat.completions.create(model=settings.model, messages=messages)
    return response.choices[0].message.content


def chat_with_openrouter(system_prompt: str, user_prompt: str) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": [{"type": "text", "text": user_prompt}]},
    ]
    return message_openrouter(messages)


def _get_chat_model() -> OpenAIChatModelType:
    if OpenAIChatModel is None or Agent is None or OpenRouterProvider is None:
        raise ImportError(
            "pydantic-ai is required for structured outputs. Install it or run `uv sync` to fetch dependencies."
        )
    global _chat_model
    if _chat_model is None:
        provider = OpenRouterProvider(api_key=_require_openrouter_key())
        _chat_model = OpenAIChatModel(settings.model, provider=provider)
    return _chat_model


def structured_chat_openrouter(system_prompt: str, user_prompt: str, response_format: type[Any]) -> Any:
    agent = Agent(
        model=_get_chat_model(),
        system_prompt=system_prompt,
    )
    result = agent.run_sync(user_prompt, output_type=PromptedOutput(response_format))
    return result.output


def _table_to_rows(table: Table) -> Iterable[str]:
    # Assuming the first row contains headers
    headers = [_normalize_cell_text(cell.text) for cell in table.rows[0].cells]
    for row in table.rows[1:]:
        cells = [_normalize_cell_text(cell.text) for cell in row.cells]
        if len(cells) != len(headers):
            continue
        yield "\n\n".join(f"{headers[i]}\n{cells[i]}" for i in range(len(headers)))


def _table_to_text(table: Table) -> str:
    return "\n\n".join(_table_to_rows(table))


def _table_to_json(table: Table) -> list[dict]:
    json_data: list[dict[str, str]] = []
    current_theme: dict[str, str] = {}

    table_rows = list(table.rows)
    first_content_index = next(
        (
            index
            for index, row in enumerate(table_rows)
            if any(_normalize_cell_text(cell.text) for cell in row.cells)
        ),
        None,
    )
    if first_content_index is None:
        return json_data

    first_cells = [_normalize_cell_text(cell.text) for cell in table_rows[first_content_index].cells]
    if _is_section_metadata_row(first_cells) or _has_target_id(first_cells):
        groups = _headers_to_groups(_fallback_headers(len(first_cells)))
        data_rows = table_rows[first_content_index:]
    else:
        groups = _header_groups(first_cells)
        data_rows = table_rows[first_content_index + 1 :]

    for row in data_rows:
        cells = [_normalize_cell_text(cell.text) for cell in row.cells]
        # Theme rows are section metadata, not recommendations.
        # Example: "Theme: Legal & institutional reform"
        if _is_section_metadata_row(cells):
            cell_text = cells[0]
            if ":" in cell_text:
                key, value = cell_text.split(":", 1)
                current_theme = {key.strip(): value.strip()}
            continue
        if not cells:
            continue
        row_data = _grouped_row_to_dict(cells, groups)
        if not any(value for value in row_data.values()):
            continue
        if current_theme:
            row_data = {**current_theme, **row_data}
        json_data.append(row_data)
    return json_data


def docx_tables_to_json(path: Path | str) -> list[dict[str, str]]:
    document = _load_docx_document(Path(path))
    rows: list[dict[str, str]] = []
    for table in document.tables:
        rows.extend(_table_to_json(table))
    return rows


def _docx_blocks_in_order(doc: Document) -> Iterable[str]:
    # check if the doc has only tables
    if all(el.tag.rsplit("}", 1)[-1] == "tbl" for el in doc.element.body.iterchildren()):
        for table in doc.tables:
            table_text = _table_to_text(table)
            if table_text.strip():
                yield table_text
        return
    # otherwise yield paragraphs and tables in order
    for el in doc.element.body.iterchildren():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph_text = Paragraph(el, doc).text
            if paragraph_text.strip():
                yield paragraph_text
        elif tag == "tbl":
            table_text = _table_to_text(Table(el, doc))
            if table_text.strip():
                yield table_text


def read_text_file(path: Path | str) -> str:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".pdf":
        with p.open("rb") as handle:
            reader: Final = PdfReader(handle)
            return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if ext in {".doc", ".docx"}:
        doc: Final = _load_docx_document(p)
        return "\n\n".join(block.strip() for block in _docx_blocks_in_order(doc) if block.strip())
    if ext in {".txt", ".md"}:
        return p.read_text(encoding="utf-8")
    raise ValueError(f"Unsupported file type: {ext}")
