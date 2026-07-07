from django.urls import path

from . import views

app_name = 'quizzes'

urlpatterns = [
    path('<int:pk>/take/', views.take_quiz, name='take'),
    path('attempts/<int:pk>/', views.quiz_result, name='result'),
]
