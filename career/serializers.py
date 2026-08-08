from rest_framework import serializers
from .models import CareerRecommendation

class CareerRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CareerRecommendation
        fields = ['id', 'current_role', 'target_role', 'roadmap_data', 'alternative_paths', 'created_at']
