from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterAPIView.as_view(), name='api_register'),
    path('profile/', views.UserProfileAPIView.as_view(), name='api_profile'),
]
