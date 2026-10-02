from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .helpdesk_api import (
    Helpdesk, HelpdeskSaver,
    HelpdeskError, HelpdeskTimeoutError,
    HelpdeskConnectionError, HelpdeskHTTPError, HelpdeskParseError,
)
from .models import HelpdeskStatistic, HelpdeskTicket
from .export_to_excel import export_excel, PERIOD_RE

MONTH_NAMES = {
    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
    5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
    9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
}


def _build_yearly_chart(selected_year):
    now = datetime.now()
    max_month = now.month if selected_year == now.year else 12
    totals = {}
    for s in (HelpdeskStatistic.objects
              .filter(period__startswith=f"{selected_year}-")
              .order_by('created_at')
              .only('period', 'total_ticket')):
        totals[s.period] = s.total_ticket
    labels = [MONTH_NAMES[m] for m in range(1, max_month + 1)]
    data = [totals.get(f"{selected_year}-{m:02d}", 0) for m in range(1, max_month + 1)]
    return labels, data


def _admins_with_tickets(stat):
    admins = list(stat.admins.values('name', 'count'))
    links = {a['name']: [] for a in admins}
    for t in (stat.tickets.handled_by_admins(list(links))
              .order_by('airline', 'created_at', 'ticket_id')
              .only('airline', 'ticket_id', 'executor')):
        if t.ticket_id is not None:
            links[t.executor].append({'id': t.ticket_id, 'url': t.url, 'airline': t.airline})
    for a in admins:
        a['tickets'] = links[a['name']]
    return admins


def _stat_payload(stat):
    """Данные для графиков — в шаблон уходят через json_script, без ручной сборки JS"""
    if stat is None:
        return {
            'total_ticket': 0, 'request_count_afl': 0, 'request_count_akr': 0,
            'count_service_ife': 0, 'count_service_rportal': 0,
            'redirect_second_line': 0, 'redirect_second_line_count': None,
            'avg_time_first_answer': None,
            'admins': [], 'categories_afl': [], 'categories_akr': [],
        }
    return {
        'total_ticket':               stat.total_ticket,
        'request_count_afl':          stat.request_count_afl,
        'request_count_akr':          stat.request_count_akr,
        'count_service_ife':          stat.count_service_ife,
        'count_service_rportal':      stat.count_service_rportal,
        'redirect_second_line':       stat.redirect_second_line,
        'redirect_second_line_count': stat.redirect_second_line_count,
        'avg_time_first_answer':      stat.avg_time_first_answer,
        'admins':         _admins_with_tickets(stat),
        'categories_afl': list(stat.categories_afl.values('category', 'count', 'ticket_ids')),
        'categories_akr': list(stat.categories_akr.values('category', 'count', 'ticket_ids')),
    }


@login_required(login_url='login')
def dashboards(request):
    period = request.GET.get('period') or ''
    if not PERIOD_RE.match(period):
        period = datetime.now().strftime("%Y-%m")
    selected_year = int(period.split('-')[0])
    month_labels, monthly_data = _build_yearly_chart(selected_year)

    stat = HelpdeskStatistic.objects.filter(period=period).order_by('-created_at').first()

    context = {
        'title': "Статистика обращений",
        'stat': stat,
        'periods': HelpdeskStatistic.objects.values_list('period', flat=True).distinct().order_by('-period'),
        'current_period': period,
        'dashboard_data': {
            'period': period,
            'stat': _stat_payload(stat),
            'monthLabels': month_labels,
            'monthlyData': monthly_data,
            'urls': {
                'update': reverse('stats_hd_update'),
                'export': reverse('stats_hd_export'),
            },
            'csrfToken': get_token(request),
            'ticketUrls': {
                'afl': HelpdeskTicket.base_url(HelpdeskTicket.AFL),
                'akr': HelpdeskTicket.base_url(HelpdeskTicket.AKR),
            },
        },
    }
    return render(request, 'statistic/dashboards.html', context)

# Кнопка обновление статистики
@login_required(login_url='login')
@require_POST
def update_statistic(request):
    period = request.POST.get('period') or datetime.now().strftime("%Y-%m")
    try:
        data = Helpdesk(period=period).get_all_statistic()
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except HelpdeskTimeoutError:
        return JsonResponse({'ok': False, 'error': 'HelpDesk не отвечает — превышено время ожидания'}, status=504)
    except HelpdeskConnectionError:
        return JsonResponse({'ok': False, 'error': 'Нет соединения с HelpDesk API'}, status=502)
    except HelpdeskHTTPError as e:
        return JsonResponse({'ok': False, 'error': f'HelpDesk вернул ошибку {e.status_code}'}, status=502)
    except HelpdeskParseError:
        return JsonResponse({'ok': False, 'error': 'HelpDesk вернул некорректные данные'}, status=502)
    except HelpdeskError:
        return JsonResponse({'ok': False, 'error': 'Неизвестная ошибка при получении данных'}, status=502)
    HelpdeskSaver.save(data, period=period)
    return JsonResponse({'ok': True})