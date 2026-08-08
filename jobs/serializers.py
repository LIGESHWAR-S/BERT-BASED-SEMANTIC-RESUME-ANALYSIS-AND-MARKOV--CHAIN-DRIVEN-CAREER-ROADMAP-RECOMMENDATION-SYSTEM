from rest_framework import serializers
from .models import JobRole, JobDescription, AnalysisResult, SkillGap
from resumes.serializers import SkillSerializer

class JobRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobRole
        fields = ['id', 'name', 'industry', 'minimum_experience', 'description']

class JobDescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobDescription
        fields = ['id', 'title', 'raw_text', 'extracted_skills', 'created_at']

class SkillGapSerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source='skill.name')
    category = serializers.CharField(source='skill.category')
    
    class Meta:
        model = SkillGap
        fields = ['skill_name', 'category', 'status', 'priority', 'explanation']

class AnalysisResultSerializer(serializers.ModelSerializer):
    skill_gaps = SkillGapSerializer(many=True, read_only=True)
    resume_name = serializers.CharField(source='resume.filename')
    job_title = serializers.CharField(source='job_description.title')
    
    class Meta:
        model = AnalysisResult
        fields = [
            'id', 'resume_name', 'job_title',
            'overall_score', 'semantic_score', 'skill_score', 
            'experience_score', 'education_score', 'project_score', 'certification_score',
            'explanation', 'skill_gaps', 'created_at'
        ]
