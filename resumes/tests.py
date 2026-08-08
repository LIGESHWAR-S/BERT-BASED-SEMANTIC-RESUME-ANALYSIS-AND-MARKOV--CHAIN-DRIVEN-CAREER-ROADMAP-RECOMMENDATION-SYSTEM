import json
import numpy as np
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth.models import User
from resumes.models import Resume, Skill, ResumeSkill, Education, Experience
from nlp_engine.parser import detect_sections, clean_text, extract_contact_info
from nlp_engine.extractor import SkillExtractor
from nlp_engine.embedder import SBERTModelManager

class ResumesTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="resuser", password="password123")
        self.raw_resume_text = """
        John Doe
        Email: john.doe@example.com
        Phone: 123-456-7890
        GitHub: github.com/johndoe
        
        Summary
        Experienced software engineer specialized in back-end architectures and python web development.
        
        Experience
        Software Developer at Antigravity Inc.
        2020 - 2023
        Developed REST APIs and Python Django applications. Handled Docker containers and AWS EC2 deployments.
        
        Education
        Bachelor of Science in Computer Science
        Antigravity University (2016 - 2020)
        
        Skills
        Python, Django, AWS, MS Excel, Git, JavaScript, Communication
        """
        
    def test_clean_text(self):
        self.assertEqual(clean_text("Hello\r\nWorld"), "Hello\nWorld")
        self.assertEqual(clean_text("  Spaced  Text  "), "Spaced  Text")

    def test_section_detection(self):
        sections = detect_sections(self.raw_resume_text)
        self.assertEqual(sections['contact'].strip(), "John Doe\n        Email: john.doe@example.com\n        Phone: 123-456-7890\n        GitHub: github.com/johndoe")
        self.assertEqual(sections['summary'].strip(), "Experienced software engineer specialized in back-end architectures and python web development.")
        self.assertTrue("Software Developer" in sections['experience'])
        self.assertTrue("Bachelor of Science" in sections['education'])
        self.assertTrue("Python, Django" in sections['skills'])

    def test_contact_extraction(self):
        contact = extract_contact_info(self.raw_resume_text)
        self.assertIn("john.doe@example.com", contact['emails'])
        self.assertIn("123-456-7890", contact['phones'])
        self.assertIn("github.com/johndoe", contact['links'])

    @patch('nlp_engine.extractor.SkillExtractor.load_skills_from_csv')
    def test_skill_extraction_and_normalization(self, mock_load):
        # Manually inject skills to verify matching and normalization
        extractor = SkillExtractor()
        extractor.skills_dict = {
            'python': 'Python',
            'django': 'Django',
            'aws': 'AWS',
            'ms excel': 'Microsoft Excel',
            'excel': 'Microsoft Excel',
            'git': 'Git'
        }
        extractor.sorted_aliases = ['microsoft excel', 'ms excel', 'django', 'python', 'excel', 'aws', 'git']
        
        text = "I have Python, Django and MS Excel skills with Git versions."
        extracted = extractor.extract_skills(text)
        
        self.assertIn("Python", extracted)
        self.assertIn("Django", extracted)
        self.assertIn("Microsoft Excel", extracted) # MS Excel normalized to Microsoft Excel
        self.assertIn("Git", extracted)
        
    @patch('sentence_transformers.SentenceTransformer')
    def test_embedder_mocked(self, mock_sbert):
        # Mock SBERT behavior to avoid network calls and download
        mock_instance = MagicMock()
        mock_instance.encode.return_value = np.ones(384, dtype=np.float32) * 0.5
        mock_sbert.return_value = mock_instance
        
        manager = SBERTModelManager()
        # Force reload/get_model mock hook
        manager.model = mock_instance
        
        emb = manager.get_embedding("Test Sentence")
        self.assertEqual(emb.shape, (384,))
        self.assertTrue(np.allclose(emb, 0.5))
        
        # Test similarity of equal vectors
        sim = manager.calculate_similarity(emb, emb)
        self.assertAlmostEqual(sim, 1.0)
        
        # Test serialization
        serialized = manager.serialize_embedding(emb)
        deserialized = manager.deserialize_embedding(serialized)
        self.assertTrue(np.allclose(emb, deserialized))
