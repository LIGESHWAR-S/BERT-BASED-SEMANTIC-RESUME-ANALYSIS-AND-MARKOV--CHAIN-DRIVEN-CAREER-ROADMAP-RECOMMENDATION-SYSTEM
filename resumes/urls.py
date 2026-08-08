from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_home, name='dashboard_home'),
    path('upload/', views.resume_upload_view, name='resume_upload'),
    path('resume/<int:resume_id>/', views.resume_detail_view, name='resume_detail'),
]
