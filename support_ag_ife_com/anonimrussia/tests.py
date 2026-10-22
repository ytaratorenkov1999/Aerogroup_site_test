import json
import zipfile
import io
import base64

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import CrewMember
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


class AccessControlTests(TestCase):
    """Раздел должен быть доступен только авторизованным пользователям."""

    def test_index_requires_login(self):
        response = self.client.get(reverse('anonimrussia:anonimrussia'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_process_requires_login(self):
        response = self.client.post(reverse('anonimrussia:process_files'))
        self.assertEqual(response.status_code, 302)


class NumericSuffixTests(TestCase):
    """
    Пользователь может приложить файл с хвостовым числовым суффиксом,
    например profile__124601.json.32423 — суффикс должен убираться, а
    файл всё равно обрабатываться по своему настоящему типу.
    """

    def test_strip_numeric_suffix(self):
        self.assertEqual(strip_numeric_suffix("profile__124601.json.32423"), "profile__124601.json")
        self.assertEqual(strip_numeric_suffix("crew__CrewManifestFull.csv"), "crew__CrewManifestFull.csv")
        self.assertEqual(strip_numeric_suffix("crew__CrewManifestFull.csv.987"), "crew__CrewManifestFull.csv")
        self.assertEqual(strip_numeric_suffix("no_suffix_file.csv"), "no_suffix_file.csv")


class ProcessFilesTests(TestCase):
    """Проверка основного сценария: загрузка -> обезличивание -> NDJSON-поток -> ZIP."""

    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass12345")
        self.client.login(username="tester", password="pass12345")

    def test_index_accessible_when_logged_in(self):
        response = self.client.get(reverse('anonimrussia:anonimrussia'))
        self.assertEqual(response.status_code, 200)

    def test_process_crew_manifest_full(self):
        content = (
            b"129385|DMITRIACHKOV KIRILL|CCC|RU|6839||2026-05-07 00:35:00.0|"
            b"2026-05-07 03:45:00.0|KJA|NER|K.DMITRIACHKOV@ROSSIYA-AIRLINES.COM"
            b"||RUSSIA|B738|73187\n"
        )
        f = SimpleUploadedFile("crew__CrewManifestFull.csv", content, content_type="text/csv")

        response = self.client.post(reverse('anonimrussia:process_files'), {"files": [f]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/x-ndjson')

        events = parse_ndjson_response(response)

        # Должны быть логи вида "... | INFO | Обработка файла: ..."
        log_messages = [e["message"] for e in events if e["type"] == "log"]
        self.assertTrue(any("Обработка файла: crew__CrewManifestFull.csv" in m for m in log_messages))
        # Построчного лога по каждому SAP-номеру быть не должно (слишком шумно)
        self.assertFalse(any("SAP " in m for m in log_messages))
        # Финальное сообщение об итогах обработки
        self.assertTrue(any("Обработка завершена: обработано" in m for m in log_messages))
        # Формат должен включать дату и уровень (как в консоли/файле логов)
        self.assertTrue(any(" | INFO | " in m for m in log_messages))

        self.assertTrue(CrewMember.objects.filter(sap_number=129385).exists())

        result = get_result_event(events)
        zip_bytes = base64.b64decode(result["zip_base64"])
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            self.assertIn("crew__CrewManifestFull.csv", zf.namelist())
            processed_line = zf.read("crew__CrewManifestFull.csv").decode("utf-8")
            self.assertNotIn("DMITRIACHKOV KIRILL", processed_line)
            self.assertNotIn("K.DMITRIACHKOV@ROSSIYA-AIRLINES.COM", processed_line)

    def test_log_messages_are_not_duplicated_per_request(self):
        """
        StreamCaptureHandler подключается к общему логгеру на время запроса
        и должен отключаться после него — иначе сообщения одного запроса
        начнут дублироваться в следующих (или утечь между параллельными
        запросами, если хендлеры не убираются).
        """
        f1 = SimpleUploadedFile("random1.csv", b"1|2|3", content_type="text/csv")
        response1 = self.client.post(reverse('anonimrussia:process_files'), {"files": [f1]})
        events1 = parse_ndjson_response(response1)
        messages1 = [e["message"] for e in events1 if e["type"] == "log"]

        f2 = SimpleUploadedFile("random2.csv", b"1|2|3", content_type="text/csv")
        response2 = self.client.post(reverse('anonimrussia:process_files'), {"files": [f2]})
        events2 = parse_ndjson_response(response2)
        messages2 = [e["message"] for e in events2 if e["type"] == "log"]

        # Сообщения о random1.csv не должны просочиться во второй запрос
        self.assertTrue(any("random1.csv" in m for m in messages1))
        self.assertFalse(any("random1.csv" in m for m in messages2))
        self.assertTrue(any("random2.csv" in m for m in messages2))

        # После обоих запросов у логгера не должно остаться висящих
        # StreamCaptureHandler-ов
        from .logger import CrewLogger, StreamCaptureHandler
        remaining = [h for h in CrewLogger.get_logger().handlers if isinstance(h, StreamCaptureHandler)]
        self.assertEqual(remaining, [])

    def test_process_profile_json_uses_existing_fake_data(self):
        csv_content = (
            b"129385|DMITRIACHKOV KIRILL|CCC|RU|6839||2026-05-07 00:35:00.0|"
            b"2026-05-07 03:45:00.0|KJA|NER|K.DMITRIACHKOV@ROSSIYA-AIRLINES.COM"
            b"||RUSSIA|B738|73187\n"
        )
        f_csv = SimpleUploadedFile("crew__CrewManifestFull.csv", csv_content, content_type="text/csv")
        first_response = self.client.post(reverse('anonimrussia:process_files'), {"files": [f_csv]})
        parse_ndjson_response(first_response)  # дочитываем поток до конца
        member = CrewMember.objects.get(sap_number=129385)

        profile = json.dumps({
            "EmployeeId": 129385,
            "FirstName_EN": "KIRILL",
            "FirstName_RU": "КИРИЛЛ",
        }).encode("utf-8")
        f_json = SimpleUploadedFile("profile__129385.json", profile, content_type="application/json")

        response = self.client.post(reverse('anonimrussia:process_files'), {"files": [f_json]})
        events = parse_ndjson_response(response)
        result = get_result_event(events)
        zip_bytes = base64.b64decode(result["zip_base64"])

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            data = json.loads(zf.read("profile__129385.json").decode("utf-8"))
            self.assertEqual(data["FirstName_EN"], member.first_name_en)
            self.assertEqual(data["FirstName_RU"], member.first_name_ru)

    def test_profile_json_with_trailing_numeric_suffix_is_processed(self):
        """
        Файл profile__124601.json.32423 (с "мусорным" числовым хвостом на
        конце имени) должен обрабатываться как обычный profile__*.json.
        """
        profile = json.dumps({
            "EmployeeId": 124601,
            "FirstName_EN": "KIRILL",
            "FirstName_RU": "КИРИЛЛ",
        }).encode("utf-8")
        f = SimpleUploadedFile("profile__124601.json.32423", profile, content_type="application/json")

        response = self.client.post(reverse('anonimrussia:process_files'), {"files": [f]})
        events = parse_ndjson_response(response)
        result = get_result_event(events)

        self.assertEqual(result["summary"]["processed"], 1)
        self.assertEqual(result["summary"]["skipped"], 0)
        self.assertTrue(CrewMember.objects.filter(sap_number=124601).exists())

        zip_bytes = base64.b64decode(result["zip_base64"])
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            # В архиве файл должен лежать уже под очищенным именем
            self.assertIn("profile__124601.json", zf.namelist())
            self.assertNotIn("profile__124601.json.32423", zf.namelist())

    def test_crew_manifest_with_trailing_numeric_suffix_is_processed(self):
        content = (
            b"129385|DMITRIACHKOV KIRILL|CCC|RU|6839||2026-05-07 00:35:00.0|"
            b"2026-05-07 03:45:00.0|KJA|NER|K.DMITRIACHKOV@ROSSIYA-AIRLINES.COM"
            b"||RUSSIA|B738|73187\n"
        )
        f = SimpleUploadedFile(
            "[20260504-T-003135Z]_CrewManifestFull.csv.998", content, content_type="text/csv"
        )

        response = self.client.post(reverse('anonimrussia:process_files'), {"files": [f]})
        events = parse_ndjson_response(response)
        result = get_result_event(events)

        self.assertEqual(result["summary"]["processed"], 1)
        self.assertEqual(result["summary"]["skipped"], 0)

        zip_bytes = base64.b64decode(result["zip_base64"])
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            self.assertIn("[20260504-T-003135Z]_CrewManifestFull.csv", zf.namelist())

    def test_unknown_filename_format_is_skipped(self):
        f = SimpleUploadedFile("random.csv", b"1|2|3", content_type="text/csv")
        response = self.client.post(reverse('anonimrussia:process_files'), {"files": [f]})
        events = parse_ndjson_response(response)
        result = get_result_event(events)

        self.assertEqual(result["summary"]["processed"], 0)
        self.assertEqual(result["summary"]["skipped"], 1)

    def test_invalid_json_is_skipped(self):
        f = SimpleUploadedFile("profile__1.json", b"{broken", content_type="application/json")
        response = self.client.post(reverse('anonimrussia:process_files'), {"files": [f]})
        events = parse_ndjson_response(response)
        result = get_result_event(events)

        self.assertEqual(result["summary"]["skipped"], 1)

    def test_disallowed_extension_rejected(self):
        f = SimpleUploadedFile("data.txt", b"hello", content_type="text/plain")
        response = self.client.post(reverse('anonimrussia:process_files'), {"files": [f]})
        self.assertEqual(response.status_code, 400)

    def test_no_files_rejected(self):
        response = self.client.post(reverse('anonimrussia:process_files'), {})
        self.assertEqual(response.status_code, 400)

    def test_get_not_allowed_on_process(self):
        response = self.client.get(reverse('anonimrussia:process_files'))
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
        from .logger import CrewLogger, StreamCaptureHandler

        test_logger = CrewLogger.get_logger("test_capture_logger")
        messages = []

        with StreamCaptureHandler(test_logger, messages.append):
            test_logger.info("Обработка файла: test.csv")
            test_logger.warning("Файл test.csv не соответствует формату")

        self.assertEqual(len(messages), 2)

        # Формат: "YYYY-MM-DD HH:MM:SS | LEVEL | message"
        pattern = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| (INFO|WARNING) \| (.+)$")

        match0 = pattern.match(messages[0])
        self.assertIsNotNone(match0)
        self.assertEqual(match0.group(1), "INFO")
        self.assertEqual(match0.group(2), "Обработка файла: test.csv")

        match1 = pattern.match(messages[1])
        self.assertIsNotNone(match1)
        self.assertEqual(match1.group(1), "WARNING")
        self.assertEqual(match1.group(2), "Файл test.csv не соответствует формату")

        # Без ANSI-кодов цвета (те есть только в консольном ColorFormatter)
        for m in messages:
            self.assertNotIn("\033[", m)

    def test_handler_removed_after_context(self):
        from .logger import CrewLogger, StreamCaptureHandler

        test_logger = CrewLogger.get_logger("test_capture_logger_2")
        with StreamCaptureHandler(test_logger, lambda m: None):
            self.assertEqual(
                len([h for h in test_logger.handlers if isinstance(h, StreamCaptureHandler)]), 1
            )

        self.assertEqual(
            len([h for h in test_logger.handlers if isinstance(h, StreamCaptureHandler)]), 0
        )


class CrewMemberModelTests(TestCase):
    def test_str_representation(self):
        member = CrewMember.objects.create(
            sap_number=12345,
            full_name="TEST NAME",
        )
        self.assertIn("12345", str(member))
        self.assertIn("TEST NAME", str(member))