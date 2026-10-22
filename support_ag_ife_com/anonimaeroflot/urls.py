from django.urls import path
from . import views

app_name = 'anonimaeroflot'

urlpatterns = [
    path('', views.index, name='anonimaeroflot'),
    path('process/', views.process_files, name='process_files'),
]
