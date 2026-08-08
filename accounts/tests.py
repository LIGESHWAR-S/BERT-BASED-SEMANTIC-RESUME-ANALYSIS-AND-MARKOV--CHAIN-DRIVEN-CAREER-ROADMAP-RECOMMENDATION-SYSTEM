from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from accounts.models import UserProfile

class AccountsTestCase(TestCase):
    def setUp(self):
        self.username = "testuser"
        self.password = "securepassword123"
        self.email = "testuser@example.com"
        
    def test_user_profile_creation_signal(self):
        """
        Tests that creating a User automatically spawns a UserProfile.
        """
        user = User.objects.create_user(username=self.username, password=self.password, email=self.email)
        self.assertIsNotNone(user.profile)
        self.assertEqual(user.profile.current_role, None)
        self.assertEqual(user.profile.experience_years, 0.0)

    def test_user_registration_view(self):
        """
        Tests registration form submission.
        """
        url = reverse('register')
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302) # Redirects to dashboard
        self.assertTrue(User.objects.filter(username='newuser').exists())
        
    def test_user_login_view(self):
        """
        Tests login form submission.
        """
        user = User.objects.create_user(username=self.username, password=self.password, email=self.email)
        url = reverse('login')
        data = {
            'username': self.username,
            'password': self.password
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302) # Redirects to dashboard
        
    def test_profile_update_view(self):
        """
        Tests profile updating.
        """
        user = User.objects.create_user(username=self.username, password=self.password, email=self.email)
        self.client.login(username=self.username, password=self.password)
        url = reverse('profile')
        data = {
            'current_role': 'Data Analyst',
            'experience_years': '3.5',
            'bio': 'Test bio description.'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.current_role, 'Data Analyst')
        self.assertEqual(float(user.profile.experience_years), 3.5)
        self.assertEqual(user.profile.bio, 'Test bio description.')
