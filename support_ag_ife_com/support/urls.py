from django.urls import path
from . import views
from . import auth

urlpatterns = [
    path('', views.index, name='home'),
    path('login/', auth.user_login, name='login'),
    path('logout/', auth.user_logout, name='logout'),
    path('profile/', views.profile, name='profile'),
]