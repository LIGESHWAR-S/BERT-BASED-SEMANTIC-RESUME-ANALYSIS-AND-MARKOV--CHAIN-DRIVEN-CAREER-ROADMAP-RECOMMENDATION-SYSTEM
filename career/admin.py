from django.contrib import admin
from .models import CareerState, CareerTransition, CareerRecommendation

@admin.register(CareerState)
class CareerStateAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(CareerTransition)
class CareerTransitionAdmin(admin.ModelAdmin):
    list_display = ('from_state', 'to_state', 'transition_count', 'probability', 'industry')
    search_fields = ('from_state__name', 'to_state__name', 'industry')
    list_filter = ('industry',)
    raw_id_fields = ('from_state', 'to_state')

@admin.register(CareerRecommendation)
class CareerRecommendationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'current_role', 'target_role', 'created_at')
    search_fields = ('user__username', 'current_role', 'target_role')
    list_filter = ('created_at',)
