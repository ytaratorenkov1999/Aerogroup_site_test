from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
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