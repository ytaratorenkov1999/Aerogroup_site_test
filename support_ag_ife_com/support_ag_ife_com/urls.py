from django.contrib import admin
from django.urls import path, include

from support.views import protected_media

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('support.urls')),
    path('statistic/', include('statistic.urls')),
    path('daily/', include('daily_schedule.urls')),
    path('bdaeroflot/', include('aeroflot.urls')),
    path('bdrussia/', include('russia.urls')),
    path('knowledge-check/', include('knowledge_check.urls')),
    path('anonim/afl/', include('anonimaeroflot.urls')),
    path('anonim/akr/', include('anonimrussia.urls')),
    path('project-finance/', include('project_finance.urls')),
    # Медиафайлы — только для вошедших пользователей (см. support.views.protected_media)
    path('media/<path:path>', protected_media, name='protected_media'),
]