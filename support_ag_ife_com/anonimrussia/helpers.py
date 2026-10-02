"""Вспомогательный файл для обработки и генерации фейковых данных АК Россия.

Перенесено из прототипа (helpers.py). Класс Russia — без изменений (чистая
генерация случайных значений). Класс Basic адаптирован: вместо чтения/записи
файлов на диске и обращения к SQLite (BdRussia) он работает с Django ORM
(CrewMember) и с данными в памяти, т.к. файлы теперь приходят через веб-форму,
а не лежат в папке на диске.
"""

import random

from .logger import CrewLogger


class FileFull:
    """129385|DMITRIACHKOV KIRILL|CCC|RU|6839||2026-05-07 00:35:00.0|2026-05-07 03:45:00.0|KJA|NER|K.DMITRIACHKOV@ROSSIYA-AIRLINES.COM||RUSSIA|B738|73187"""
    SAP_NUMBER = 0  # Табельный номер
    FULL_NAME = 1  # ФИО
    JOB_TITLE = 2  # Должность
    LANGUAGE = 3  # Знание языков
    FLIGHT_NUMBER = 4  # Номер рейса
    EMPTY_FIELD = 5  # Пустое поле
    DATE_DEPARTURE = 6  # Дата вылета
    DATE_ARRIVAL = 7  # Дата прилета
    AIRPORT_DEPARTURE = 8  # Аэропорт вылета
    AIRPORT_ARRIVAL = 9  # Аэропорт прилета
    EMAIL = 10  # Почтовый адрес
    PHONE = 11  # Номер телефона
    NATIONALITY = 12  # Гражданство
    TYPE_AIRCRAFT = 13  # Тип ВС
    REG_NUMBER = 14  # Регистрационный номер


class FileUpdate:
    """6086|2026-05-08 17:00:00.0|LED|SVO|125267|BARSUKOV NIKITA|CO|DELETE"""
    FLIGHT_NUMBER = 0  # Номер рейса
    DATE_DEPARTURE = 1  # Дата вылета
    AIRPORT_DEPARTURE = 2  # Аэропорт вылета
    AIRPORT_ARRIVAL = 3  # Аэропорт прилета
    SAP_NUMBER = 4  # Табельный номер
    FULL_NAME = 5  # ФИО
    JOB_TITLE = 6  # Должность
    UPDATE_ACTION = 7  # Признак удаления


class Russia:
    @staticmethod
    def generate_email(name, surname):
        """Функция генерации почты ЧКЭ"""
        return f"{name[0]}.{surname}@ROSSIYA-AIRLINES.COM"

    @staticmethod
    def generate_phone():
        """Функция генерации номера телефона ЧКЭ"""
        return "7" + ''.join([str(random.randint(0, 9)) for i in range(10)])

    @staticmethod
    def generate_name_ru_en():
        """Функция генерации имени на двух языках"""
        return random.choice([
            ("LIONEL", "ЛИОНЕЛЬ"), ("CRISTIANO", "КРИСТИАНО"), ("NEYMAR", "НЕЙМАР"), ("KYLIAN", "КИЛИАН"),
            ("ERLING", "ЭРЛИНГ"), ("KARIM", "КАРИМ"), ("LUCA", "ЛУКА"), ("VINICIUS", "ВИНИСИУС"),
            ("MOHAMED", "МОХАМЕД"), ("KEVIN", "КЕВИН"), ("LUIS", "ЛУИС"), ("ANDREY", "АНДРЕЙ"),
            ("ROBERT", "РОБЕРТ"), ("ANTOINE", "АНТУАН"), ("SADIO", "САДИО"), ("LEROY", "ЛЕРОЙ"),
            ("TRENT", "ТРЕНТ"), ("VIRGIL", "ВИРДЖИЛ"), ("ALISSON", "АЛИССОН"), ("EDER", "ЭДЕР"),
            ("FERNANDO", "ФЕРНАНДО"), ("MANUEL", "МАНУЭЛЬ"), ("THIAGO", "ТИАГО"), ("JOSE", "ХОСЕ"),
            ("PAULO", "ПАУЛО"), ("MARC", "МАРК"), ("DAVID", "ДЭВИД"), ("SERGIO", "СЕРХИО"),
            ("RAFAEL", "РАФАЭЛЬ"), ("RIYAD", "РИЯД"), ("KALIDOU", "КАЛИДУ"), ("ACHRAF", "АШРАФ"),
            ("JAMAL", "ДЖАМАЛ"), ("PEDRI", "ПЕДРИ"), ("GAVI", "ГАВИ"), ("RONALDO", "РОНАЛДО"),
            ("ZINEDINE", "ЗИНЕДИН"), ("RIVALDO", "РИВАЛДО"), ("RONALDINHO", "РОНАЛДИНЬО"), ("KAKA", "КАКА"),
            ("BECKHAM", "БЕКХЭМ"), ("GERARD", "ДЖЕРАРД"), ("FRANK", "ФРЭНК"), ("RAUL", "РАУЛЬ"),
            ("ALESSANDRO", "АЛЕССАНДРО"), ("FABIO", "ФАБИО"), ("PAOLO", "ПАОЛО"), ("ANDRES", "АНДРЕС"),
            ("XAVI", "ХАВИ"), ("PHILIPPE", "ФИЛИПП"), ("COUTINHO", "КОУТИНЬО"), ("GARETH", "ГАРЕТ"),
            ("LUKA", "ЛУКА"), ("TONI", "ТОНИ"), ("KROOS", "КРООС"), ("JOSHUA", "ДЖОШУА"),
            ("KIMMICH", "КИММИХ"), ("LEON", "ЛЕОН"), ("GORETZKA", "ГОРЕЦКА"), ("SERGE", "СЕРЖ"),
            ("GNABRY", "ГНАБРИ"), ("KINGSLEY", "КИНГСЛИ"), ("COMAN", "КОМАН"), ("ALPHONSO", "АЛЬФОНСО"),
            ("DAVIES", "ДЭВИС"), ("MASON", "МЭЙСОН"), ("MOUNT", "МАУНТ"), ("DECLAN", "ДЕКЛАН"),
            ("RICE", "РАЙС"), ("JACK", "ДЖЕК"), ("GREALISH", "ГРИЛИШ"), ("RAHEEM", "РАХИМ"),
            ("STERLING", "СТЕРЛИНГ")
        ])

    @staticmethod
    def generate_second_name():
        """Функция генерации фамилии ЧКЭ"""
        return random.choice([
            "MESSI", "RONALDO", "MBAPPE", "HAALAND", "BENZEMA", "MODRIC",
            "DEBRUYNE", "SALAH", "MANE", "STERLING", "ALEXANDERARNOLD",
            "VANDIJK", "BECKER", "SILVA", "NEUER", "ALCANTARA", "MOURINHO",
            "GUARDIOLA", "KLOPP", "ANCELOTTI", "PEPE", "RAMOS", "VARANE",
            "MENDY", "WALKER", "STONES", "DIAS", "CANCELO", "RODRIGO",
            "BALE", "MODRIC", "KROOS", "CASEMIRO", "VALVERDE", "CAMAVINGA",
            "TCHOUAMENI", "MILITAO", "ALABA", "DAVIES", "KIMMICH", "GORETZKA",
            "MUELLER", "LEWANDOWSKI", "SUAREZ", "CAVANI", "FALCAO", "JAMES",
            "RODRIGUEZ", "CUADRADO", "CHIESA", "BONUCCI", "CHIELLINI", "BUFFON",
            "DONNARUMMA", "VERRATTI", "MARQUINHOS", "HAKIMI", "ZIEYECH", "MAZRAOUI",
            "GNABRY", "COMAN", "SANE", "MUSIALA", "HERNANDEZ", "UPAMECANO",
            "PAVARD", "KOUNDE", "ARAUJO", "PEDRI", "GAVI", "FATI"
        ])


class Basic:
    """Класс для обработки данных файлов манифеста и профилей.

    В отличие от прототипа не читает/пишет файлы с диска и не обращается к
    SQLite напрямую — вместо BdRussia используется Django ORM (CrewMember),
    а результат обработки собирается в памяти и возвращается вызывающему
    коду (services.py), который упаковывает всё в ZIP.
    """

    @staticmethod
    def generate_fake_info(sap_number: int):
        """Функция генерации фейковых данных для ЧКЭ который не существует в БД"""
        logger = CrewLogger.get_logger()
        try:
            FIRST_NAME_EN, FIRST_NAME_RU = Russia.generate_name_ru_en()  # Генерация имен на русском и английском
            SECOND_NAME = Russia.generate_second_name()  # Генерация фамилии
            FULLNAME = f"{SECOND_NAME} {FIRST_NAME_EN}"  # Генерация полного ФИО
            EMAIL = Russia.generate_email(FIRST_NAME_EN, SECOND_NAME)  # Генерация почтового адреса
            PHONE = Russia.generate_phone()  # Генерация номер телефона

            return FIRST_NAME_RU, FIRST_NAME_EN, SECOND_NAME, FULLNAME, EMAIL, PHONE

        except Exception as e:
            logger.error(f"При генерации фейковых данных возникла ошибка: {e}")
            raise

    @staticmethod
    def get_or_create_fake_crew_member(sap_number: int):
        """
        Возвращает CrewMember с фейковыми данными для sap_number.

        Если запись уже есть в БД (Postgres, ранее сгенерирована) — берёт её.
        Если нет — генерирует новые фейковые данные и сохраняет.

        Замена связки BdRussia.id_exists/get_*/add_sap_number/set_* из
        прототипа: там это было 2-8 отдельных SQLite-запросов, здесь —
        одна операция через ORM.
        """
        from .models import CrewMember

        logger = CrewLogger.get_logger()
        try:
            member = CrewMember.objects.filter(sap_number=sap_number).first()
            if member is not None:
                return member, False

            first_name_ru, first_name_en, second_name, fullname, email, phone = (
                Basic.generate_fake_info(sap_number)
            )
            member = CrewMember.objects.create(
                sap_number=sap_number,
                first_name_ru=first_name_ru,
                first_name_en=first_name_en,
                second_name=second_name,
                full_name=fullname,
                email=email,
                phone=phone,
            )
            return member, True
        except Exception as e:
            logger.error(f"При получении/сохранении данных ЧКЭ {sap_number} возникла ошибка: {e}")
            raise

    @staticmethod
    def check_sap_profile_json(data: dict) -> bool:
        """Проверяет наличие обязательных полей в JSON-профиле"""
        logger = CrewLogger.get_logger()
        required_fields = ("EmployeeId", "FirstName_EN", "FirstName_RU")

        missing = [field for field in required_fields if field not in data]

        if missing:
            logger.error(f"В профиле отсутствуют поля: {', '.join(missing)}")
            return False

        return True