from django.urls import path
from . import views


urlpatterns = [
    path('vsdesk/',         views.dashboards,       name='stats_hd'),
    path('vsdesk/update/',  views.update_statistic,  name='stats_hd_update'),
    path('vsdesk/export/',  views.export_excel,      name='stats_hd_export'),
]