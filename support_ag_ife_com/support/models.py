from django.db import models
from django.contrib.auth.models import User


class Department(models.Model):
    """Отдел"""
    name = models.CharField(max_length=150)

    class Meta:
        verbose_name = 'Отдел'
        verbose_name_plural = 'Отделы'

    def __str__(self):
        return self.name


class Role(models.Model):
    """Роль — для будущих ролевых моделей"""
    name = models.CharField(max_length=150)

    class Meta:
        verbose_name = 'Роль'
        verbose_name_plural = 'Роли'

    def __str__(self):
        return self.name


class EmployeeProfile(models.Model):
    """Профиль сотрудника — 1 к 1 с User"""
    user           = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    full_name      = models.CharField(max_length=255, verbose_name='ФИО')
    email          = models.EmailField(verbose_name='Почта')
    phone          = models.CharField(max_length=20, blank=True, verbose_name='Телефон')
    birthday       = models.DateField(null=True, blank=True, verbose_name='Дата рождения')
    position       = models.CharField(max_length=150, blank=True, verbose_name='Должность')
    department     = models.ForeignKey(
                         Department, null=True, blank=True,
                         on_delete=models.SET_NULL,
                         verbose_name='Отдел'
                     )
    role           = models.ForeignKey(
                         Role, null=True, blank=True,
                         on_delete=models.SET_NULL,
                         verbose_name='Роль'
                     )
    photo          = models.ImageField(
                         upload_to='employee_photos/',
                         null=True, blank=True,
                         verbose_name='Фото'
                     )

    class Meta:
        verbose_name = 'Профиль сотрудника'
        verbose_name_plural = 'Профили сотрудников'

    def __str__(self):
        return self.full_name or self.user.username

    def get_photo(self):
        """Возвращает фото или заглушку"""
        if self.photo:
            return self.photo.url
        return 'support/images/avatar_man.jpg'