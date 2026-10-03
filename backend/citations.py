"""Exact transcript quotations with centrally maintained subject-area metadata."""

import json
from pathlib import Path


def load_subject_areas(path: Path) -> dict:
    areas = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(areas, list) or not areas:
        raise ValueError("Fachbereichsliste fehlt oder ist leer.")
    by_module, numbers = {}, set()
    for area in areas:
        number, name, modules = area["number"], area["name"], area["modules"]
        if type(number) is not int or number < 1 or number in numbers:
            raise ValueError("Ungültige oder doppelte Fachbereichsnummer.")
        if not isinstance(name, str) or not name.strip() or not isinstance(modules, list) or not modules:
            raise ValueError("Fachbereich benötigt einen Namen und Module.")
        numbers.add(number)
        for module in modules:
            if type(module) is not int or module < 1 or module in by_module:
                raise ValueError("Ungültige oder doppelte Modulzuordnung.")
            by_module[module] = {
                "subject_area_number": str(number),
                "subject_area_name": name.strip(),
            }
    missing = set(range(1, 45)) - set(by_module)
    if missing:
        raise ValueError(f"Fachbereich fehlt für Module: {sorted(missing)}")
    return by_module


SUBJECT_AREAS = load_subject_areas(Path(__file__).with_name("subject_areas.json"))


def subject_area(module_number) -> dict:
    # Only exact numeric module IDs are mapped, never names or model guesses.
    value = str(module_number).strip()
    key = int(value) if value.isascii() and value.isdigit() else None
    return dict(SUBJECT_AREAS.get(key, {
        "subject_area_number": "",
        "subject_area_name": "Nicht zugeordnet",
    }))


def citation_from_chunk(chunk: dict) -> dict:
    text = chunk["text"].strip()
    return {
        **subject_area(chunk.get("module_number", "")),
        **{key: chunk.get(key, "") for key in (
            "module_number", "module_name", "video_number", "video_name",
            "filename", "time_range",
        )},
        "text": text,
        # Backwards-compatible preview; the source dialog uses full `text`.
        "text_preview": text[:300],
    }


def format_citation_source(citation: dict) -> str:
    number = citation["subject_area_number"]
    area = f"Fachbereich {number}" if number else "Fachbereich"
    return (
        f"{area} - {citation['subject_area_name']} | "
        f"Modul {citation['module_number']} - {citation['module_name']} | "
        f"Video {citation['video_number']} - {citation['video_name']} | "
        f"{citation['time_range']}"
    )
