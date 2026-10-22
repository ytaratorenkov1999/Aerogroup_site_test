import io
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

import openpyxl
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.utils import timezone
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from .models import HelpdeskStatistic, HelpdeskTicket

MONTH_NAMES = {
    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
    5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
    9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
}

PERIOD_RE = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')

class Style:
    FONT_NAME = 'Arial'

    BLUE = '03A0DC'
    RED = 'D32F2F'
    GRAY = '455A64'

    ALT_GRAY = 'F0F4F8'
    ALT_AFL = 'E3F6FD'
    ALT_AKR = 'FDEAEA'

    DATETIME_FORMAT = 'DD.MM.YYYY HH:MM'

    title = Font(name=FONT_NAME, size=14, bold=True, color='263238')
    subtitle = Font(name=FONT_NAME, size=10, color='607D8B')
    header = Font(name=FONT_NAME, size=11, bold=True, color='FFFFFF')
    cell = Font(name=FONT_NAME, size=10)
    cell_bold = Font(name=FONT_NAME, size=10, bold=True)
    link = Font(name=FONT_NAME, size=10, color='0563C1', underline='single')
    muted = Font(name=FONT_NAME, size=10, italic=True, color='9E9E9E')

    title_fill = PatternFill('solid', fgColor='ECEFF1')

    @staticmethod
    def fill(color):
        return PatternFill('solid', fgColor=color)

    @staticmethod
    def border(outer_top=False, outer_bottom=False, outer_left=False, outer_right=False):
        thin = Side(style='thin', color='B0BEC5')
        thick = Side(style='medium', color='455A64')
        return Border(
            top=thick if outer_top else thin,
            bottom=thick if outer_bottom else thin,
            left=thick if outer_left else thin,
            right=thick if outer_right else thin,
        )


AIRLINE_SHEETS = {
    HelpdeskTicket.AFL: ('ПАО "Аэрофлот"', Style.BLUE, Style.ALT_AFL),
    HelpdeskTicket.AKR: ('АК "Россия"', Style.RED, Style.ALT_AKR),
}


def excel_datetime(value):
    if value is None:
        return None
    if timezone.is_aware(value):
        value = timezone.localtime(value).replace(tzinfo=None)
    return value


class BaseExcelReport:
    slug = ''
    title = ''

    FIRST_ROW = 3
    FIRST_COL = 3

    def col(self, n):
        return self.FIRST_COL + n - 1

    def row(self, n):
        return self.FIRST_ROW + n - 1

    def __init__(self, stat: HelpdeskStatistic):
        self.stat = stat
        self.period = stat.period
        self.wb = openpyxl.Workbook()
        self.wb.remove(self.wb.active)


    @property
    def period_label(self):
        year, month = self.period.split('-')
        return f'{MONTH_NAMES[int(month)]} {year}'

    @property
    def filename(self):
        return f'VsDesk_{self.slug}_{self.period}.xlsx'


    def build(self):
        raise NotImplementedError

    def render(self) -> bytes:
        self.build()
        buf = io.BytesIO()
        self.wb.save(buf)
        return buf.getvalue()

    def new_sheet(self, title):
        ws = self.wb.create_sheet(title)
        ws.page_setup.orientation = 'landscape'
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_options.horizontalCentered = True
        return ws


    @staticmethod
    def set_widths(ws, widths, first_col=1):
        for idx, width in enumerate(widths, first_col):
            ws.column_dimensions[get_column_letter(idx)].width = width

    @staticmethod
    def write_title(ws, text, ncols, row=1, subtitle=None, first_col=1):
        last_col = first_col + ncols - 1
        ws.merge_cells(start_row=row, start_column=first_col, end_row=row, end_column=last_col)
        c = ws.cell(row=row, column=first_col, value=text)
        c.font = Style.title
        c.fill = Style.title_fill
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        ws.row_dimensions[row].height = 32
        if subtitle:
            ws.merge_cells(start_row=row + 1, start_column=first_col, end_row=row + 1, end_column=last_col)
            s = ws.cell(row=row + 1, column=first_col, value=subtitle)
            s.font = Style.subtitle
            s.alignment = Alignment(horizontal='center', vertical='center')
            ws.row_dimensions[row + 1].height = 20
            return row + 2
        return row + 1

    @staticmethod
    def write_header(ws, row, headers, color, first_col=1):
        for col, text in enumerate(headers, first_col):
            c = ws.cell(row=row, column=col, value=text)
            c.font = Style.header
            c.fill = Style.fill(color)
            c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        ws.row_dimensions[row].height = 28


    @staticmethod
    def apply_borders(ws, min_row, max_row, min_col, max_col):
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                ws.cell(row=row, column=col).border = Style.border(
                    outer_top=(row == min_row),
                    outer_bottom=(row == max_row),
                    outer_left=(col == min_col),
                    outer_right=(col == max_col),
                )

    def write_ticket_table(self, ws, title, columns, rows, header_color, alt_color, empty_text):
        columns = [Column('№', 7, None)] + list(columns)
        ncols = len(columns)
        first_col, last_col = self.col(1), self.col(ncols)
        self.set_widths(ws, [c.width for c in columns], first_col=first_col)

        header_row = self.write_title(ws, title, ncols, row=self.FIRST_ROW, first_col=first_col)
        self.write_header(ws, header_row, [c.header for c in columns], header_color, first_col=first_col)
        row = header_row + 1

        if not rows:
            self.write_note(ws, row, ncols, empty_text, first_col=first_col)
            self.apply_borders(ws, header_row, row, first_col, last_col)
            self.set_print_area(ws, ncols, row)
            return None, None, row + 1

        first_data_row = row
        for idx, ticket in enumerate(rows, 1):
            alt = Style.fill(alt_color) if idx % 2 == 0 else None
            for n, column in enumerate(columns, 1):
                value = idx if n == 1 else column.value(ticket)
                c = ws.cell(row=row, column=self.col(n), value=value)
                c.font = Style.link if (column.is_link and value) else Style.cell
                c.alignment = Alignment(horizontal=column.align, vertical='center')
                if column.is_link and value:
                    c.hyperlink = value
                if column.number_format:
                    c.number_format = column.number_format
                if alt:
                    c.fill = alt
            row += 1
        last_data_row = row - 1

        self.apply_borders(ws, header_row, last_data_row, first_col, last_col)
        self.set_print_area(ws, ncols, last_data_row)
        return first_data_row, last_data_row, row

    def set_print_area(self, ws, ncols, last_row):
        ws.print_area = (f'{get_column_letter(self.col(1))}{self.FIRST_ROW}:'
                         f'{get_column_letter(self.col(ncols))}{last_row}')

    @staticmethod
    def write_note(ws, row, ncols, text, first_col=1):
        ws.merge_cells(start_row=row, start_column=first_col, end_row=row, end_column=first_col + ncols - 1)
        c = ws.cell(row=row, column=first_col, value=text)
        c.font = Style.muted
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        ws.row_dimensions[row].height = 30




@dataclass
class Column:
    header: str
    width: float
    value: Callable[[HelpdeskTicket], Any]
    number_format: Optional[str] = None
    is_link: bool = False
    align: str = 'center'


def sort_by_category(tickets):
    """Сначала самые частые категории (как на графике), внутри категории — по дате создания"""
    counts = Counter(t.category for t in tickets)
    return sorted(tickets, key=lambda t: (-counts[t.category], t.category))


def link_column():
    return Column('Ссылка на заявку', 50, lambda t: t.url, is_link=True)


def created_column():
    return Column('Дата создания', 18, lambda t: excel_datetime(t.created_at),
                  number_format=Style.DATETIME_FORMAT)


class TicketListReport(BaseExcelReport):
    airlines = (HelpdeskTicket.AFL, HelpdeskTicket.AKR)
    NO_DETAILS_TEXT = ('Нажмите «Обновить статистику» и выгрузите отчёт заново')
    EMPTY_TEXT = 'Заявок нет'

    def get_columns(self) -> list:
        raise NotImplementedError

    def get_queryset(self):
        """Заявки отчёта по обеим авиакомпаниям — фильтр по airline делается в build()"""
        raise NotImplementedError

    def get_rows(self, airline) -> list:
        return list(self.get_queryset().filter(airline=airline).order_by('created_at', 'ticket_id'))

    def write_footer(self, ws, row, airline, rows, first_data_row, last_data_row):
        """Итоговые строки под таблицей. Возвращает номер следующей свободной строки."""
        return row

    def build(self):
        columns = self.get_columns()
        has_details = self.stat.tickets.exists()

        for airline in self.airlines:
            sheet_name, header_color, alt_color = AIRLINE_SHEETS[airline]
            ws = self.new_sheet(sheet_name)
            rows = self.get_rows(airline) if has_details else []
            first_data_row, last_data_row, next_row = self.write_ticket_table(
                ws, sheet_name, columns, rows, header_color, alt_color,
                empty_text=self.EMPTY_TEXT if has_details else self.NO_DETAILS_TEXT,
            )
            if rows:
                last_row = self.write_footer(ws, next_row + 1, airline, rows, first_data_row, last_data_row)
                self.set_print_area(ws, len(columns) + 1, max(last_row - 1, last_data_row))


    def write_total(self, ws, row, label, value, label_col, value_col, number_format=None):
        """label_col / value_col — номера колонок таблицы (1 — «№»)"""
        label_cell = ws.cell(row=row, column=self.col(label_col), value=label)
        label_cell.font = Style.cell_bold
        label_cell.alignment = Alignment(horizontal='center', vertical='center')
        value_cell = ws.cell(row=row, column=self.col(value_col), value=value)
        value_cell.font = Style.cell_bold
        value_cell.alignment = Alignment(horizontal='center', vertical='center')
        if number_format:
            value_cell.number_format = number_format
        return row + 1


class CrewTabletReport(TicketListReport):
    slug = 'crew_tablet'
    title = 'Заявки Crew Tablet'

    def get_columns(self):
        return [link_column(), created_column()]

    def get_queryset(self):
        return self.stat.tickets.crew_tablet()

    def write_footer(self, ws, row, airline, rows, first_data_row, last_data_row):
        return self.write_total(ws, row, 'Всего заявок:', len(rows), label_col=2, value_col=3)


class ServicesReport(TicketListReport):
    slug = 'services'
    title = 'Заявки по сервисам'

    def get_columns(self):
        return [link_column(), Column('Сервис', 18, lambda t: t.service_name), created_column()]

    def get_queryset(self):
        return self.stat.tickets.media_services()

    def write_footer(self, ws, row, airline, rows, first_data_row, last_data_row):
        return self.write_total(ws, row, 'Всего заявок:', len(rows), label_col=2, value_col=3)


class AdminsReport(TicketListReport):
    slug = 'admins'
    title = 'Решённые обращения сотрудниками'

    def get_columns(self):
        return [link_column(), created_column(),
                Column('Исполнитель', 28, lambda t: t.executor)]

    def get_queryset(self):
        # Сотрудники — те же, что сохранены в статистике периода (график на дашборде)
        names = list(self.stat.admins.values_list('name', flat=True))
        return self.stat.tickets.handled_by_admins(names)

    def write_footer(self, ws, row, airline, rows, first_data_row, last_data_row):
        row = self.write_total(ws, row, 'Всего заявок:', len(rows), label_col=3, value_col=4)
        row += 1
        for name, count in Counter(t.executor for t in rows).most_common():
            row = self.write_total(ws, row, name, count, label_col=3, value_col=4)
        return row


class SecondLineReport(TicketListReport):
    slug = 'second_line'
    title = 'Обращения, переведённые на 2 линию'

    def get_columns(self):
        return [link_column(), created_column(),
                Column('Группа', 26, lambda t: t.group),
                Column('Исполнитель', 28, lambda t: t.executor)]

    def get_queryset(self):
        return self.stat.tickets.second_line()

    def write_footer(self, ws, row, airline, rows, first_data_row, last_data_row):
        total = self.stat.tickets.crew_tablet().filter(airline=airline).count()
        percent = round(len(rows) / total * 100, 1) if total else 0.0
        row = self.write_total(ws, row, 'Переведено на 2 линию:', len(rows), label_col=3, value_col=4)
        row = self.write_total(ws, row, 'Всего заявок Crew Tablet:', total, label_col=3, value_col=4)
        return self.write_total(ws, row, 'Процент переведённых:', percent / 100,
                                label_col=3, value_col=4, number_format='0.0%')


class FirstAnswerReport(TicketListReport):
    slug = 'first_answer'
    title = 'Время первого ответа'

    def get_columns(self):
        return [
            link_column(),
            created_column(),
            Column('Первый ответ', 18, lambda t: excel_datetime(t.first_answer_at),
                   number_format=Style.DATETIME_FORMAT),
            Column('Время ответа, мин', 16,
                   lambda t: round(t.first_answer_minutes, 1) if t.first_answer_minutes is not None else None,
                   number_format='0.0'),
        ]

    def get_queryset(self):
        return self.stat.tickets.crew_tablet()

    def write_footer(self, ws, row, airline, rows, first_data_row, last_data_row):
        col = get_column_letter(self.col(5))
        formula = f'=IFERROR(ROUND(AVERAGE({col}{first_data_row}:{col}{last_data_row}),1),"—")'
        row = self.write_total(ws, row, 'Среднее по авиакомпании, мин:', formula, label_col=4, value_col=5)
        return row + 1


class CategoriesReport(TicketListReport):
    """Заявки одной авиакомпании с категориями, в порядке графика на дашборде"""
    title = 'Категории обращений'

    def get_columns(self):
        return [link_column(), Column('Категория', 34, lambda t: t.category), created_column()]

    def get_queryset(self):
        return self.stat.tickets.crew_tablet()

    def get_rows(self, airline):
        return sort_by_category(super().get_rows(airline))

    def write_footer(self, ws, row, airline, rows, first_data_row, last_data_row):
        row = self.write_total(ws, row, 'Всего заявок:', len(rows), label_col=3, value_col=4)
        row += 1
        for category, count in Counter(t.category for t in rows).most_common():
            row = self.write_total(ws, row, category, count, label_col=3, value_col=4)
        return row


class CategoriesAflReport(CategoriesReport):
    slug = 'categories_afl'
    airlines = (HelpdeskTicket.AFL,)


class CategoriesAkrReport(CategoriesReport):
    slug = 'categories_akr'
    airlines = (HelpdeskTicket.AKR,)

class SummaryReport(BaseExcelReport):
    slug = 'summary'
    title = 'Статистика HelpDesk'

    @property
    def filename(self):
        return f'helpdesk_{self.period}.xlsx'

    def build(self):
        self.build_summary()
        self.build_categories('Категории Аэрофлот', HelpdeskTicket.AFL)
        self.build_categories('Категории Россия', HelpdeskTicket.AKR)
        self.build_admins()
        self.build_dynamics()

    def _write_row(self, ws, row, values, alt=False, formats=None):
        for n, val in enumerate(values, 1):
            c = ws.cell(row=row, column=self.col(n), value=val)
            c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            c.font = Style.cell
            if formats and formats.get(n):
                c.number_format = formats[n]
            if alt:
                c.fill = Style.fill(Style.ALT_GRAY)
        ws.row_dimensions[row].height = 22

    def _finish_table(self, ws, first_row, last_row, ncols):
        """Рамка, закреплённая шапка и область печати для таблицы на листе"""
        first_col, last_col = self.col(1), self.col(ncols)
        self.apply_borders(ws, first_row, last_row, first_col, last_col)
        ws.print_area = (f'{get_column_letter(first_col)}{self.FIRST_ROW}:'
                         f'{get_column_letter(last_col)}{last_row}')


    def build_summary(self):
        stat = self.stat
        ws = self.new_sheet('Сводка')
        self.set_widths(ws, [42, 22], first_col=self.col(1))
        header_row = self.write_title(ws, f'{self.title} — {self.period_label}', 2,
                                      row=self.row(1), first_col=self.col(1))

        count = stat.redirect_second_line_count
        rows = [
            ('Всего обращений',                   stat.total_ticket, None),
            ('Обращений Аэрофлот',                stat.request_count_afl, None),
            ('Обращений Россия',                  stat.request_count_akr, None),
            ('Заявок IFE.AFL',                    stat.count_service_ife, None),
            ('Заявок r.portal',                   stat.count_service_rportal, None),
            ('Переведено на 2 линию, шт',         count if count is not None else '—', None),
            ('Переведено на 2 линию, %',          stat.redirect_second_line / 100, '0.0%'),
            ('Среднее время первого ответа, мин',
             stat.avg_time_first_answer if stat.avg_time_first_answer is not None else '—', '0.0'),
        ]
        self.write_header(ws, header_row, ['Показатель', 'Значение'], Style.GRAY, first_col=self.col(1))
        for i, (label, value, fmt) in enumerate(rows, header_row + 1):
            self._write_row(ws, i, (label, value), alt=(i % 2 == 0), formats={2: fmt})
        self._finish_table(ws, header_row, header_row + len(rows), 2)



    def build_categories(self, sheet_title, airline):
        airline_name, header_color, alt_color = AIRLINE_SHEETS[airline]
        ws = self.new_sheet(sheet_title)
        has_details = self.stat.tickets.exists()
        rows = []
        if has_details:
            rows = sort_by_category(list(
                self.stat.tickets.crew_tablet().filter(airline=airline).order_by('created_at', 'ticket_id')
            ))
        columns = [
            created_column(),
            Column('Категория', 34, lambda t: t.category),
            Column('Исполнитель', 28, lambda t: t.executor),
            link_column(),
        ]
        self.write_ticket_table(
            ws, airline_name, columns, rows, header_color, alt_color,
            empty_text='Заявок нет' if has_details else TicketListReport.NO_DETAILS_TEXT,
        )


    def build_admins(self):
        ws = self.new_sheet('Сотрудники')
        self.set_widths(ws, [38, 20], first_col=self.col(1))
        admins = list(self.stat.admins.order_by('-count'))
        header_row = self.row(1)
        self.write_header(ws, header_row, ['Сотрудник', 'Решено обращений'], Style.GRAY, first_col=self.col(1))
        for i, admin in enumerate(admins, header_row + 1):
            self._write_row(ws, i, [admin.name, admin.count], alt=(i % 2 == 0))
        self._finish_table(ws, header_row, header_row + len(admins), 2)


    def build_dynamics(self):
        year = self.period.split('-')[0]
        ws = self.new_sheet('Динамика')
        self.set_widths(ws, [18, 20], first_col=self.col(1))
        header_row = self.row(1)
        self.write_header(ws, header_row, ['Месяц', 'Всего обращений'], Style.GRAY, first_col=self.col(1))

        # Одним запросом: последняя запись за каждый месяц года
        totals = {}
        for s in (HelpdeskStatistic.objects
                  .filter(period__startswith=f'{year}-')
                  .order_by('created_at')
                  .only('period', 'total_ticket')):
            totals[s.period] = s.total_ticket

        for month_num in range(1, 13):
            count = totals.get(f'{year}-{month_num:02d}')
            self._write_row(ws, header_row + month_num, [MONTH_NAMES[month_num], count],
                            alt=(month_num % 2 == 0))
        self._finish_table(ws, header_row, header_row + 12, 2)




REPORTS = {
    cls.slug: cls for cls in (
        SummaryReport,
        CrewTabletReport,
        ServicesReport,
        AdminsReport,
        SecondLineReport,
        FirstAnswerReport,
        CategoriesAflReport,
        CategoriesAkrReport,
    )
}


@login_required(login_url='login')
def export_excel(request):
    period = request.GET.get('period') or datetime.now().strftime("%Y-%m")
    if not PERIOD_RE.match(period):
        return HttpResponse('Неверный формат периода, ожидается YYYY-MM', status=400)

    report_cls = REPORTS.get(request.GET.get('report') or SummaryReport.slug)
    if report_cls is None:
        raise Http404('Неизвестный отчёт')

    try:
        stat = HelpdeskStatistic.objects.filter(period=period).latest('created_at')
    except HelpdeskStatistic.DoesNotExist:
        return HttpResponse('Нет данных за выбранный период', status=404)

    report = report_cls(stat)
    response = HttpResponse(
        report.render(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{report.filename}"'
    return response