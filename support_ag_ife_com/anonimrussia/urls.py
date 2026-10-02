from django.urls import path
from . import views

app_name = 'anonimrussia'

urlpatterns = [
    path('', views.index, name='anonimrussia'),
    path('process/', views.process_files, name='process_files'),
]