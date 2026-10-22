from django.urls import path
from . import views

urlpatterns = [
    path('schedule/',      views.schedule,         name='schedule'),
    path('get-data/',      views.get_data,          name='schedule_get_data'),
    path('save-entry/',    views.save_entry,        name='schedule_save_entry'),
    path('import/',        views.import_schedule,   name='schedule_import'),
]