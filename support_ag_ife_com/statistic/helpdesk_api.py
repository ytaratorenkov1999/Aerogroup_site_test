import logging
import requests
from decouple import config
from datetime import datetime

logger = logging.getLogger('statistic')

months = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
          'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']


class HelpdeskError(Exception):
    """Базовое исключение HelpDesk"""

class HelpdeskTimeoutError(HelpdeskError):
    pass

class HelpdeskConnectionError(HelpdeskError):
    pass

class HelpdeskHTTPError(HelpdeskError):
    def __init__(self, status_code, url, body=""):
        self.status_code = status_code
        self.url = url
        self.body = body
        super().__init__(f"HTTP {status_code} от {url}")

class HelpdeskParseError(HelpdeskError):
    pass


HELPDESK_DATE_FORMAT = '%d.%m.%Y %H:%M'


def parse_admins():
    return [name.strip() for name in config('ADMINS').split(',') if name.strip()]


def parse_helpdesk_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, HELPDESK_DATE_FORMAT)
    except (ValueError, TypeError):
        return None


def first_answer_minutes(ticket):
    created = parse_helpdesk_date(ticket.get('Date'))
    started = parse_helpdesk_date(ticket.get('fStartTime'))
    if not created or not started:
        return None
    diff = (started - created).total_seconds() / 60
    return diff if diff > 0 else None


class Helpdesk:

    def __init__(self, period=None):
        self.login_helpdesk = config('HELPDESK_LOGIN')
        self.period = period or datetime.now().strftime("%Y-%m")
        self.validate_period()
        self.password_helpdesk = config('HELPDESK_PASSWORD')
        timestamp = self.period
        self.base_url_afl = f"{config('BASE_HELPDESK_AFL_URL')}?timestamp={timestamp}"
        self.base_url_akr = f"{config('BASE_HELPDESK_AKR_URL')}?timestamp={timestamp}"
        self.admins = parse_admins()


    def validate_period(self):
        try:
            period_date = datetime.strptime(self.period, "%Y-%m")
        except ValueError:
            raise ValueError(f"Неверный формат периода: '{self.period}'. Ожидается YYYY-MM")

        now = datetime.now()
        if (period_date.year, period_date.month) > (now.year, now.month):
            raise ValueError(f"Период {self.period} недоступен.")

    @staticmethod
    def count_aeroflot(response_):
        count_request = len([i for i in response_.json()
                             if i['service_name'] == config('SERVICE_NAME_AFL')])
        return count_request

    @staticmethod
    def count_russia(response_):
        count_request = len([i for i in response_.json()
                             if i['service_name'] == config('SERVICE_NAME_AKR')])
        return count_request

    @staticmethod
    def total_tickets(response_afl, response_akr):
        return Helpdesk.count_aeroflot(response_afl) + Helpdesk.count_russia(response_akr)

    @staticmethod
    def total_count_service_name_ife_afl(response_):
        count = len([i for i in response_.json()
                     if i['service_name'] == config('SERVICE_NAME_IFE_AFL')])
        return count

    @staticmethod
    def total_count_service_name_r_portal(response_):
        count = len([i for i in response_.json()
                     if i['service_name'] == config('SERVICE_NAME_MEDIA_AKR')])
        return count

    @staticmethod
    def count_user_request_afl(response_, admins):
        admins_count = {name: 0 for name in admins}
        for i in response_.json():
            name = i['mfullname']
            if name in admins_count:
                admins_count[name] += 1
        return dict(sorted(admins_count.items(), key=lambda x: x[1], reverse=True))

    @staticmethod
    def count_user_request_akr(response_, admins):
        admins_count = {name: 0 for name in admins}
        for i in response_.json():
            name = i['mfullname']
            if name in admins_count:
                admins_count[name] += 1
        return dict(sorted(admins_count.items(), key=lambda x: x[1], reverse=True))

    @staticmethod
    def count_user_request_total(response_afl, response_akr, admins):
        admins_count = {name: 0 for name in admins}
        for response_, service in ((response_afl, config('SERVICE_NAME_AFL')),
                                   (response_akr, config('SERVICE_NAME_AKR'))):
            for i in response_.json():
                if i.get('service_name') != service:
                    continue
                name = i.get('mfullname')
                if name in admins_count:
                    admins_count[name] += 1
        return dict(sorted(admins_count.items(), key=lambda x: x[1], reverse=True))

    @staticmethod
    def count_categories_afl(response_):
        total = {}
        ids = {}
        for i in response_.json():
            if i['ZayavCategory_id'] == 'E-mail ticket':
                i['ZayavCategory_id'] = "Категория не выбрана"
            if i['service_name'] == config('SERVICE_NAME_AFL'):
                cat = i['ZayavCategory_id']
                total[cat] = total.get(cat, 0) + 1
                ids.setdefault(cat, []).append(i.get('id'))
        sorted_cats = dict(sorted(total.items(), key=lambda x: x[1], reverse=True))
        return sorted_cats, ids

    @staticmethod
    def count_categories_akr(response_):
        total = {}
        ids = {}
        for i in response_.json():
            if i['ZayavCategory_id'] == 'E-mail ticket':
                i['ZayavCategory_id'] = "Категория не выбрана"
            if i['service_name'] == config('SERVICE_NAME_AKR'):
                cat = i['ZayavCategory_id']
                total[cat] = total.get(cat, 0) + 1
                ids.setdefault(cat, []).append(i.get('id'))
        sorted_cats = dict(sorted(total.items(), key=lambda x: x[1], reverse=True))
        return sorted_cats, ids

    @staticmethod
    def redirect_second_line(response_afl, response_akr):
        second_line = config('SECOND_LINE')
        count = 0
        for response_, service in ((response_afl, config('SERVICE_NAME_AFL')),
                                   (response_akr, config('SERVICE_NAME_AKR'))):
            count += sum(1 for i in response_.json()
                         if i.get('service_name') == service
                         and i.get('gfullname') == second_line)
        return count

    def second_line_stats(self, response_afl, response_akr):
        """Возвращает (кол-во переведённых на 2 линию, процент от общего числа заявок)"""
        count = self.redirect_second_line(response_afl, response_akr)
        total = self.total_tickets(response_afl, response_akr)
        percent = round(count / total * 100, 1) if total else 0.0
        return count, percent

    def avg_first_answers_user(self, response_afl, response_akr):
        total_minutes = 0
        count = 0
        service_afl = config('SERVICE_NAME_AFL')
        service_akr = config('SERVICE_NAME_AKR')
        for i in response_afl.json() + response_akr.json():
            if i.get('service_name') not in (service_afl, service_akr):
                continue
            minutes = first_answer_minutes(i)
            if minutes is not None:
                total_minutes += minutes
                count += 1
        if count == 0:
            return None
        return round(total_minutes / count, 1)

    @staticmethod
    def collect_tickets(response_afl, response_akr):
        """Все заявки обоих API в плоском виде — для детализации в Excel"""
        tickets = []
        for airline, response_ in (('afl', response_afl), ('akr', response_akr)):
            for i in response_.json():
                try:
                    ticket_id = int(i.get('id'))
                except (TypeError, ValueError):
                    ticket_id = None
                category = i.get('ZayavCategory_id') or ''
                if category == 'E-mail ticket':
                    category = "Категория не выбрана"
                tickets.append({
                    'airline':              airline,
                    'ticket_id':            ticket_id,
                    'service_name':         i.get('service_name') or '',
                    'category':             category,
                    'group':                i.get('gfullname') or '',
                    'executor':             i.get('mfullname') or '',
                    'created_at':           parse_helpdesk_date(i.get('Date')),
                    'first_answer_at':      parse_helpdesk_date(i.get('fStartTime')),
                    'first_answer_minutes': first_answer_minutes(i),
                })
        return tickets

    def get_all_statistic(self):
        try:
            logger.info("Запрос статистики HelpDesk за период %s", self.period)
            response_afl = requests.get(self.base_url_afl, auth=(self.login_helpdesk, self.password_helpdesk), timeout=10)
            response_afl.raise_for_status()
            try:
                afl_data = response_afl.json()
            except ValueError:
                logger.warning(f"Невалидный/пустой ответ от AFL API")
                afl_data = []
                response_afl.json = lambda: []
            logger.debug(f"{config('BASE_HELPDESK_AFL_URL')}: %s, Количество записей: %d", response_afl.status_code, len(afl_data))

            response_akr = requests.get(self.base_url_akr, auth=(self.login_helpdesk, self.password_helpdesk), timeout=10)
            response_akr.raise_for_status()
            try:
                akr_data = response_akr.json()
            except ValueError:
                logger.warning(f"Невалидный/пустой ответ от AKR API")
                akr_data = []
                response_akr.json = lambda: []
            logger.debug(f"{config('BASE_HELPDESK_AKR_URL')}: %s, Количество записей: %d", response_akr.status_code, len(akr_data))

            categories_afl, ids_afl = Helpdesk.count_categories_afl(response_afl)
            categories_akr, ids_akr = Helpdesk.count_categories_akr(response_akr)
            redirect_count, redirect_percent = self.second_line_stats(response_afl, response_akr)

            slovar_with_data = {
                "total_ticket":             Helpdesk.total_tickets(response_afl, response_akr),
                "request_count_afl":        Helpdesk.count_aeroflot(response_afl),
                "request_count_akr":        Helpdesk.count_russia(response_akr),
                "count_user_request_total": Helpdesk.count_user_request_total(response_afl, response_akr, self.admins),
                "count_service_ife":        Helpdesk.total_count_service_name_ife_afl(response_afl),
                "count_service_rportal":    Helpdesk.total_count_service_name_r_portal(response_akr),
                "redirect_second_line":       redirect_percent,
                "redirect_second_line_count": redirect_count,
                "avg_time_first_answer":    self.avg_first_answers_user(response_afl, response_akr),
                "count_categories_afl":     categories_afl,
                "ids_categories_afl":       ids_afl,
                "count_categories_akr":     categories_akr,
                "ids_categories_akr":       ids_akr,
                "tickets":                  Helpdesk.collect_tickets(response_afl, response_akr),
            }

            logger.info("Статистика успешно собрана: всего обращений %d", slovar_with_data['total_ticket'])
            return slovar_with_data

        except requests.Timeout:
            logger.error("Таймаут при запросе к HelpDesk API (period=%s, url_afl=%s, url_akr=%s)",
                         self.period, self.base_url_afl, self.base_url_akr)
            raise HelpdeskTimeoutError("Превышено время ожидания от HelpDesk API")
        except requests.ConnectionError as e:
            logger.error("Нет соединения с HelpDesk API (period=%s): %s", self.period, e)
            raise HelpdeskConnectionError(f"Нет соединения с HelpDesk API: {e}")
        except requests.HTTPError as e:
            body = e.response.text[:300] if e.response is not None else "—"
            logger.error("HelpDesk API вернул HTTP %s (period=%s, url=%s). Тело: %s",
                         e.response.status_code, self.period, e.response.url, body)
            raise HelpdeskHTTPError(e.response.status_code, e.response.url, body)
        except ValueError as e:
            logger.error("Ошибка парсинга JSON от HelpDesk API (period=%s): %s", self.period, e)
            raise HelpdeskParseError(f"Невалидный JSON от HelpDesk API: {e}")
        except Exception:
            logger.exception("Неожиданная ошибка в get_all_statistic (period=%s)", self.period)
            raise


class HelpdeskSaver:

    @staticmethod
    def _to_db_datetime(value):
        from django.conf import settings
        from django.utils import timezone
        if value is None or not settings.USE_TZ:
            return value
        return timezone.make_aware(value)

    @staticmethod
    def save(data: dict, period: str) -> None:
        from django.db import transaction
        from .models import (HelpdeskStatistic, HelpdeskAdminStat, HelpdeskCategoryAfl,
                             HelpdeskCategoryAkr, HelpdeskTicket)

        logger.info("Сохранение статистики за период %s", period)

        with transaction.atomic():
            HelpdeskStatistic.objects.filter(period=period).delete()

            stat = HelpdeskStatistic.objects.create(
                period=period,
                total_ticket=data['total_ticket'],
                request_count_afl=data['request_count_afl'],
                request_count_akr=data['request_count_akr'],
                count_service_ife=data['count_service_ife'],
                count_service_rportal=data['count_service_rportal'],
                redirect_second_line=data['redirect_second_line'],
                redirect_second_line_count=data['redirect_second_line_count'],
                avg_time_first_answer=data['avg_time_first_answer'],
            )

            HelpdeskAdminStat.objects.bulk_create(
                HelpdeskAdminStat(statistic=stat, name=name, count=count)
                for name, count in data['count_user_request_total'].items()
            )

            HelpdeskCategoryAfl.objects.bulk_create(
                HelpdeskCategoryAfl(statistic=stat, category=category, count=count,
                                    ticket_ids=data['ids_categories_afl'].get(category, []))
                for category, count in data['count_categories_afl'].items()
            )

            HelpdeskCategoryAkr.objects.bulk_create(
                HelpdeskCategoryAkr(statistic=stat, category=category, count=count,
                                    ticket_ids=data['ids_categories_akr'].get(category, []))
                for category, count in data['count_categories_akr'].items()
            )

            HelpdeskTicket.objects.bulk_create(
                (HelpdeskTicket(
                    statistic=stat,
                    airline=t['airline'],
                    ticket_id=t['ticket_id'],
                    service_name=t['service_name'],
                    category=t['category'],
                    group=t['group'],
                    executor=t['executor'],
                    created_at=HelpdeskSaver._to_db_datetime(t['created_at']),
                    first_answer_at=HelpdeskSaver._to_db_datetime(t['first_answer_at']),
                    first_answer_minutes=t['first_answer_minutes'],
                ) for t in data.get('tickets', [])),
                batch_size=500,
            )

        logger.info("Статистика за %s сохранена успешно", period)