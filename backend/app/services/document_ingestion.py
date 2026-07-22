from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import fitz

from app.services.chunker import TextChunker


@dataclass(frozen=True, slots=True)
class ExtractedRecord:
    text: str
    location_type: str
    location_value: str


@dataclass(frozen=True, slots=True)
class PreparedChunk:
    text: str
    source_type: str
    location_type: str
    location_value: str

    def to_payload(self) -> dict:
        return asdict(self)


class DocumentIngestionService:
    """Parse supported files into source-aware embedding chunks."""

    MAX_FILE_BYTES = 10 * 1024 * 1024
    SUPPORTED_EXTENSIONS = {".pdf", ".csv", ".json"}

    def __init__(self) -> None:
        self.chunker = TextChunker()

    def prepare(
        self,
        path: Path,
        original_filename: str,
    ) -> tuple[str, list[PreparedChunk]]:
        extension = Path(original_filename).suffix.lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError("Only PDF, CSV, and JSON files are supported.")

        size = path.stat().st_size
        if size <= 0:
            raise ValueError("The uploaded file is empty.")
        if size > self.MAX_FILE_BYTES:
            raise ValueError("The uploaded file exceeds the 10 MB limit.")

        if extension == ".pdf":
            records = self._extract_pdf(path)
            source_type = "pdf"
        elif extension == ".csv":
            records = self._extract_csv(path)
            source_type = "csv"
        else:
            records = self._extract_json(path)
            source_type = "json"

        chunks: list[PreparedChunk] = []
        for record in records:
            for text in self.chunker.chunk(record.text):
                if text.strip():
                    chunks.append(
                        PreparedChunk(
                            text=text.strip(),
                            source_type=source_type,
                            location_type=record.location_type,
                            location_value=record.location_value,
                        )
                    )

        if not chunks:
            raise ValueError("No readable text was found in the file.")

        return source_type, chunks

    @staticmethod
    def _extract_pdf(path: Path) -> list[ExtractedRecord]:
        try:
            document = fitz.open(path)
        except Exception as exc:
            raise ValueError(f"The PDF could not be opened: {exc}") from exc

        try:
            if document.needs_pass:
                raise ValueError("Password-protected PDFs are not supported.")

            return [
                ExtractedRecord(
                    text=page.get_text("text").strip(),
                    location_type="page",
                    location_value=str(page_number),
                )
                for page_number, page in enumerate(document, start=1)
                if page.get_text("text").strip()
            ]
        finally:
            document.close()

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("The file must use UTF-8 text encoding.") from exc

    def _extract_csv(self, path: Path) -> list[ExtractedRecord]:
        content = self._read_text(path)
        try:
            reader = csv.DictReader(StringIO(content))
            if not reader.fieldnames:
                raise ValueError("The CSV must contain a header row.")

            records = []
            for row_number, row in enumerate(reader, start=2):
                fields = [
                    f"{name}: {str(value).strip()}"
                    for name, value in row.items()
                    if name and value is not None and str(value).strip()
                ]
                if fields:
                    records.append(
                        ExtractedRecord(
                            text="\n".join(fields),
                            location_type="row",
                            location_value=str(row_number),
                        )
                    )
            return records
        except csv.Error as exc:
            raise ValueError(f"The CSV could not be parsed: {exc}") from exc

    def _extract_json(self, path: Path) -> list[ExtractedRecord]:
        try:
            value = json.loads(self._read_text(path))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"The JSON is invalid at line {exc.lineno}, column {exc.colno}."
            ) from exc

        flattened: list[tuple[str, Any]] = []
        self._flatten_json(value, "$", flattened)
        return [
            ExtractedRecord(
                text=f"{json_path}: {self._display_json_value(item)}",
                location_type="json_path",
                location_value=json_path,
            )
            for json_path, item in flattened
            if item is not None and str(item).strip()
        ]

    @classmethod
    def _flatten_json(
        cls,
        value: Any,
        path: str,
        output: list[tuple[str, Any]],
    ) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                cls._flatten_json(child, f"{path}.{key}", output)
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                cls._flatten_json(child, f"{path}[{index}]", output)
            return
        output.append((path, value))

    @staticmethod
    def _display_json_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)
