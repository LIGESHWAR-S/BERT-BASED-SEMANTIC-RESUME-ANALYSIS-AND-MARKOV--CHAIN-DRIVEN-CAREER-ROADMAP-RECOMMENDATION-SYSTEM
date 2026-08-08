from django.urls import path
from . import views

urlpatterns = [
    path('resume/upload/', views.ResumeUploadAPIView.as_view(), name='api_resume_upload'),
    path('resume/analyze/', views.ResumeAnalyzeAPIView.as_view(), name='api_resume_analyze'),
    path('skills/', views.SkillListAPIView.as_view(), name='api_skill_list'),
]
