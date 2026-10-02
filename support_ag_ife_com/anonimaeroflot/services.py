import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile

from .helpers import AeroflotCrew, AeroflotPassengers, AeroflotReport
from .logger import AeroflotLogger, StreamCaptureHandler

logger = AeroflotLogger.get_logger()

_NUMERIC_SUFFIX_RE = re.compile(r'\.\d+$')


class ProcessingError(Exception):
    """Файл не подошёл по формату/содержимому и не может быть обработан."""


def strip_numeric_suffix(filename: str) -> str:
    return _NUMERIC_SUFFIX_RE.sub('', filename)


def process_crew_manifest(file_obj):
    """Обрабатывает crew_*.json — манифест экипажа рейса(ов)."""
    raw = file_obj.read().decode("utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProcessingError(f"Ошибка чтения JSON: {e}")

    for flight in data.get("flights", []):
        for member in flight.get("crew", []):
            try:
                sap_number = int(member["id"])
            except (KeyError, ValueError, TypeError) as e:
                raise ProcessingError(f"Некорректный идентификатор члена экипажа: {e}")

            position = member.get("position")

            crew_member, _created = AeroflotCrew.get_or_create_fake_crew_member(sap_number)

            member["lastName"] = crew_member.last_name
            member["firstName"] = crew_member.first_name
            if position not in ("CPT", "FO"):
                member["email"] = crew_member.email

            full_name_en_parts = (crew_member.full_name_en or "").split()
            if len(full_name_en_parts) >= 2:
                full_name_en_reversed = f"{full_name_en_parts[1]} {full_name_en_parts[0]}"
            else:
                full_name_en_reversed = crew_member.full_name_en or ""

            for meta in member.get("metadata", []):
                if meta.get("name") != "crewEnhancedData":
                    continue

                try:
                    enhanced_data = json.loads(meta["payload"])
                except (KeyError, json.JSONDecodeError):
                    continue

                for card in enhanced_data.get("crewCard", []):
                    for line in card.get("sectionInfoLines", []):
                        line_name = line.get("name", "")

                        if line_name.startswith("Фамилия Имя Отчество"):
                            line["payload"] = crew_member.full_name
                        elif line_name.startswith("LastName, FirstName"):
                            line["payload"] = full_name_en_reversed
                        elif line_name.startswith("Фамилия И.О. проверяющего"):
                            line["payload"] = crew_member.instructor_check

                meta["payload"] = json.dumps(enhanced_data, ensure_ascii=False)

    return json.dumps(data, ensure_ascii=False, indent=4).encode("utf-8")


def _anonymize_booking(data):
    safe_items = []
    for item in data.get("data", []):
        try:
            booking_name = item["bookingName"]
            segment = booking_name["bookingSegment"]
            document = segment["document"]

            real_document_number = document.get("documentNumber")

            if real_document_number:
                fake = AeroflotPassengers.get_or_create_pax_identity(real_document_number)
            else:
                logger.warning(
                    "Пассажир без номера документа — подставляю разовую "
                    "фейковую личность без сохранения в БД"
                )
                fake = AeroflotPassengers.generate_ephemeral_pax_identity()

            first_plus_middle_name = f"{fake['first_name']} {fake['middle_name']}"

            booking_name["firstName"] = first_plus_middle_name
            booking_name["lastName"] = fake["last_name"]

            document["documentNumber"] = fake["document_number"]
            document["birthDate"] = AeroflotPassengers.to_full_iso(fake["birth_date"])
            document["expiryDate"] = fake["expiry_date"]
            document["firstName"] = first_plus_middle_name
            document["lastName"] = fake["last_name"]

            safe_items.append(item)
        except Exception as e:
            logger.error(f"Не удалось обезличить данные пассажира: {e}")
            # Запись о пассажире удаляется из результата
            continue

    data["data"] = safe_items
    return data


def _anonymize_register(data):
    passengers = data.get("data", {}).get("passengers", [])

    identities = {}
    infants_by_pnr = {}
    safe_passengers = []

    for passenger in passengers:
        try:
            document = passenger.setdefault("document", {})
            real_document_number = document.get("number")

            if real_document_number:
                fake = AeroflotPassengers.get_or_create_pax_identity(real_document_number)
            else:
                logger.warning(
                    f"Номер документа отсутствует: {passenger.get('passengerNameRecord')}"
                )
                fake = AeroflotPassengers.generate_ephemeral_pax_identity()

            identities[id(passenger)] = fake
            safe_passengers.append(passenger)

            if passenger.get("personType") == "Infant":
                pnr = passenger.get("passengerNameRecord")
                real_birth_date = document.get("birthDate")
                infants_by_pnr.setdefault(pnr, []).append((real_birth_date, fake))
        except Exception as e:
            logger.error(f"Не удалось обезличить данные пассажира: {e}")
            continue

    for passenger in safe_passengers:
        try:
            fake = identities[id(passenger)]
            first_plus_middle_name = f"{fake['first_name']} {fake['middle_name']}"

            passenger["firstName"] = fake["first_name"]
            passenger["middleName"] = fake["middle_name"]
            passenger["lastName"] = fake["last_name"]

            document = passenger.setdefault("document", {})
            document["number"] = fake["document_number"]
            document["birthDate"] = AeroflotPassengers.to_full_iso(fake["birth_date"])
            document["expirationDate"] = fake["expiry_date"]
            document["firstName"] = first_plus_middle_name
            document["lastName"] = fake["last_name"]

            remarks = passenger.get("checkInPassengerRemarks", [])
            pnr = passenger.get("passengerNameRecord")

            for remark in remarks:
                code = remark.get("specialServiceRequestCode")

                if code == "PCTC":
                    remark["freeTextDescription"] = fake["phone_number"]

                elif code == "CTCM":
                    phone_digits = fake["ctcm_phone_number"].split("/")[-1]
                    remark["freeTextDescription"] = f"CTCM {phone_digits}"

                elif code == "OTHS" and remark.get("freeTextDescription", "").startswith("OTHS HK1 DOCS/"):
                    remark["freeTextDescription"] = AeroflotPassengers.generate_doc_number(fake["document_number"])

                elif code == "CHLD":
                    remark["freeTextDescription"] = f"CHLD HK1 {AeroflotPassengers.format_ssr_date(fake['birth_date'])}"

                elif code == "INFT":
                    text = remark.get("freeTextDescription", "")
                    matched_infant = None

                    for real_birth_date, infant_fake in infants_by_pnr.get(pnr, []):
                        if AeroflotPassengers.format_ssr_date(real_birth_date) in text:
                            matched_infant = infant_fake
                            break

                    if matched_infant:
                        infant_birthday_ssr = AeroflotPassengers.format_ssr_date(matched_infant["birth_date"])
                        remark["freeTextDescription"] = (
                            f"INFT HK1 {infant_birthday_ssr} "
                            f"{matched_infant['last_name']}/{matched_infant['first_name']} {matched_infant['middle_name']}"
                        )
                    else:
                        infant_first_name = AeroflotPassengers.generate_first_name()
                        infant_last_name = AeroflotPassengers.generate_last_name()
                        infant_middle_name = AeroflotPassengers.generate_middle_name()
                        infant_birthday_ssr = AeroflotPassengers.generate_infant_birthday_format_ssr()
                        remark["freeTextDescription"] = (
                            f"INFT HK1 {infant_birthday_ssr} "
                            f"{infant_last_name}/{infant_first_name} {infant_middle_name}"
                        )
        except Exception as e:
            logger.error(f"Не удалось обработать ремарки пассажира, ремарки очищены: {e}")
            passenger["checkInPassengerRemarks"] = []
            continue

    data["data"]["passengers"] = safe_passengers
    return data


def process_pax_booking(file_obj):
    """Обрабатывает pax_*booking.json — данные бронирования пассажиров."""
    raw = file_obj.read().decode("utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProcessingError(f"Ошибка чтения JSON: {e}")

    data = _anonymize_booking(data)
    return json.dumps(data, ensure_ascii=False, indent=4).encode("utf-8")


def process_pax_register(file_obj):
    """Обрабатывает pax_*register.json — данные регистрации пассажиров."""
    raw = file_obj.read().decode("utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProcessingError(f"Ошибка чтения JSON: {e}")

    data = _anonymize_register(data)
    return json.dumps(data, ensure_ascii=False, indent=4).encode("utf-8")


def process_purser_report(file_obj):
    """Обрабатывает Purser_Report*.xml — отчёт старшего бортпроводника."""
    raw = file_obj.read()
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise ProcessingError(f"Ошибка чтения XML: {e}")

    names_replaced = AeroflotReport.anonymize_tree(root)
    logger.info(f"  Заменено ФИО: {names_replaced} чел.")

    output = io.BytesIO()
    ET.ElementTree(root).write(output, encoding="UTF-8", xml_declaration=True)
    return output.getvalue()


def _detect_file_type(filename: str) -> str:
    lower = filename.strip().lower()

    if lower.startswith("crew_") and lower.endswith(".json"):
        return "crew_manifest"
    if lower.startswith("pax_") and lower.endswith("booking.json"):
        return "pax_booking"
    if lower.startswith("pax_") and lower.endswith("register.json"):
        return "pax_register"
    if lower.startswith("purser_report") and lower.endswith(".xml"):
        return "purser_report"
    return "unknown"


_PROCESSORS = {
    "crew_manifest": process_crew_manifest,
    "pax_booking": process_pax_booking,
    "pax_register": process_pax_register,
    "purser_report": process_purser_report,
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
