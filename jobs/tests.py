import json
import numpy as np
from django.test import TestCase
from django.contrib.auth.models import User
from resumes.models import Resume, Skill, ResumeSkill, Education
from jobs.models import JobRole, JobSkill, JobDescription, AnalysisResult, SkillGap
from jobs.views import calculate_experience_score, calculate_education_score, perform_matching

class JobsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="jobuser", password="password123")
        self.user.profile.experience_years = 4.0
        self.user.profile.save()
        
        # Create a mock Resume
        self.resume = Resume.objects.create(
            user=self.user,
            filename="myresume.pdf",
            file_size=1024,
            content_type="application/pdf",
            embedding=json.dumps((np.ones(384, dtype=np.float32) * 0.5).tolist()),
            sections={'projects': 'Build Django API with docker containers.'}
        )
        
        # Add education
        Education.objects.create(
            resume=self.resume,
            degree="Bachelor of Science",
            institution="Test University"
        )
        
        # Setup skills
        self.python = Skill.objects.create(name="Python", category="Programming Languages")
        self.django = Skill.objects.create(name="Django", category="Frameworks")
        self.docker = Skill.objects.create(name="Docker", category="Cloud & DevOps")
        self.sql = Skill.objects.create(name="SQL", category="Programming Languages")
        
        # Link skills to resume
        ResumeSkill.objects.create(resume=self.resume, skill=self.python, matched_text="python")
        ResumeSkill.objects.create(resume=self.resume, skill=self.django, matched_text="django")
        ResumeSkill.objects.create(resume=self.resume, skill=self.docker, matched_text="docker")

        # Create Job Role
        self.job_role = JobRole.objects.create(
            name="Backend Developer",
            industry="Software Development",
            minimum_experience=3,
            embedding=json.dumps((np.ones(384, dtype=np.float32) * 0.5).tolist())
        )
        JobSkill.objects.create(job_role=self.job_role, skill=self.python, is_required=True)
        JobSkill.objects.create(job_role=self.job_role, skill=self.django, is_required=True)
        JobSkill.objects.create(job_role=self.job_role, skill=self.docker, is_required=False)
        JobSkill.objects.create(job_role=self.job_role, skill=self.sql, is_required=True)

    def test_experience_scoring(self):
        # Candidate has 4 years, job needs 3 years
        score = calculate_experience_score(self.resume, 3)
        self.assertEqual(score, 1.0)
        
        # Job needs 5 years
        score = calculate_experience_score(self.resume, 5)
        self.assertEqual(score, 0.8)

    def test_education_scoring(self):
        # Job wants a PhD
        score = calculate_education_score(self.resume, "minimum requirement phd in cs")
        self.assertEqual(score, 0.3) # Candidate only has Bachelor
        
        # Job wants a Bachelor
        score = calculate_education_score(self.resume, "preferred qualification bachelor degree")
        self.assertEqual(score, 1.0)

    def test_matching_engine(self):
        # Construct a JobDescription representing our role
        job_desc = JobDescription.objects.create(
            user=self.user,
            job_role=self.job_role,
            title="Backend Developer",
            raw_text="Required: Python, Django, SQL. Preferred: Docker. Bachelor Degree. 3 years exp.",
            embedding=self.job_role.embedding
        )
        
        # Run perform_matching
        result, req, pref = perform_matching(self.resume, job_desc)
        
        self.assertIn("Python", req)
        self.assertIn("SQL", req)
        self.assertIn("Docker", pref)
        
        # Verify scores are correct
        self.assertEqual(result.experience_score, 100.0)
        self.assertEqual(result.semantic_score, 100.0) # Mocked embeddings are identical
        self.assertEqual(result.education_score, 100.0) # Matches Bachelor
        
        # Skills match: has Python, Django, Docker. Missing SQL (required).
        # Required skills = {Python, Django, SQL} (3). Preferred = {Docker} (1).
        # User has {Python, Django} from required, and {Docker} from preferred.
        # User matched weight = 2*1.0 + 1*0.5 = 2.5
        # Total weight = 3*1.0 + 1*0.5 = 3.5
        # Skill score should be 2.5 / 3.5 = ~71.4%
        self.assertAlmostEqual(result.skill_score, (2.5 / 3.5) * 100.0, places=1)
        self.assertTrue(result.overall_score > 50.0)
        self.assertTrue("SQL" in result.explanation)
