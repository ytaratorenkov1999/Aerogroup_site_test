"""
Логика импорта графика из .xlsx файла в БД.

Структура ожидаемого файла:
  D4       — дата периода (datetime/date объект Excel)
  B9+      — порядковый номер строки (пока не пусто и является числом)
  C9+      — ФИО сотрудника
  E9..AI9+ — статусы по дням 1..31 (коды: ЯП / РВ / В)
"""

import re
import calendar
import datetime
import logging

import openpyxl

from support.models import EmployeeProfile, Department
from .models import DailyTable

logger = logging.getLogger('daily_schedule')

# Соответствие кодов из xlsx → статусы в БД
XLSX_CODE_TO_STATUS = {
    'ЯП': 'working',
    'РВ': 'working_holiday',
    'В':  'vacation',
}


def _to_short_name(full_name):
    """
    Нормализует ФИО к виду 'Фамилия И.О.'
    Работает с полным  'Иванов Иван Иванович',
    кратким            'Иванов И.О.',
    двусловным         'Иванов Иван'.
    """
    name = re.sub(r'\s+', ' ', full_name.replace('\n', ' ')).strip()
    parts = name.split()
    if len(parts) >= 3:
        if re.match(r'^[А-ЯЁA-Z]\.$', parts[1]):
            return name  # уже краткое
        return f"{parts[0]} {parts[1][0]}.{parts[2][0]}."
    elif len(parts) == 2:
        if re.match(r'^[А-ЯЁA-Z]\.$', parts[1]):
            return name
        return f"{parts[0]} {parts[1][0]}."
    return name


def _build_employee_index():
    """
    Строит словарь краткое_имя_нижний_регистр → EmployeeProfile
    для сотрудников отдела технической поддержки.
    """
    dept = Department.objects.filter(name='Отдел технической поддержки').first()
    if not dept:
        logger.warning('Отдел "Отдел технической поддержки" не найден в БД')
        return {}

    index = {}
    for emp in EmployeeProfile.objects.filter(department=dept):
        short = _to_short_name(emp.full_name).lower()
        index[short] = emp

    logger.info('Построен индекс сотрудников: %d человек', len(index))
    return index


def import_schedule_from_xlsx(file_obj, uploaded_by=None):
    """
    Парсит загруженный .xlsx файл и массово записывает/обновляет
    записи DailyTable в БД.

    Принимает:
        file_obj    — объект файла из request.FILES
        uploaded_by — username пользователя (для логов)

    Возвращает словарь:
        {
            'success':       bool,
            'imported':      int,
            'period':        str,          # '06.2026'
            'skipped_names': list[str],
            'skipped_codes': list[str],
            'error':         str,          # только при success=False
        }
    """
    user_label = uploaded_by or 'неизвестный'

    if not file_obj.name.lower().endswith('.xlsx'):
        logger.warning(
            'Пользователь %s передал файл неверного формата: %s',
            user_label, file_obj.name
        )
        return {'success': False, 'error': 'Поддерживается только формат .xlsx'}

    logger.info(
        'Пользователь %s начал импорт файла: %s',
        user_label, file_obj.name
    )

    try:
        wb = openpyxl.load_workbook(file_obj, data_only=True)
        ws = wb.active

        # ── Определяем период из ячейки D4 ───────────────────────
        period_cell = ws['D4'].value
        if not period_cell:
            logger.error('Ячейка D4 пуста — период не определён. Файл: %s', file_obj.name)
            return {'success': False, 'error': 'Не найдена ячейка периода (D4)'}

        if hasattr(period_cell, 'year'):
            year, month = period_cell.year, period_cell.month
        else:
            logger.error(
                'Не удалось распознать период в D4: %s. Файл: %s',
                period_cell, file_obj.name
            )
            return {
                'success': False,
                'error': f'Не удалось распознать период в D4: {period_cell}'
            }

        logger.info('Определён период: %02d.%d', month, year)
        days_in_month = calendar.monthrange(year, month)[1]

        # ── Индекс сотрудников отдела
        emp_index = _build_employee_index()

        # ── Читаем строки начиная с 9-й
        imported      = 0
        skipped_names = []
        skipped_codes = set()

        row = 9
        while True:
            num_cell = ws.cell(row, 2).value  # колонка B — номер
            if num_cell is None or not str(num_cell).strip().isdigit():
                break

            raw_name   = ws.cell(row, 3).value or ''  # колонка C — ФИО
            name_clean = re.sub(r'\s+', ' ', raw_name.replace('\n', ' ')).strip()
            name_short = _to_short_name(name_clean).lower()

            emp = emp_index.get(name_short)
            if emp is None:
                logger.warning(
                    'Сотрудник не найден в БД: "%s" (строка %d)', name_clean, row
                )
                skipped_names.append(name_clean)
                row += 1
                continue

            # ── Дни: колонки E(5)..AI(35) → дни 1..31 ───────────
            for col_offset in range(31):
                day_num = col_offset + 1
                if day_num > days_in_month:
                    break

                cell_val   = ws.cell(row, 5 + col_offset).value
                entry_date = datetime.date(year, month, day_num)

                if not cell_val or not isinstance(cell_val, str):
                    DailyTable.objects.filter(employee=emp, date=entry_date).delete()
                    continue

                code   = cell_val.strip()
                status = XLSX_CODE_TO_STATUS.get(code)

                if status is None:
                    logger.warning(
                        'Неизвестный код "%s" у сотрудника "%s" на дату %s',
                        code, name_clean, entry_date
                    )
                    skipped_codes.add(code)
                    continue

                DailyTable.objects.update_or_create(
                    employee=emp,
                    date=entry_date,
                    defaults={'status': status},
                )
                imported += 1

            row += 1

        logger.info(
            'Импорт завершён. Пользователь: %s, период: %02d.%d, '
            'записей: %d, пропущено сотрудников: %d, неизвестных кодов: %d',
            user_label, month, year, imported, len(skipped_names), len(skipped_codes)
        )

        if skipped_names:
            logger.warning('Не найденные сотрудники: %s', ', '.join(skipped_names))
        if skipped_codes:
            logger.warning('Неизвестные коды статусов: %s', ', '.join(skipped_codes))

        result = {
            'success':  True,
            'imported': imported,
            'period':   f'{month:02d}.{year}',
        }
        if skipped_names:
            result['skipped_names'] = skipped_names
        if skipped_codes:
            result['skipped_codes'] = list(skipped_codes)

        return result

    except Exception as e:
        logger.exception(
            'Критическая ошибка при импорте файла %s (пользователь: %s): %s',
            file_obj.name, user_label, e
        )
        return {'success': False, 'error': f'Ошибка обработки файла: {str(e)}'}