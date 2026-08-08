from django.db import models
from django.contrib.auth.models import User
from resumes.models import Resume, Skill

class JobRole(models.Model):
    name = models.CharField(max_length=100, unique=True)
    industry = models.CharField(max_length=100)
    minimum_experience = models.IntegerField(default=0, help_text="Minimum experience years required")
    description = models.TextField(blank=True, null=True)
    embedding = models.TextField(blank=True, null=True, help_text="SBERT 384d embedding serialized as JSON array")

    def __str__(self):
        return self.name

class JobSkill(models.Model):
    job_role = models.ForeignKey(JobRole, on_delete=models.CASCADE, related_name='job_skills')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='job_matches')
    is_required = models.BooleanField(default=True, help_text="True if required, False if preferred/optional")

    class Meta:
        unique_together = ('job_role', 'skill')

    def __str__(self):
        status = "Required" if self.is_required else "Preferred"
        return f"{self.job_role.name} - {self.skill.name} ({status})"

class JobDescription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, related_name='job_descriptions')
    job_role = models.ForeignKey(JobRole, on_delete=models.SET_NULL, blank=True, null=True, help_text="Reference predefined job role if applicable")
    title = models.CharField(max_length=200)
    raw_text = models.TextField(help_text="Full pasted job description text")
    extracted_skills = models.JSONField(default=dict, blank=True, help_text="JSON dictionary of extracted skills {skill_name: matched_text}")
    embedding = models.TextField(blank=True, null=True, help_text="SBERT 384d embedding serialized as JSON array")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class AnalysisResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analyses')
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name='analyses')
    job_description = models.ForeignKey(JobDescription, on_delete=models.CASCADE, related_name='analyses')
    
    # Detailed scoring breakdown
    overall_score = models.FloatField(default=0.0)
    semantic_score = models.FloatField(default=0.0)
    skill_score = models.FloatField(default=0.0)
    experience_score = models.FloatField(default=0.0)
    education_score = models.FloatField(default=0.0)
    project_score = models.FloatField(default=0.0)
    certification_score = models.FloatField(default=0.0)
    
    explanation = models.TextField(blank=True, null=True, help_text="Natural language explanation of suitability and gaps")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Match: {self.resume.filename} to {self.job_description.title} ({self.overall_score:.1f}%)"

class SkillGap(models.Model):
    STATUS_CHOICES = (
        ('matched', 'Matched'),
        ('missing', 'Missing'),
        ('partial', 'Partially Matched'),
        ('recommended', 'Recommended')
    )
    PRIORITY_CHOICES = (
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low')
    )
    analysis_result = models.ForeignKey(AnalysisResult, on_delete=models.CASCADE, related_name='skill_gaps')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='analysis_gaps')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES)
    explanation = models.TextField(blank=True, null=True, help_text="Why this skill is relevant and how to acquire it")

    class Meta:
        unique_together = ('analysis_result', 'skill')

    def __str__(self):
        return f"{self.analysis_result.id} - {self.skill.name} ({self.status})"
