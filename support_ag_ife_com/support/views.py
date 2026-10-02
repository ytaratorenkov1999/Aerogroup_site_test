import mimetypes
import os
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils._os import safe_join
from .models import EmployeeProfile

@login_required(login_url='login')
def index(request):
    return render(request, 'support/index.html', {'title': "Главная страница"})


@login_required(login_url='login')
def profile(request):
    try:
        employee = request.user.profile
    except EmployeeProfile.DoesNotExist:
        employee = EmployeeProfile.objects.create(
            user=request.user,
            full_name=request.user.get_full_name() or request.user.username,
            email=request.user.email,
        )

    if request.method == 'POST':
        employee.full_name = request.POST.get('full_name', '').strip()
        employee.email     = request.POST.get('email', '').strip()
        employee.phone     = request.POST.get('phone', '').strip()
        employee.position  = request.POST.get('position', '').strip()

        if request.POST.get('birthday'):
            employee.birthday = request.POST.get('birthday')

        if request.POST.get('delete_photo'):
            if employee.photo:
                employee.photo.delete(save=False)
            employee.photo = None
        elif 'photo' in request.FILES:
            if employee.photo:
                employee.photo.delete(save=False)
            employee.photo = request.FILES['photo']

        employee.save()
        messages.success(request, 'Профиль успешно обновлён')
        return redirect('profile')

    return render(request, 'support/profile.html', {'employee': employee})

@login_required(login_url='login')
def protected_media(request, path):
    """
    Файлы из MEDIA (вложения БЗ, фото сотрудников, вложения к вопросам)
    отдаются только вошедшим пользователям.

    В продакшене (MEDIA_X_ACCEL=True) Django лишь проверяет доступ, а сам файл
    отдаёт nginx через внутренний location /protected-media/ (X-Accel-Redirect).
    Без nginx (локальная разработка) файл отдаёт Django.
    """
    try:
        full_path = safe_join(settings.MEDIA_ROOT, path)
    except SuspiciousFileOperation:
        raise Http404
    if not os.path.isfile(full_path):
        raise Http404

    content_type = mimetypes.guess_type(full_path)[0] or 'application/octet-stream'
    if settings.MEDIA_X_ACCEL:
        response = HttpResponse(content_type=content_type)
        response['X-Accel-Redirect'] = settings.MEDIA_X_ACCEL_PREFIX + quote(path)
        return response
    return FileResponse(open(full_path, 'rb'), content_type=content_type)
