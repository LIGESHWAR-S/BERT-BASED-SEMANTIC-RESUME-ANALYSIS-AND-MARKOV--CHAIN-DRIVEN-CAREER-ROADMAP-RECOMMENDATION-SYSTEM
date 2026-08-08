from django.urls import path
from . import views

urlpatterns = [
    path('career/recommend/', views.CareerRecommendAPIView.as_view(), name='api_career_recommend'),
    path('career/roadmap/', views.CareerRoadmapAPIView.as_view(), name='api_career_roadmap'),
]
