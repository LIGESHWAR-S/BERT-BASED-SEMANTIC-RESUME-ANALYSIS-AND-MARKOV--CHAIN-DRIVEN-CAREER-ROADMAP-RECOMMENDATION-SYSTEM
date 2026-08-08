from django.urls import path
from . import views

urlpatterns = [
    path('match/', views.match_view, name='match_create'),
    path('analysis/<int:analysis_id>/', views.analysis_detail_view, name='analysis_detail'),
]
