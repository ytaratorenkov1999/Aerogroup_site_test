import csv
import io
import json
import re
import zipfile

from .helpers import Basic, FileFull, FileUpdate
from .logger import CrewLogger, StreamCaptureHandler

logger = CrewLogger.get_logger()

_NUMERIC_SUFFIX_RE = re.compile(r'\.\d+$')


class ProcessingError(Exception):
    """Файл не подошёл по формату/содержимому и не может быть обработан."""


def strip_numeric_suffix(filename: str) -> str:
    return _NUMERIC_SUFFIX_RE.sub('', filename)


def process_crew_manifest_full(file_obj):
    text = file_obj.read().decode("utf-8")
    reader = csv.reader(io.StringIO(text), delimiter="|")
    rows = []

    for line_no, info in enumerate(reader, start=1):
        if not info:
            continue
        try:
            sap_id = int(info[FileFull.SAP_NUMBER])
        except (ValueError, IndexError) as e:
            raise ProcessingError(
                f"Строка {line_no}: некорректный табельный номер ({e})"
            )

        member, _created = Basic.get_or_create_fake_crew_member(sap_id)

        info[FileFull.FULL_NAME] = member.full_name

        if len(info) > FileFull.EMAIL and info[FileFull.EMAIL]:
            info[FileFull.EMAIL] = member.email

        if len(info) > FileFull.PHONE and info[FileFull.PHONE]:
            info[FileFull.PHONE] = member.phone

        rows.append(info)

    output = io.StringIO()
    writer = csv.writer(output, delimiter="|", lineterminator="\r\n")
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def process_crew_manifest_update(file_obj):
    text = file_obj.read().decode("utf-8")
    reader = csv.reader(io.StringIO(text), delimiter="|")
    rows = []

    for line_no, info in enumerate(reader, start=1):
        if not info:
            continue
        try:
            sap_id = int(info[FileUpdate.SAP_NUMBER])
        except (ValueError, IndexError) as e:
            raise ProcessingError(
                f"Строка {line_no}: некорректный табельный номер ({e})"
            )

        member, _created = Basic.get_or_create_fake_crew_member(sap_id)
        info[FileUpdate.FULL_NAME] = member.full_name

        rows.append(info)

    output = io.StringIO()
    writer = csv.writer(output, delimiter="|", lineterminator="\r\n")
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def process_profile_json(file_obj):
    raw = file_obj.read().decode("utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProcessingError(f"Ошибка чтения JSON: {e}")

    if not Basic.check_sap_profile_json(data):
        raise ProcessingError("Нарушение структуры файла (отсутствуют обязательные поля)")

    try:
        sap_id = int(data["EmployeeId"])
    except (ValueError, TypeError) as e:
        raise ProcessingError(f"Некорректный EmployeeId: {e}")

    member, _created = Basic.get_or_create_fake_crew_member(sap_id)

    data["FirstName_EN"] = member.first_name_en
    data["FirstName_RU"] = member.first_name_ru

    return json.dumps(data, ensure_ascii=False, indent=4).encode("utf-8")


def _detect_file_type(filename: str) -> str:
    lower = filename.strip().lower()

    if lower.endswith("crewmanifestfull.csv"):
        return "crew_manifest_full"
    if lower.endswith("crewmanifestupdate.csv"):
        return "crew_manifest_update"
    if lower.startswith("profile__") and lower.endswith(".json"):
        return "profile_json"
    return "unknown"


_PROCESSORS = {
    "crew_manifest_full": process_crew_manifest_full,
    "crew_manifest_update": process_crew_manifest_update,
    "profile_json": process_profile_json,
}


def process_uploaded_files(uploaded_files):

    processed = 0
    skipped = 0

    pending_messages = []
    with StreamCaptureHandler(logger, pending_messages.append):

        def drain():
            """Забирает всё, что успело залогироваться с прошлого drain()."""
            while pending_messages:
                yield {"type": "log", "message": pending_messages.pop(0)}

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for uploaded_file in uploaded_files:
                original_name = uploaded_file.name
                clean_name = strip_numeric_suffix(original_name)

                logger.info(f"Обработка файла: {original_name}")

                file_type = _detect_file_type(clean_name)
                processor = _PROCESSORS.get(file_type)

                if processor is None:
                    logger.warning(f"Файл {original_name} не соответствует ожидаемому формату наименования")
                    skipped += 1
                    yield from drain()
                    continue

                try:
                    result_bytes = processor(uploaded_file)
                    zf.writestr(clean_name, result_bytes)
                    processed += 1
                    logger.info(f"Обработка файла {original_name} завершена")
                except ProcessingError as e:
                    logger.error(f"Файл {original_name} пропущен: {e}")
                    skipped += 1
                except Exception as e:
                    logger.error(f"Ошибка при обработке файла {original_name}: {e}")
                    skipped += 1

                yield from drain()

        logger.info(f"Обработка завершена: обработано {processed}, пропущено {skipped}")
        yield from drain()

    summary = {"processed": processed, "skipped": skipped, "total": len(uploaded_files)}
    yield {"type": "result", "zip_bytes": zip_buffer.getvalue(), "summary": summary}