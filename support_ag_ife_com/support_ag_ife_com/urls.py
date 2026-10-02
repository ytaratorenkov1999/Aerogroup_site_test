from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

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

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)