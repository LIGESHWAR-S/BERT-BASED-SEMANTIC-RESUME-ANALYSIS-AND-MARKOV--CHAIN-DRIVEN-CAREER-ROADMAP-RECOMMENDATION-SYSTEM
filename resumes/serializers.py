from rest_framework import serializers
from .models import Resume, Education, Experience, Skill, ResumeSkill

class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name', 'category']

class ResumeSkillSerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source='skill.name')
    category = serializers.CharField(source='skill.category')
    
    class Meta:
        model = ResumeSkill
        fields = ['skill_name', 'category', 'matched_text']

class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = ['id', 'degree', 'institution', 'field_of_study', 'start_date', 'end_date']

class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        fields = ['id', 'job_title', 'company', 'location', 'start_date', 'end_date', 'description']

class ResumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resume
        fields = ['id', 'filename', 'file_size', 'content_type', 'uploaded_at']

class ResumeDetailSerializer(serializers.ModelSerializer):
    education_records = EducationSerializer(many=True, read_only=True)
    experience_records = ExperienceSerializer(many=True, read_only=True)
    skills = serializers.SerializerMethodField()
    
    class Meta:
        model = Resume
        fields = [
            'id', 'filename', 'file_size', 'content_type', 
            'contact_info', 'summary', 'sections', 
            'education_records', 'experience_records', 'skills', 
            'uploaded_at'
        ]
        
    def get_skills(self, obj):
        matches = obj.resume_skills.all()
        return ResumeSkillSerializer(matches, many=True).data
