from django.urls import path

from . import views

app_name = 'project_finance'

urlpatterns = [
    path('mikrosites/',                                   views.summary,          name='summary'),
    path('mikrosites/projects/create/',                   views.project_create,   name='project_create'),
    path('mikrosites/<int:pk>/',                          views.project_detail,   name='project'),
    path('mikrosites/<int:pk>/edit/',                     views.project_edit,     name='project_edit'),
    path('mikrosites/<int:pk>/delete/',                   views.project_delete,   name='project_delete'),
    path('mikrosites/<int:pk>/price/save/',               views.price_save,       name='price_save'),
    path('mikrosites/<int:pk>/price/<int:item_id>/delete/', views.price_delete,   name='price_delete'),
    path('mikrosites/<int:pk>/tasks/save/',               views.task_save,        name='task_save'),
    path('mikrosites/tasks/<int:task_id>/delete/',        views.task_delete,      name='task_delete'),
    path('mikrosites/tasks/<int:task_id>/toggle-paid/',   views.task_toggle_paid, name='task_toggle_paid'),
]
