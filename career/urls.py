from django.urls import path
from . import views

urlpatterns = [
    path('recommend/', views.career_recommend_view, name='career_recommend'),
    path('roadmap/<int:recommendation_id>/', views.roadmap_detail_view, name='roadmap_detail'),
    path('roadmap/<int:recommendation_id>/download/', views.download_roadmap_markdown_view, name='roadmap_download_markdown'),
    path('roadmap/<int:recommendation_id>/pdf/', views.download_roadmap_pdf_view, name='roadmap_download_pdf'),
    path('match-pdf/<int:analysis_id>/', views.generate_match_recommendation_pdf_view, name='match_recommend_pdf'),
]
