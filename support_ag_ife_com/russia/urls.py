from django.urls import path
from . import views

app_name = 'russia'

urlpatterns = [
    path('', views.knowledgebase, name='index'),

    path('search/', views.knowledge_search, name='search'),
    path('get-structure/', views.get_knowledge_structure, name='get_structure'),

    path('category/create/', views.category_create, name='category_create'),
    path('category/<int:category_id>/edit/', views.category_edit, name='category_edit'),
    path('category/<int:category_id>/delete/', views.category_delete, name='category_delete'),
    path('category/<slug:category_slug>/', views.category_detail, name='category_detail'),

    path('article/create/', views.article_create, name='article_create'),
    path('article/<slug:article_slug>/', views.article_detail, name='article_detail'),
    path('article/<slug:article_slug>/edit/', views.article_edit, name='article_edit'),
    path('article/<slug:article_slug>/delete/', views.article_delete, name='article_delete'),
    path('article/<slug:article_slug>/acknowledge/', views.article_acknowledge, name='article_acknowledge'),

    path('attachment/<int:attachment_id>/delete/', views.attachment_delete, name='attachment_delete'),
    path('attachment/<int:attachment_id>/delete-pending/', views.attachment_delete_pending, name='attachment_delete_pending'),
    path('attachment/upload-image/', views.attachment_upload_image, name='attachment_upload_image'),

    path('notifications/api/', views.notifications_api, name='notifications_api'),
    path('notifications/<int:notification_id>/read/', views.notification_read, name='notification_read'),
    path('notifications/<int:notification_id>/delete/', views.notification_delete, name='notification_delete'),
]