import json
import zipfile
import io
import base64
import xml.etree.ElementTree as ET

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import CrewMember, Passenger
from .services import strip_numeric_suffix


def parse_ndjson_response(response):
    """Разбирает NDJSON-поток ответа в список событий (для тестов)."""
    raw = b"".join(response.streaming_content).decode("utf-8")
    events = [json.loads(line) for line in raw.splitlines() if line.strip()]
    return events


def get_result_event(events):
    result = [e for e in events if e["type"] == "result"]
    assert result, "В потоке не найдено событие 'result'"
    return result[0]


def make_crew_manifest(sap_number=11805, position="FO", last_name="ФАТИ", first_name="ВИРДЖИЛ ИВАНОВИЧ"):
    return {
        "flights": [
            {
                "crew": [
                    {
                        "id": sap_number,
                        "position": position,
                        "lastName": last_name,
                        "firstName": first_name,
                        "email": "V.FATI@AEROFLOT.RU",
                        "metadata": [
                            {
                                "name": "crewEnhancedData",
                                "payload": json.dumps({
                                    "crewCard": [
                                        {
                                            "sectionInfoLines": [
                                                {"name": "Фамилия Имя Отчество", "payload": f"{last_name} {first_name}"},
                                                {"name": "LastName, FirstName", "payload": f"{first_name.split()[0]} {last_name}"},
                                                {"name": "Фамилия И.О. проверяющего", "payload": "Петров А.Б"},
                                            ]
                                        }
                                    ]
                                }, ensure_ascii=False),
                            }
                        ],
                    }
                ]
            }
        ]
    }


def make_pax_booking(document_number="1234567890"):
    return {
        "data": [
            {
                "bookingName": {
                    "firstName": "IVAN",
                    "lastName": "PETROV",
                    "bookingSegment": {
                        "document": {
                            "documentNumber": document_number,
                            "birthDate": "1990-01-01",
                            "expiryDate": "2030-01-01T00:00:00",
                            "firstName": "IVAN",
                            "lastName": "PETROV",
                        }
                    },
                }
            }
        ]
    }


def make_pax_register(document_number="1234567890", pnr="ABCDEF"):
    return {
        "data": {
            "passengers": [
                {
                    "passengerNameRecord": pnr,
                    "personType": "Adult",
                    "firstName": "IVAN",
                    "middleName": "IVANOVICH",
                    "lastName": "PETROV",
                    "document": {
                        "number": document_number,
                        "birthDate": "1990-01-01",
                        "expirationDate": "2030-01-01T00:00:00",
                        "firstName": "IVAN",
                        "lastName": "PETROV",
                    },
                    "checkInPassengerRemarks": [
                        {"specialServiceRequestCode": "PCTC", "freeTextDescription": "PCTC /79991234567"},
                    ],
                }
            ]
        }
    }


def make_purser_report_xml():
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<report>'
        '<formElement><fieldName>cc-name</fieldName><fieldValue>ИВАНОВ ИВАН ИВАНОВИЧ</fieldValue></formElement>'
        '<formElement><fieldName>service_notes_1</fieldName><fieldValue>Обслуживание прошло без замечаний по факту.</fieldValue></formElement>'
        '</report>'
    ).encode("utf-8")


class AccessControlTests(TestCase):
    """Раздел должен быть доступен только авторизованным пользователям."""

    def test_index_requires_login(self):
        response = self.client.get(reverse('anonimaeroflot:anonimaeroflot'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_process_requires_login(self):
        response = self.client.post(reverse('anonimaeroflot:process_files'))
        self.assertEqual(response.status_code, 302)


class NumericSuffixTests(TestCase):
    """
    Пользователь может приложить файл с хвостовым числовым суффиксом,
    например crew_123456.json.32423 — суффикс должен убираться, а файл
    всё равно обрабатываться по своему настоящему типу.
    """

    def test_strip_numeric_suffix(self):
        self.assertEqual(strip_numeric_suffix("crew_123456.json.32423"), "crew_123456.json")
        self.assertEqual(strip_numeric_suffix("Purser_Report_123.xml.987"), "Purser_Report_123.xml")
        self.assertEqual(strip_numeric_suffix("pax_1_booking.json"), "pax_1_booking.json")
        self.assertEqual(strip_numeric_suffix("no_suffix_file.json"), "no_suffix_file.json")


class ProcessFilesTests(TestCase):
    """Проверка основного сценария: загрузка -> обезличивание -> NDJSON-поток -> ZIP."""

    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass12345")
        self.client.login(username="tester", password="pass12345")

    def test_index_accessible_when_logged_in(self):
        response = self.client.get(reverse('anonimaeroflot:anonimaeroflot'))
        self.assertEqual(response.status_code, 200)

    def test_process_crew_manifest(self):
        content = json.dumps(make_crew_manifest(sap_number=11805)).encode("utf-8")
        f = SimpleUploadedFile("crew_11805.json", content, content_type="application/json")

        response = self.client.post(reverse('anonimaeroflot:process_files'), {"files": [f]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/x-ndjson')

        events = parse_ndjson_response(response)
        log_messages = [e["message"] for e in events if e["type"] == "log"]
        self.assertTrue(any("Обработка файла: crew_11805.json" in m for m in log_messages))
        self.assertTrue(any("Обработка завершена: обработано" in m for m in log_messages))
        self.assertTrue(any(" | INFO | " in m for m in log_messages))

        self.assertTrue(CrewMember.objects.filter(sap_number=11805).exists())
        member = CrewMember.objects.get(sap_number=11805)

        result = get_result_event(events)
        zip_bytes = base64.b64decode(result["zip_base64"])
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            self.assertIn("crew_11805.json", zf.namelist())
            data = json.loads(zf.read("crew_11805.json").decode("utf-8"))
            crew = data["flights"][0]["crew"][0]
            self.assertNotEqual(crew["lastName"], "ФАТИ")
            self.assertEqual(crew["lastName"], member.last_name)
            # FO/CPT — почта в манифесте не подменяется фейковой (как в прототипе)
            self.assertEqual(crew["email"], "V.FATI@AEROFLOT.RU")

    def test_crew_manifest_reuses_existing_fake_data(self):
        content = json.dumps(make_crew_manifest(sap_number=22222)).encode("utf-8")
        f1 = SimpleUploadedFile("crew_22222.json", content, content_type="application/json")
        response1 = self.client.post(reverse('anonimaeroflot:process_files'), {"files": [f1]})
        parse_ndjson_response(response1)  # дочитываем поток, иначе generator не отработает
        member_first = CrewMember.objects.get(sap_number=22222)

        f2 = SimpleUploadedFile("crew_22222.json", content, content_type="application/json")
        response2 = self.client.post(reverse('anonimaeroflot:process_files'), {"files": [f2]})
        parse_ndjson_response(response2)
        member_second = CrewMember.objects.get(sap_number=22222)

        self.assertEqual(member_first.full_name, member_second.full_name)
        self.assertEqual(CrewMember.objects.filter(sap_number=22222).count(), 1)

    def test_process_pax_booking(self):
        content = json.dumps(make_pax_booking(document_number="9988776655")).encode("utf-8")
        f = SimpleUploadedFile("pax_1_booking.json", content, content_type="application/json")

        response = self.client.post(reverse('anonimaeroflot:process_files'), {"files": [f]})
        events = parse_ndjson_response(response)
        result = get_result_event(events)

        self.assertEqual(result["summary"]["processed"], 1)
        self.assertTrue(Passenger.objects.filter(document_number="9988776655").exists())

        zip_bytes = base64.b64decode(result["zip_base64"])
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            data = json.loads(zf.read("pax_1_booking.json").decode("utf-8"))
            document = data["data"][0]["bookingName"]["bookingSegment"]["document"]
            self.assertNotEqual(document["documentNumber"], "9988776655")
            self.assertNotIn("PETROV", json.dumps(data))

    def test_process_pax_register(self):
        content = json.dumps(make_pax_register(document_number="1112223334")).encode("utf-8")
        f = SimpleUploadedFile("pax_1_register.json", content, content_type="application/json")

        response = self.client.post(reverse('anonimaeroflot:process_files'), {"files": [f]})
        events = parse_ndjson_response(response)
        result = get_result_event(events)

        self.assertEqual(result["summary"]["processed"], 1)
        self.assertTrue(Passenger.objects.filter(document_number="1112223334").exists())

        zip_bytes = base64.b64decode(result["zip_base64"])
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            data = json.loads(zf.read("pax_1_register.json").decode("utf-8"))
            passenger = data["data"]["passengers"][0]
            self.assertNotEqual(passenger["lastName"], "PETROV")
            remark = passenger["checkInPassengerRemarks"][0]
            self.assertTrue(remark["freeTextDescription"].startswith("PCTC /79"))

    def test_pax_without_document_number_gets_ephemeral_identity(self):
        booking = make_pax_booking()
        booking["data"][0]["bookingName"]["bookingSegment"]["document"]["documentNumber"] = ""
        content = json.dumps(booking).encode("utf-8")
        f = SimpleUploadedFile("pax_1_booking.json", content, content_type="application/json")

        response = self.client.post(reverse('anonimaeroflot:process_files'), {"files": [f]})
        events = parse_ndjson_response(response)
        result = get_result_event(events)

        self.assertEqual(result["summary"]["processed"], 1)
        self.assertEqual(Passenger.objects.count(), 0)

    def test_process_purser_report(self):
        content = make_purser_report_xml()
        f = SimpleUploadedFile("Purser_Report_11805.xml", content, content_type="application/xml")

        response = self.client.post(reverse('anonimaeroflot:process_files'), {"files": [f]})
        events = parse_ndjson_response(response)
        result = get_result_event(events)

        self.assertEqual(result["summary"]["processed"], 1)

        zip_bytes = base64.b64decode(result["zip_base64"])
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            self.assertIn("Purser_Report_11805.xml", zf.namelist())
            xml_bytes = zf.read("Purser_Report_11805.xml")
            root = ET.fromstring(xml_bytes)
            values = [el.text for el in root.findall(".//fieldValue")]
            self.assertNotIn("ИВАНОВ ИВАН ИВАНОВИЧ", values)
            self.assertNotIn("Обслуживание прошло без замечаний по факту.", values)
            # Никакая обработка отчёта СБ не должна создавать записи в БД
            self.assertEqual(CrewMember.objects.count(), 0)

    def test_log_messages_are_not_duplicated_per_request(self):
        """
        StreamCaptureHandler подключается к общему логгеру на время запроса
        и должен отключаться после него — иначе сообщения одного запроса
        начнут дублироваться в следующих (или утечь между параллельными
        запросами, если хендлеры не убираются).
        """
        f1 = SimpleUploadedFile("random1.json", b"{}", content_type="application/json")
        response1 = self.client.post(reverse('anonimaeroflot:process_files'), {"files": [f1]})
        events1 = parse_ndjson_response(response1)
        messages1 = [e["message"] for e in events1 if e["type"] == "log"]

        f2 = SimpleUploadedFile("random2.json", b"{}", content_type="application/json")
        response2 = self.client.post(reverse('anonimaeroflot:process_files'), {"files": [f2]})
        events2 = parse_ndjson_response(response2)
        messages2 = [e["message"] for e in events2 if e["type"] == "log"]

        self.assertTrue(any("random1.json" in m for m in messages1))
        self.assertFalse(any("random1.json" in m for m in messages2))
        self.assertTrue(any("random2.json" in m for m in messages2))

        from .logger import AeroflotLogger, StreamCaptureHandler
        remaining = [h for h in AeroflotLogger.get_logger().handlers if isinstance(h, StreamCaptureHandler)]
        self.assertEqual(remaining, [])

    def test_crew_manifest_with_trailing_numeric_suffix_is_processed(self):
        content = json.dumps(make_crew_manifest(sap_number=33333)).encode("utf-8")
        f = SimpleUploadedFile("crew_33333.json.998", content, content_type="application/json")

        response = self.client.post(reverse('anonimaeroflot:process_files'), {"files": [f]})
        events = parse_ndjson_response(response)
        result = get_result_event(events)

        self.assertEqual(result["summary"]["processed"], 1)
        self.assertEqual(result["summary"]["skipped"], 0)

        zip_bytes = base64.b64decode(result["zip_base64"])
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            self.assertIn("crew_33333.json", zf.namelist())
            self.assertNotIn("crew_33333.json.998", zf.namelist())

    def test_unknown_filename_format_is_skipped(self):
        f = SimpleUploadedFile("random.json", b"{}", content_type="application/json")
        response = self.client.post(reverse('anonimaeroflot:process_files'), {"files": [f]})
        events = parse_ndjson_response(response)
        result = get_result_event(events)

        self.assertEqual(result["summary"]["processed"], 0)
        self.assertEqual(result["summary"]["skipped"], 1)

    def test_invalid_json_is_skipped(self):
        f = SimpleUploadedFile("crew_1.json", b"{broken", content_type="application/json")
        response = self.client.post(reverse('anonimaeroflot:process_files'), {"files": [f]})
        events = parse_ndjson_response(response)
        result = get_result_event(events)

        self.assertEqual(result["summary"]["skipped"], 1)

    def test_invalid_xml_is_skipped(self):
        f = SimpleUploadedFile("Purser_Report_1.xml", b"<broken", content_type="application/xml")
        response = self.client.post(reverse('anonimaeroflot:process_files'), {"files": [f]})
        events = parse_ndjson_response(response)
        result = get_result_event(events)

        self.assertEqual(result["summary"]["skipped"], 1)

    def test_disallowed_extension_rejected(self):
        f = SimpleUploadedFile("data.txt", b"hello", content_type="text/plain")
        response = self.client.post(reverse('anonimaeroflot:process_files'), {"files": [f]})
        self.assertEqual(response.status_code, 400)

    def test_no_files_rejected(self):
        response = self.client.post(reverse('anonimaeroflot:process_files'), {})
        self.assertEqual(response.status_code, 400)

    def test_get_not_allowed_on_process(self):
        response = self.client.get(reverse('anonimaeroflot:process_files'))
        self.assertEqual(response.status_code, 405)


class StreamCaptureHandlerTests(TestCase):
    """
    Проверка самого механизма перехвата логов (logger.py), в отрыве от
    HTTP-слоя: сообщения, которые реально уходят в logger.info(...),
    должны попадать в callback в том же формате "дата | уровень | текст",
    что уходит в консоль и файл логов.
    """

    def test_captures_messages_with_timestamp_and_level(self):
        import re
        from .logger import AeroflotLogger, StreamCaptureHandler

        test_logger = AeroflotLogger.get_logger("test_capture_logger")
        messages = []

        with StreamCaptureHandler(test_logger, messages.append):
            test_logger.info("Обработка файла: test.json")
            test_logger.warning("Файл test.json не соответствует формату")

        self.assertEqual(len(messages), 2)

        pattern = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| (INFO|WARNING) \| (.+)$")

        match0 = pattern.match(messages[0])
        self.assertIsNotNone(match0)
        self.assertEqual(match0.group(1), "INFO")
        self.assertEqual(match0.group(2), "Обработка файла: test.json")

        match1 = pattern.match(messages[1])
        self.assertIsNotNone(match1)
        self.assertEqual(match1.group(1), "WARNING")
        self.assertEqual(match1.group(2), "Файл test.json не соответствует формату")

        for m in messages:
            self.assertNotIn("\033[", m)

    def test_handler_removed_after_context(self):
        from .logger import AeroflotLogger, StreamCaptureHandler

        test_logger = AeroflotLogger.get_logger("test_capture_logger_2")
        with StreamCaptureHandler(test_logger, lambda m: None):
            self.assertEqual(
                len([h for h in test_logger.handlers if isinstance(h, StreamCaptureHandler)]), 1
            )

        self.assertEqual(
            len([h for h in test_logger.handlers if isinstance(h, StreamCaptureHandler)]), 0
        )


class TransliterationTests(TestCase):
    def test_transliterate_basic(self):
        from .helpers import transliterate
        self.assertEqual(transliterate("ИВАНОВ"), "IVANOV")
        self.assertEqual(transliterate("щукин"), "SHCHUKIN")


class CrewMemberModelTests(TestCase):
    def test_str_representation(self):
        member = CrewMember.objects.create(
            sap_number=12345,
            full_name="TEST NAME",
        )
        self.assertIn("12345", str(member))
        self.assertIn("TEST NAME", str(member))


class PassengerModelTests(TestCase):
    def test_str_representation(self):
        passenger = Passenger.objects.create(
            document_number="1234567890",
            last_name="TESTOV",
        )
        self.assertIn("1234567890", str(passenger))
        self.assertIn("TESTOV", str(passenger))
