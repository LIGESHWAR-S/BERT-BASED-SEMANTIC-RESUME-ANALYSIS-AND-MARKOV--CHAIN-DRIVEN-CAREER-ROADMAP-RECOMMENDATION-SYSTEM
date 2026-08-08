from django.contrib import admin
from .models import JobRole, JobSkill, JobDescription, AnalysisResult, SkillGap

class JobSkillInline(admin.TabularInline):
    model = JobSkill
    extra = 0
    raw_id_fields = ('skill',)

class SkillGapInline(admin.TabularInline):
    model = SkillGap
    extra = 0
    raw_id_fields = ('skill',)

@admin.register(JobRole)
class JobRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'industry', 'minimum_experience')
    search_fields = ('name', 'industry')
    list_filter = ('industry', 'minimum_experience')
    inlines = [JobSkillInline]

@admin.register(JobDescription)
class JobDescriptionAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'job_role', 'created_at')
    search_fields = ('title', 'user__username', 'raw_text')
    list_filter = ('created_at',)

@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'resume', 'job_description', 'overall_score', 'created_at')
    search_fields = ('resume__filename', 'job_description__title', 'explanation')
    list_filter = ('overall_score', 'created_at')
    inlines = [SkillGapInline]

@admin.register(SkillGap)
class SkillGapAdmin(admin.ModelAdmin):
    list_display = ('analysis_result', 'skill', 'status', 'priority')
    search_fields = ('analysis_result__id', 'skill__name', 'status')
    list_filter = ('status', 'priority')
