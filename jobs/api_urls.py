from django.urls import path
from . import views

urlpatterns = [
    path('job/analyze/', views.JobDescriptionAnalyzeAPIView.as_view(), name='api_job_analyze'),
    path('match/', views.ResumeToJobMatchAPIView.as_view(), name='api_resume_match'),
    path('skill-gaps/', views.SkillGapsAPIView.as_view(), name='api_skill_gaps'),
    path('analysis/<int:id>/', views.AnalysisResultRetrieveAPIView.as_view(), name='api_analysis_retrieve'),
]
