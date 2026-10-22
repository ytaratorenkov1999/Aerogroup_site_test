"""Файл с логикой авторизации на портал тех поддержки"""
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required


def user_login(request):
    if request.user.is_authenticated:
        return redirect('home')

    error = None

    if request.method == 'POST':
        username = request.POST.get('login')
        password = request.POST.get('password')
        remember = request.POST.get('remember')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            if not remember:
                request.session.set_expiry(0)
            return redirect('home')
        else:
            error = 'Неверный логин или пароль'

    return render(request, 'support/login.html', {'error': error})


def user_logout(request):
    auth_logout(request)
    return redirect('login')