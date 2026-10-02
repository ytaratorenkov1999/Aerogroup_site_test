import json
import logging

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from support.models import EmployeeProfile, Department
from support.roles import role_required
from .models import DailyTable
from .export_to_excel_daily import import_schedule_from_xlsx

logger = logging.getLogger('daily_schedule')


def _get_dept_employees():
    dept = Department.objects.filter(name='Отдел технической поддержки').first()
    if not dept:
        return EmployeeProfile.objects.none()
    return EmployeeProfile.objects.filter(department=dept).order_by('full_name')


@login_required(login_url='login')
def schedule(request):
    return render(request, 'daily_schedule/schedule_grafik.html', {
        'title': 'График дежурств',
    })


@login_required(login_url='login')
def get_data(request):
    try:
        year  = int(request.GET.get('year'))
        month = int(request.GET.get('month'))
    except (TypeError, ValueError):
        logger.warning('get_data: неверные параметры year/month от пользователя %s', request.user)
        return JsonResponse({'success': False, 'error': 'Неверные параметры'})

    employees_qs = _get_dept_employees()

    entries = DailyTable.objects.filter(
        employee__in=employees_qs,
        date__year=year,
        date__month=month,
    ).select_related('employee')

    schedule_data = {}
    for entry in entries:
        schedule_data.setdefault(entry.employee_id, {})[str(entry.date)] = entry.status

    return JsonResponse({
        'success':   True,
        'employees': [{'id': emp.id, 'name': emp.full_name} for emp in employees_qs],
        'schedule':  schedule_data,
    })


@login_required(login_url='login')
@require_POST
@role_required('Администратор', 'Руководитель')
def save_entry(request):
    try:
        data        = json.loads(request.body)
        employee_id = int(data['employee_id'])
        date_str    = data['date']
        status      = data.get('status', '')
    except (KeyError, ValueError, json.JSONDecodeError):
        logger.warning('save_entry: неверные данные от пользователя %s', request.user)
        return JsonResponse({'success': False, 'error': 'Неверные данные'})

    valid_statuses = {s[0] for s in DailyTable.STATUS_CHOICES}
    if status and status not in valid_statuses:
        logger.warning(
            'save_entry: недопустимый статус "%s" от пользователя %s',
            status, request.user
        )
        return JsonResponse({'success': False, 'error': 'Недопустимый статус'})

    try:
        from datetime import date as date_cls
        date = date_cls.fromisoformat(date_str)
    except (ValueError, TypeError):
        logger.warning(
            'save_entry: невалидная дата "%s" от пользователя %s',
            date_str, request.user
        )
        return JsonResponse({'success': False, 'error': 'Неверный формат даты'})

    try:
        employee = EmployeeProfile.objects.get(id=employee_id)
    except EmployeeProfile.DoesNotExist:
        logger.warning('save_entry: сотрудник id=%s не найден (пользователь %s)', employee_id, request.user)
        return JsonResponse({'success': False, 'error': 'Сотрудник не найден'})

    if status:
        DailyTable.objects.update_or_create(
            employee=employee,
            date=date,
            defaults={'status': status},
        )
    else:
        DailyTable.objects.filter(employee=employee, date=date).delete()

    return JsonResponse({'success': True})


@login_required(login_url='login')
@require_POST
@role_required('Администратор', 'Руководитель')
def import_schedule(request):
    uploaded = request.FILES.get('file')
    if not uploaded:
        logger.warning('import_schedule: файл не передан (пользователь %s)', request.user)
        return JsonResponse({'success': False, 'error': 'Файл не передан'})

    result = import_schedule_from_xlsx(uploaded, uploaded_by=request.user.username)
    return JsonResponse(result)