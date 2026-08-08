from django.db import models
from django.contrib.auth.models import User

class CareerState(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class CareerTransition(models.Model):
    from_state = models.ForeignKey(CareerState, on_delete=models.CASCADE, related_name='outgoing_transitions')
    to_state = models.ForeignKey(CareerState, on_delete=models.CASCADE, related_name='incoming_transitions')
    transition_count = models.IntegerField(default=1)
    probability = models.FloatField(default=0.0)
    industry = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        unique_together = ('from_state', 'to_state')

    def __str__(self):
        return f"{self.from_state.name} -> {self.to_state.name} ({self.probability:.2%})"

class CareerRecommendation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='career_recommendations')
    current_role = models.CharField(max_length=100)
    target_role = models.CharField(max_length=100)
    
    roadmap_data = models.JSONField(help_text="Steps and metrics representing the primary progression sequence")
    alternative_paths = models.JSONField(help_text="Alternative next roles with transition probabilities and compatibility scores")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Recommendation for {self.user.username} (from {self.current_role} to {self.target_role})"
