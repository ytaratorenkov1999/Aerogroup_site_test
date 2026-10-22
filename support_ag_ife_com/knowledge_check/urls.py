from django.urls import path
from . import views

app_name = 'knowledge_check'

urlpatterns = [
    path('',                                 views.knowledge_test, name='knowledge'),
    path('api/start/<slug:category_slug>/',  views.start_quiz,    name='start_quiz'),
    path('api/resume/<slug:category_slug>/', views.resume_quiz,   name='resume_quiz'),
    path('api/question/',                    views.get_question,  name='get_question'),
    path('api/submit/',                      views.submit_answer, name='submit_answer'),
    path('api/complete/',                    views.complete_quiz, name='complete_quiz'),
]