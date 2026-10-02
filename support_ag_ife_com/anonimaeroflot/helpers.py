"""Вспомогательный файл для обработки и генерации фейковых данных Аэрофлота.

Перенесено из прототипа (helpers.py). Классы-генераторы (AeroflotCrew,
AeroflotPassengers, AeroflotReport) — без изменений по своей сути (чистая
генерация случайных значений). Работа с БД адаптирована: вместо чтения/записи
файлов на диске и обращения к SQLite (BdCrew, BdPax) используется Django ORM
(CrewMember, Passenger), т.к. файлы теперь приходят через веб-форму, а не
лежат в папке на диске.

Перевод ФИО на английский язык (translate_to_english в прототипе, через
Google Translate) заменён на транслитерацию, чтобы не делать сетевые запросы
в процессе обработки веб-запроса.
"""

import calendar
import random
import re
from datetime import datetime, timedelta
from typing import ClassVar

from .logger import AeroflotLogger

_TRANSLIT_MAP = {
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "E",
    "Ж": "ZH", "З": "Z", "И": "I", "Й": "Y", "К": "K", "Л": "L", "М": "M",
    "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T", "У": "U",
    "Ф": "F", "Х": "KH", "Ц": "TS", "Ч": "CH", "Ш": "SH", "Щ": "SHCH",
    "Ъ": "", "Ы": "Y", "Ь": "", "Э": "E", "Ю": "YU", "Я": "YA",
}


def transliterate(text: str) -> str:
    """Транслитерация кириллического текста латиницей (только заглавные буквы
    и пробелы, этого достаточно для ФИО в верхнем регистре)."""
    return "".join(_TRANSLIT_MAP.get(ch, ch) for ch in text.upper())


class AeroflotCrew:
    """Класс для генерации фейковых данных для обработки файлов экипажа"""

    @staticmethod
    def generate_instructors():
        """Возвращает случайную фамилию проверяющего"""
        list_instructors = [
            "Иванов В.А", "Иванов А.П", "Иванов М.И", "Иванов Д.С", "Иванов Е.Н",
            "Иванов П.В", "Иванов С.М", "Иванов К.Д", "Иванов О.Г", "Иванов Н.Л",
            "Иванов И.И", "Иванов Р.В", "Иванов Т.П", "Иванов Ф.А", "Иванов Ю.Е",
            "Иванов Г.С", "Иванов В.Б", "Иванов А.К", "Иванов Л.В", "Иванов Е.М",
            "Иванов П.А", "Иванов С.И", "Иванов Д.В", "Иванов К.П", "Иванов М.С",
            "Иванов О.В", "Иванов Н.А", "Иванов Р.С", "Иванов Т.В", "Иванов Ю.И"
        ]
        return random.choice(list_instructors)

    @staticmethod
    def generate_last_name():
        """Возвращает случайную фамилию ЧКЭ"""
        return random.choice([
            "МЕССИ", "РОНАЛДО", "МБАППЕ", "ХОЛАНД", "БЕНЗЕМА", "МОДРИЧ",
            "ДЕ БРЮЙНЕ", "САЛАХ", "МАНЕ", "СТЕРЛИНГ", "АЛЕКСАНДР-АРНОЛЬД",
            "ВАН ДАЙК", "БЕККЕР", "СИЛЬВА", "НОЙЕР", "АЛЬКАНТАРА", "МОУРИНЬО",
            "ГВАРДИОЛА", "КЛОПП", "АНЧЕЛОТТИ", "ПЕПЕ", "РАМОС", "ВАРАН",
            "МЕНДИ", "УОКЕР", "СТОУНЗ", "ДИАШ", "КАНСЕЛУ", "РОДРИГО",
            "БЕЙЛ", "МОДРИЧ", "КРООС", "КАЗЕМИРО", "ВАЛЬВЕРДЕ", "КАМАВИНГА",
            "ЧУАМЕНИ", "МИЛИТАН", "АЛАБА", "ДЭВИС", "КИММИХ", "ГОРЕТЦКА",
            "МЮЛЛЕР", "ЛЕВАНДОВСКИ", "СУАРЕС", "КАВАНИ", "ФАЛЬКАО", "ХАМЕС",
            "РОДРИГЕС", "КУАДРАДО", "КЬЕЗА", "БОНУЧЧИ", "КЬЕЛЛИНИ", "БУФФОН",
            "ДОННАРУММА", "ВЕРРАТТИ", "МАРКИНЬОС", "ХАКИМИ", "ЗИЕШ", "МАЗРАУИ",
            "ГНАБРИ", "КОМАН", "САНЕ", "МУСИАЛА", "ЭРНАНДЕС", "УПАМЕКАНО",
            "ПАВАР", "КУНДЕ", "АРАУХО", "ПЕДРИ", "ГАВИ", "ФАТИ"
        ])

    @staticmethod
    def generate_first_name():
        """Функция генерации имени ЧКЭ"""
        return random.choice([
            "ЛИОНЕЛЬ", "КРИСТИАНО", "НЕЙМАР", "КИЛИАН", "ЭРЛИНГ", "КАРИМ",
            "ЛУКА", "ВИНИСИУС", "МОХАМЕД", "КЕВИН", "ЛУИС", "АНДРЕЙ",
            "РОБЕРТ", "АНТУАН", "САДИО", "ЛЕРОЙ", "ТРЕНТ", "ВИРДЖИЛ",
            "АЛИССОН", "ЭДЕР", "ФЕРНАНДО", "МАНУЭЛЬ", "ТИАГО", "ХОСЕ",
            "ПАУЛО", "МАРК", "ДЭВИД", "СЕРХИО", "РАФАЭЛЬ", "РИЯД",
            "КАЛИДУ", "АШРАФ", "ДЖАМАЛ", "ПЕДРИ", "ГАВИ", "РОНАЛДО",
            "ЗИНЕДИН", "РИВАЛДО", "РОНАЛДИНЬО", "КАКА", "БЕКХЭМ", "ДЖЕРАРД",
            "ФРЭНК", "РАУЛЬ", "АЛЕССАНДРО", "ФАБИО", "ПАОЛО", "АНДРЕС",
            "ХАВИ", "ФИЛИПП", "КОУТИНЬО", "ГАРЕТ", "ЛУКА", "ТОНИ",
            "ДЖОШУА", "ЛЕОН", "СЕРЖ", "КИНГСЛИ", "АЛЬФОНСО", "МЭЙСОН",
            "ДЕКЛАН", "ДЖЕК", "РАХИМ"
        ])

    @staticmethod
    def generate_middle_name():
        """Функция генерации отчества ЧКЭ"""
        return random.choice([
            "ИВАНОВИЧ", "ПЕТРОВИЧ", "АЛЕКСАНДРОВИЧ", "ВЛАДИМИРОВИЧ", "СЕРГЕЕВИЧ", "АНДРЕЕВИЧ",
            "МИХАЙЛОВИЧ", "АЛЕКСЕЕВИЧ", "ДМИТРИЕВИЧ", "НИКОЛАЕВИЧ", "ВИКТОРОВИЧ", "ОЛЕГОВИЧ",
            "ЕВГЕНЬЕВИЧ", "ПАВЛОВИЧ", "РОМАНОВИЧ", "КОНСТАНТИНОВИЧ", "АРТЕМОВИЧ", "МАКСИМОВИЧ",
            "СТЕПАНОВИЧ", "ВАСИЛЬЕВИЧ", "ГРИГОРЬЕВИЧ", "БОРИСОВИЧ", "ФЕДОРОВИЧ", "ЮРЬЕВИЧ",
            "АНАТОЛЬЕВИЧ", "ВЯЧЕСЛАВОВИЧ", "ИЛЬИЧ", "ЛЕОНИДОВИЧ", "МАТВЕЕВИЧ", "ДЕНИСОВИЧ",
            "ТИМОФЕЕВИЧ", "МИРОНОВИЧ", "КИРИЛЛОВИЧ", "ГЛЕБОВИЧ", "ВАЛЕРЬЕВИЧ", "РУСЛАНОВИЧ",
            "СТАНИСЛАВОВИЧ", "ЕГОРОВИЧ", "ВСЕВОЛОДОВИЧ", "ПЛАТОНОВИЧ", "СВЯТОСЛАВОВИЧ", "ЯРОСЛАВОВИЧ",
            "ВИТАЛЬЕВИЧ", "АРСЕНЬЕВИЧ", "БОГДАНОВИЧ", "ЕЛИСЕЕВИЧ", "ВЛАДИСЛАВОВИЧ", "ГЕННАДЬЕВИЧ",
            "ЭДУАРДОВИЧ", "АРТУРОВИЧ", "ДАВИДОВИЧ", "ИВАНОВИЧ", "СЕРГЕЕВИЧ", "АЛЕКСАНДРОВИЧ",
            "ПЕТРОВИЧ", "АНДРЕЕВИЧ", "МИХАЙЛОВИЧ", "ДМИТРИЕВИЧ", "АЛЕКСЕЕВИЧ", "ВЛАДИМИРОВИЧ",
            "НИКОЛАЕВИЧ", "ВИКТОРОВИЧ"
        ])

    @staticmethod
    def translate_to_english(text: str) -> str:
        """Транслитерация ФИО для экипажа (замена вызова внешнего переводчика
        из прототипа — без сетевых запросов в потоке обработки запроса)."""
        return transliterate(text)

    @staticmethod
    def generate_email(first_name, last_name):
        """Функция генерации почтового адреса"""
        return f"{first_name[0]}{last_name}@aeroflot.ru"

    @staticmethod
    def generate_fake_info():
        """Функция генерации фейковых данных для ЧКЭ который не существует в БД"""
        logger = AeroflotLogger.get_logger()
        try:
            last_name = AeroflotCrew.generate_last_name().title()
            middle_name = AeroflotCrew.generate_middle_name().title()
            first_name = f"{AeroflotCrew.generate_first_name().title()} {middle_name}"
            full_name = f"{last_name} {first_name}"

            full_name_en_parts = AeroflotCrew.translate_to_english(
                f"{first_name.split()[0]} {last_name}"
            )
            en_first, en_last = full_name_en_parts.split()[0], full_name_en_parts.split()[1]
            full_name_en = f"{en_first} {en_last}"
            email = AeroflotCrew.generate_email(en_first, en_last)
            instructors = AeroflotCrew.generate_instructors()

            return last_name, first_name, full_name, full_name_en, email, instructors
        except Exception as e:
            logger.error(f"При генерации фейковых данных ЧКЭ возникла ошибка: {e}")
            raise

    @staticmethod
    def get_or_create_fake_crew_member(sap_number: int):

        from .models import CrewMember

        logger = AeroflotLogger.get_logger()
        try:
            member = CrewMember.objects.filter(sap_number=sap_number).first()
            if member is not None:
                return member, False

            last_name, first_name, full_name, full_name_en, email, instructor_check = (
                AeroflotCrew.generate_fake_info()
            )
            member = CrewMember.objects.create(
                sap_number=sap_number,
                first_name=first_name,
                last_name=last_name,
                full_name=full_name,
                full_name_en=full_name_en,
                email=email,
                instructor_check=instructor_check,
            )
            return member, True
        except Exception as e:
            logger.error(f"При получении/сохранении данных ЧКЭ {sap_number} возникла ошибка: {e}")
            raise


class AeroflotPassengers:
    """Класс для генерации фейковых данных по пассажирам"""

    lst_first_name = [
        "LIONEL", "CRISTIANO", "NEYMAR", "KYLIAN", "ERLING", "ROBERT",
        "KEVIN", "VIRGIL", "SADIO", "MOHAMED", "HARRY", "JUDE",
        "VINICIUS", "PEDRI", "GAVI", "JAMAL", "FLORIAN", "BUKAYO",
        "PHIL", "DECLAN", "RODRI", "CASEMIRO", "LUKA", "TONI",
        "JOSHUA", "ALPHONSO", "ACHRAF", "JOAO", "KYLE", "TRENT",
        "ANDREW", "RUBEN", "EDER", "DAVID", "MATS", "GIANLUIGI",
        "ALISSON", "THIBAUT", "MANUEL", "EDERSON", "MARCUS", "RAHEEM",
        "JACK", "OLLIE", "ALEXANDER", "VICTOR", "KHVICHA", "RAFAEL",
        "DARWIN", "JULIAN", "ANTOINE", "PAULO", "DIOGO", "BRUNO",
        "BERNARDO", "RIYAD", "RIYADH", "WILFRIED", "ZLATAN", "GARETH",
        "EDEN", "N'GOLO", "PAUL", "KAI", "THOMAS", "MASON",
        "JAMES", "CHRISTIAN", "SON", "HEUNGMIN"
    ]

    lst_last_name = [
        "MESSI", "RONALDO", "NEYMAR", "MBAPPE", "HAALAND", "LEWANDOWSKI",
        "DEBRUYNE", "VANDIJK", "MANE", "SALAH", "KANE", "BELLINGHAM",
        "VINICIUS", "PEDRI", "GAVI", "MUSIALA", "WIRTZ", "SAKA",
        "FODEN", "RICE", "RODRI", "CASEMIRO", "MODRIC", "KROOS",
        "KIMMICH", "DAVIES", "HAKIMI", "CANCELO", "WALKER", "ARNOLD",
        "ROBERTSON", "DIAS", "MILITAO", "ALABA", "HUMMELS", "DONNARUMMA",
        "BECKER", "COURTOIS", "NEUER", "EDERSON", "RASHFORD", "STERLING",
        "GREALISH", "WATKINS", "ISAK", "OSIMHEN", "KAVARATSKHELIA", "LEAO",
        "NUNEZ", "ALVAREZ", "GRIEZMANN", "DYBALA", "JOTA", "FERNANDES",
        "SILVA", "MAHREZ", "RAHEEM", "ZAHA", "IBRAHIMOVIC", "BALE",
        "HAZARD", "KANTE", "POGBA", "HAVERTZ", "MULLER", "MOUNT",
        "MADDISON", "ERIKSEN", "HEUNGMIN", "HWANG"
    ]

    lst_middle_name = [
        "JAMES", "MICHAEL", "WILLIAM", "ROBERT", "JOHN", "DAVID",
        "RICHARD", "THOMAS", "CHARLES", "CHRISTOPHER", "DANIEL", "MATTHEW",
        "ANTHONY", "MARK", "DONALD", "STEVEN", "PAUL", "ANDREW",
        "JOSHUA", "KENNETH", "KEVIN", "BRIAN", "TIMOTHY", "RONALD",
        "EDWARD", "JASON", "JEFFREY", "RYAN", "JACOB", "GARY",
        "NICHOLAS", "ERIC", "JONATHAN", "STEPHEN", "LARRY", "JUSTIN",
        "SCOTT", "BRANDON", "BENJAMIN", "SAMUEL", "GREGORY", "FRANK",
        "ALEXANDER", "RAYMOND", "PATRICK", "JACK", "DENNIS", "JERRY",
        "TYLER", "AARON", "JOSE", "NATHAN", "ADAM", "HENRY",
        "ZACHARY", "TRISTAN", "DAMIAN", "COLIN", "OWEN", "LIAM",
        "NOAH", "MASON", "LOGAN", "OLIVER", "ELIJAH", "SEBASTIAN",
        "GABRIEL", "JULIAN", "DOMINIC", "VINCENT"
    ]

    @staticmethod
    def generate_document_number():
        """Генерация случайных чисел для номера документа"""
        return ''.join([str(random.randint(1, 10)) for _ in range(10)])

    @staticmethod
    def generate_expiration_data():
        """Генерация даты истечения срока документа"""
        year = random.randint(2000, 2080)
        month = random.randint(1, 12)

        day = random.randint(1, calendar.monthrange(year, month)[1])
        return f"{year}-{month:02d}-{day:02d}T00:00:00"

    @staticmethod
    def generate_phone_number():
        """Для строк PCTC - specialServiceRequestCode"""
        return f"PCTC /79{''.join(str(random.randint(0, 9)) for _ in range(9))}"

    @staticmethod
    def generate_doc_number(doc_number):
        """Возвращает готовую строку с specialServiceRequestCode"""
        return f"OTHS HK1 DOCS/{doc_number}/P"

    @staticmethod
    def generate_first_name():
        """Возвращает случайное имя"""
        return random.choice(AeroflotPassengers.lst_first_name)

    @staticmethod
    def generate_last_name():
        """Возвращает случайную Фамилию"""
        return random.choice(AeroflotPassengers.lst_last_name)

    @staticmethod
    def generate_middle_name():
        """Возвращает случайное отчество"""
        return random.choice(AeroflotPassengers.lst_middle_name)

    @staticmethod
    def generate_birthday_date():
        """Функция генерации дня рождения"""
        start_date = datetime(1945, 1, 1)
        end_date = datetime.now()

        delta = end_date - start_date
        random_days = random.randint(0, delta.days)

        random_date = start_date + timedelta(days=random_days)
        return random_date.strftime('%Y-%m-%d')

    @staticmethod
    def generate_infant_birthday_format_ssr():
        """Возвращает строку даты рождения инфанта в виде 01OCT24"""
        months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
        current_year = datetime.now().year
        min_year = current_year - 2

        year = random.randint(min_year, current_year)

        month_days = [31, 29 if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0) else 28,
                      31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        month = random.randint(1, 12)
        day = random.randint(1, month_days[month - 1])

        return f"{day:02d}{months[month - 1]}{year % 100:02d}"

    @staticmethod
    def generate_fake_pax():
        """Функция генерации фейковых значений для пассажира"""
        logger = AeroflotLogger.get_logger()
        try:
            first_name = AeroflotPassengers.generate_first_name()
            middle_name = AeroflotPassengers.generate_middle_name()
            last_name = AeroflotPassengers.generate_last_name()
            fake_document_number = AeroflotPassengers.generate_document_number()
            birth_date = AeroflotPassengers.generate_birthday_date()
            expiry_date = AeroflotPassengers.generate_expiration_data()
            phone_number = AeroflotPassengers.generate_phone_number()
            ctcm_phone_number = AeroflotPassengers.generate_phone_number()

            return {
                "first_name": first_name,
                "middle_name": middle_name,
                "last_name": last_name,
                "document_number": fake_document_number,
                "birth_date": birth_date,
                "expiry_date": expiry_date,
                "phone_number": phone_number,
                "ctcm_phone_number": ctcm_phone_number,
            }
        except Exception as e:
            logger.error(f"Возникла ошибка при генерации фейковых значений пассажира: {e}")
            raise

    @staticmethod
    def _pax_to_dict(passenger) -> dict:
        return {
            "first_name": passenger.first_name,
            "middle_name": passenger.middle_name,
            "last_name": passenger.last_name,
            "document_number": passenger.fake_document_number,
            "birth_date": passenger.birth_date,
            "expiry_date": passenger.expiry_date,
            "phone_number": passenger.phone_number,
            "ctcm_phone_number": passenger.ctcm_phone_number,
        }

    @staticmethod
    def get_or_create_pax_identity(document_number: str) -> dict:
        """
        Возвращает фейковую личность пассажира из БД, либо генерирует новую
        и сохраняет её.

        Замена связки BdPax.document_exists/get_*/add_document/set_* из
        прототипа — одна операция через ORM вместо пачки SQLite-запросов.
        """
        from .models import Passenger

        logger = AeroflotLogger.get_logger()
        try:
            passenger = Passenger.objects.filter(document_number=document_number).first()
            if passenger is not None:
                return AeroflotPassengers._pax_to_dict(passenger)

            fake = AeroflotPassengers.generate_fake_pax()
            passenger = Passenger.objects.create(
                document_number=document_number,
                fake_document_number=fake["document_number"],
                first_name=fake["first_name"],
                middle_name=fake["middle_name"],
                last_name=fake["last_name"],
                birth_date=fake["birth_date"],
                expiry_date=fake["expiry_date"],
                phone_number=fake["phone_number"],
                ctcm_phone_number=fake["ctcm_phone_number"],
            )
            return AeroflotPassengers._pax_to_dict(passenger)
        except Exception as e:
            logger.error(f"При получении/сохранении данных пассажира {document_number} возникла ошибка: {e}")
            raise

    @staticmethod
    def generate_ephemeral_pax_identity() -> dict:
        """Возвращает разовую фейковую личность пассажира без сохранения в БД"""
        return AeroflotPassengers.generate_fake_pax()

    @staticmethod
    def format_ssr_date(date_str):
        try:
            dt = datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            return date_str
        return dt.strftime('%d%b%y').upper()

    @staticmethod
    def to_full_iso(date_str):
        if date_str and 'T' not in date_str:
            return f"{date_str}T00:00:00"
        return date_str


class AeroflotReport:
    """Класс для генерации фейковой информации в отчете Старшего бортпроводника.

    ФИО обезличиваются "на лету" в пределах одного файла (свой кэш
    real -> fake, без сохранения в БД) — как и в прототипе."""

    lst_with_service_notes: ClassVar[list[str]] = [
        "Обслуживание прошло в штатном режиме.",
        "Питание. Недовольство пассажира",
        "Торговля пользовалась спросом  в экономическом классе, больше всего интересовала услуга Sky Cafe. Сумма выручки составила 3700₽",
    ]

    lst_with_medical_comments: ClassVar[list[str]] = [
        "Медицинская помощь оказана согласно инструкции.",
        "Не оказывалась",
        "Была предоставлена таблетка от головной боли пассажиру 571C",
        "Пассажир жаловался на боль в животе. Справился самостоятельно походом в туалет в хвостовой части самолета",
    ]

    lst_with_aviation_security_comments: ClassVar[list[str]] = [
        "Нарушений авиационной безопасности не выявлено.",
        "В кармане кресла 9А найден розовый powerbank с шнуром. Передано представителю.",
        "Без нарушений",
        "1F паспорт РФ. Передан сотруднику ЛУВД SVO по акту."
    ]

    lst_with_service_comments: ClassVar[list[str]] = [
        "Замечания к сервису отсутствуют.",
        "В Шереметьево было загружено 4 порции питания класса Бизнес, в а/п Волгограда довезли 3 порции, которые отличались.",
        "2й рацион, на 36м ряду закончился выбор горячего из двух, закончились блины, предлагали кашу, принесены извинения, без претензий.",
        "Загруженное количество пледов недостаточно для всех желающих, принесены извинения, в салонах поддерживалась комфортная температура.",
        "После 4 часов полета закончилось шампанское, белое вино, красное российское. Принесены извинения, предлагали альтернативные напитки.",
        "Торговля: 650р. Не пользовалась спросом, много пассажиров с детьми."
        "Температура в салонах ВС регулировалась по просьбам пассажиров всоответствии со стандартами ак. Жалоб не поступало. При опросе степениудовлетворенности пассажиры благодарили за чудесный полет и прекрасное обслуживание.Жалоб и замечаний не поступало.По прилете в SVO ВС досмотрен- все АСЖ на борту, неисправности не обнаружены."
    ]

    lst_with_notes_and_comments: ClassVar[list[str]] = [
        "Дополнительных комментариев нет.",
        "В соответствии с перечнем мест для отдыха при выполнении рейса, для ЧКЭ должны быть заблокированы кресла в последнем ряду. Кресла заблокированы не были, в связи с чем ЧКЭ не предоставлялся отдых. Необходимо принять меры.",
    ]

    lst_with_transport_comment: ClassVar[list[str]] = [
        "Во время встречи-размещения пассажирка обратилась к ЧКЭ с жалобой на то, что при регистрации на рейс им выдали посадочные места, отличные от заранее оплаченных. Пассажирам принесли извинения и посоветовали обратиться на горячую линию. После завершения посадки все пассажиры были размещены совместно и остались довольны.",
        "инструктаж проведён БП 1R, от услуги сопровождения отказ.",
    ]

    lst_with_equipment_failure_comments: ClassVar[list[str]] = [
        "Пассажирам принесены извинения, предложено пересесть, отказались, путешествовали семьёй. При опросе степени удовлетворённости рейсом пассажиры остались довольны.",
        "Пульт управления системой развлечения не работает. Пассажиру принесены извинения, предложено пересесть, отказался, т.к. путешествовал с семьёй.",
        "В полёте выявлено, что замок сервисной дверцы под раковиной прикручен неполностью, нуждается в регулировке. Сделана запись в ACLB. Доклад КВС.",
        "23В: 2DF Отсутствует световая дорожка. После выхода пассажиров 16.00 ВС был досмотрен на предмет неисправностей, было обнаружено отсутствие части световой дорожки в районе кресел 2DF. Был сделан докладКВС, агент, ИТП, направлено ОТГ."
    ]

    fake_names: ClassVar[list[str]] = [
        "Арнольд Шварценеггер Робертович", "Сильвестр Сталлоне Джозефович", "Джеки Чан Константинович",
        "Брюс Ли Виллисович", "Чак Норрис Фёдорович", "Джим Керри Юджинович", "Уилл Смит Кристоферович",
        "Том Круз Мэплеторович", "Киану Ривз Чарльзович", "Джонни Депп Кристофорович", "Леонардо Ди Каприо Вильгельмович",
        "Брэд Питт Уильямович", "Роберт Де Ниро Энтониевич", "Аль Пачино Альфредович", "Морган Фримен Портерович",
        "Дензел Вашингтон Хейзович", "Рассел Кроу Айратович", "Хью Джекман Майклович", "Джейсон Стэйтем Майклович",
        "Дуэйн Джонсон Дугласович", "Мадонна Луиза Верониковна", "Бейонсе Жизель Максимовна", "Шакира Исабель Робертовна",
        "Дженнифер Лопес Линдоновна", "Анджелина Джоли Воуговна", "Эмма Уотсон Шарлоттовна", "Скарлетт Йоханссон Ингридовна",
        "Кира Найтли Кристиновна", "Натали Портман Хершлаговна", "Энн Хэтэуэй Жаклиновна", "Мила Йовович Богдановна",
        "Чарлиз Терон Хендриковна", "Гвинет Пэлтроу Кейтовна", "Кейт Уинслет Элизабетовна", "Кейт Бланшетт Морицовна",
        "Николь Кидман Урсуловна", "Джулия Робертс Эриковна", "Сандра Буллок Мэтьюзовна",
        "Кэмерон Диас Чарльзовна", "Дрю Бэрримор Джоновна",
    ]

    # Поля ФИО: точное совпадение имени поля или наличие одного из суффиксов в имени поля
    NAME_FIELDS: ClassVar[set[str]] = {"cc-name"}
    NAME_SUFFIXES: ClassVar[tuple[str, ...]] = ("_full_name", "-name_")

    # Соответствие префикса поля ("<prefix>_N") методу-генератору заглушки
    COMMENT_GENERATORS: ClassVar[dict[str, str]] = {
        "service_notes": "generate_service_notes",
        "medical_help_comment": "generate_medical_notes",
        "aviation_security_comment": "generate_aviation_security_notes",
        "service_comment": "generate_service_comments",
        "notes_and_comments_comment": "generate_notes_and_comment_comments",
        "organization_of_transportation_comment": "generate_transport_comment",
        "equipment_failures_comment": "generate_equipment_failure_comments",
    }

    @staticmethod
    def generate_service_notes() -> str:
        """Функция генерация случайного коммента по замечаниям сервиса"""
        return random.choice(AeroflotReport.lst_with_service_notes)

    @staticmethod
    def generate_medical_notes() -> str:
        """Функция генерация случайного коммента по замечаниям сервиса"""
        return random.choice(AeroflotReport.lst_with_medical_comments)

    @staticmethod
    def generate_aviation_security_notes() -> str:
        """Функция генерация случайного коммента по замечаниям сервиса"""
        return random.choice(AeroflotReport.lst_with_aviation_security_comments)

    @staticmethod
    def generate_service_comments() -> str:
        """Функция генерация случайного коммента по замечаниям сервиса"""
        return random.choice(AeroflotReport.lst_with_service_comments)

    @staticmethod
    def generate_notes_and_comment_comments() -> str:
        """Функция генерация случайного коммента по замечаниям сервиса"""
        return random.choice(AeroflotReport.lst_with_notes_and_comments)

    @staticmethod
    def generate_transport_comment() -> str:
        """Функция генерации случайного коммента по организации перевозки"""
        return random.choice(AeroflotReport.lst_with_transport_comment)

    @staticmethod
    def generate_equipment_failure_comments() -> str:
        """Функция генерация случайного коммента по замечаниям сервиса"""
        return random.choice(AeroflotReport.lst_with_equipment_failure_comments)

    @staticmethod
    def generate_random_name() -> str:
        """Функция генерации имен для ЧКЭ"""
        return random.choice(AeroflotReport.fake_names)

    @classmethod
    def get_comment_stub(cls, field_name: str) -> str | None:
        """Возвращает случайную заглушку-комментарий, если field_name соответствует
        одному из известных префиксов вида '<prefix>_N', иначе None."""
        for prefix, method_name in cls.COMMENT_GENERATORS.items():
            if re.fullmatch(rf"{re.escape(prefix)}_\d+", field_name):
                generator = getattr(cls, method_name)
                return generator()
        return None

    @classmethod
    def is_name_field(cls, field_name: str) -> bool:
        """Проверяет, является ли поле полем ФИО."""
        return field_name in cls.NAME_FIELDS or any(
            sfx in field_name for sfx in cls.NAME_SUFFIXES
        )

    @classmethod
    def anonymize_tree(cls, root) -> int:
        """Обезличивает разобранное XML-дерево отчёта: заменяет ФИО на случайные
        псевдонимы (один и тот же кэш псевдонимов действует в пределах одного
        файла) и подставляет случайные заглушки в заполненные комментарийные
        поля. Возвращает количество уникальных обезличенных ФИО. Изменяет root
        на месте."""
        logger = AeroflotLogger.get_logger()

        real_to_fake: dict[str, str] = {}
        fake_index = 0

        def get_fake_name(real_name: str) -> str:
            nonlocal fake_index
            if real_name not in real_to_fake:
                real_to_fake[real_name] = cls.fake_names[fake_index % len(cls.fake_names)]
                fake_index += 1
            return real_to_fake[real_name]

        for elem in root.findall(".//formElement"):
            field_name = elem.findtext("fieldName", "")
            field_value_el = elem.find("fieldValue")

            if field_value_el is None:
                continue

            value = (field_value_el.text or "").strip()
            if not value:
                continue  # пустое — не трогаем

            if cls.is_name_field(field_name):
                field_value_el.text = get_fake_name(value)
                logger.debug(f"  ФИО '{field_name}': заменено на псевдоним")
                continue

            comment_stub = cls.get_comment_stub(field_name)
            if comment_stub:
                field_value_el.text = comment_stub
                logger.debug(f"  Комментарий '{field_name}' заменён заглушкой")

        return len(real_to_fake)
