from django.urls import path
from . import views

app_name = 'monitoring'

urlpatterns = [
    # Главная страница мониторинга хоста
    path('', views.index, name='index'),

]