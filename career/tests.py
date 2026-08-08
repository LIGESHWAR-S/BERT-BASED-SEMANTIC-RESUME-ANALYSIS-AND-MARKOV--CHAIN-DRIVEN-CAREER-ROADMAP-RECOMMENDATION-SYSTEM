import json
import numpy as np
from django.test import TestCase
from django.contrib.auth.models import User
from resumes.models import Resume, Skill, ResumeSkill
from jobs.models import JobRole, JobSkill
from career.models import CareerState, CareerTransition
from nlp_engine.markov import MarkovCareerRecommender
from career.views import compute_career_recommendations

class CareerTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="caruser", password="password123")
        self.user.profile.current_role = "Junior Developer"
        self.user.profile.experience_years = 2.0
        self.user.profile.save()
        
        self.resume = Resume.objects.create(
            user=self.user,
            filename="carresume.pdf",
            file_size=1024,
            content_type="application/pdf",
            embedding=json.dumps((np.ones(384, dtype=np.float32) * 0.5).tolist())
        )
        
        # Setup skills
        self.python = Skill.objects.create(name="Python", category="Programming Languages")
        self.django = Skill.objects.create(name="Django", category="Frameworks")
        ResumeSkill.objects.create(resume=self.resume, skill=self.python, matched_text="python")
        ResumeSkill.objects.create(resume=self.resume, skill=self.django, matched_text="django")
        
        # Setup job roles and skills
        self.dev = JobRole.objects.create(
            name="Software Developer",
            industry="Software Development",
            minimum_experience=2,
            embedding=json.dumps((np.ones(384, dtype=np.float32) * 0.5).tolist())
        )
        JobSkill.objects.create(job_role=self.dev, skill=self.python, is_required=True)
        JobSkill.objects.create(job_role=self.dev, skill=self.django, is_required=True)

        self.lead = JobRole.objects.create(
            name="Tech Lead",
            industry="Software Development",
            minimum_experience=6,
            embedding=json.dumps((np.ones(384, dtype=np.float32) * 0.5).tolist())
        )
        self.leadership = Skill.objects.create(name="Leadership", category="Soft Skills")
        JobSkill.objects.create(job_role=self.lead, skill=self.leadership, is_required=True)
        
        # Set up Career Transitions
        self.s_jun = CareerState.objects.create(name="Junior Developer")
        self.s_dev = CareerState.objects.create(name="Software Developer")
        self.s_lead = CareerState.objects.create(name="Tech Lead")
        
        # Transitions
        # Junior -> Dev (80% prob), Junior -> Tech Lead (20% prob)
        CareerTransition.objects.create(from_state=self.s_jun, to_state=self.s_dev, transition_count=8, probability=0.8)
        CareerTransition.objects.create(from_state=self.s_jun, to_state=self.s_lead, transition_count=2, probability=0.2)
        # Dev -> Tech Lead (100% prob)
        CareerTransition.objects.create(from_state=self.s_dev, to_state=self.s_lead, transition_count=5, probability=1.0)

    def test_recommender_probabilities(self):
        transitions_query = CareerTransition.objects.all()
        recommender = MarkovCareerRecommender(transitions_query)
        
        prob_dev = recommender.get_transitions_from("Junior Developer")["Software Developer"]
        prob_lead = recommender.get_transitions_from("Junior Developer")["Tech Lead"]
        
        self.assertAlmostEqual(prob_dev, 0.8)
        self.assertAlmostEqual(prob_lead, 0.2)
        
    def test_recommender_roadmap(self):
        transitions_query = CareerTransition.objects.all()
        recommender = MarkovCareerRecommender(transitions_query)
        
        user_skills = ["Python", "Django"]
        user_emb = np.ones(384, dtype=np.float32) * 0.5
        
        job_roles_data = {
            'Software Developer': {
                'required_skills': ['Python', 'Django'],
                'embedding': user_emb
            },
            'Tech Lead': {
                'required_skills': ['Python', 'Django', 'Leadership'],
                'embedding': user_emb
            }
        }
        
        # Generate multi-step roadmap
        roadmap = recommender.generate_roadmap(
            current_role="Junior Developer",
            user_skills=user_skills,
            user_embedding=user_emb,
            job_roles_data=job_roles_data,
            embedder_manager=None,
            max_steps=2
        )
        
        # Path should go Junior Developer -> Software Developer -> Tech Lead
        self.assertEqual(len(roadmap), 2)
        self.assertEqual(roadmap[0]['role'], "Software Developer")
        self.assertEqual(roadmap[1]['role'], "Tech Lead")
        
    def test_recommender_view_logic(self):
        # Trigger compute_career_recommendations logic
        rec = compute_career_recommendations(
            user=self.user,
            resume=self.resume,
            current_role_override="Junior Developer"
        )
        
        self.assertEqual(rec.current_role, "Junior Developer")
        
        # Roadmap data steps
        # Step 0: Junior Developer (current)
        # Step 1: Software Developer (next)
        # Step 2: Tech Lead (future)
        self.assertEqual(len(rec.roadmap_data), 3)
        self.assertEqual(rec.roadmap_data[0]['role'], "Junior Developer")
        self.assertEqual(rec.roadmap_data[1]['role'], "Software Developer")
        self.assertEqual(rec.roadmap_data[2]['role'], "Tech Lead")
        
        # Verify that "Tech Lead" step has "Leadership" as a missing skill
        self.assertIn("Leadership", rec.roadmap_data[2]['explanation'])
