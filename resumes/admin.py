from django.contrib import admin
from .models import Resume, Education, Experience, Skill, ResumeSkill

class EducationInline(admin.TabularInline):
    model = Education
    extra = 0

class ExperienceInline(admin.TabularInline):
    model = Experience
    extra = 0

class ResumeSkillInline(admin.TabularInline):
    model = ResumeSkill
    extra = 0
    raw_id_fields = ('skill',)

@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ('filename', 'user', 'file_size', 'uploaded_at')
    search_fields = ('filename', 'user__username', 'extracted_text')
    list_filter = ('uploaded_at', 'content_type')
    inlines = [EducationInline, ExperienceInline, ResumeSkillInline]

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    search_fields = ('name', 'category')
    list_filter = ('category',)

@admin.register(ResumeSkill)
class ResumeSkillAdmin(admin.ModelAdmin):
    list_display = ('resume', 'skill', 'matched_text')
    search_fields = ('resume__filename', 'skill__name', 'matched_text')
