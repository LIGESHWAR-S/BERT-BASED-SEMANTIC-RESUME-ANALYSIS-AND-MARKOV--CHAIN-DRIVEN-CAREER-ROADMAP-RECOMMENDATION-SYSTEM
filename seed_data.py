import os
import django
import csv
import numpy as np

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'resume_analyzer.settings')
django.setup()

from resumes.models import Skill
from jobs.models import JobRole, JobSkill
from career.models import CareerState, CareerTransition
from nlp_engine.embedder import SBERTModelManager

def seed_skills():
    print("Seeding skills...")
    csv_path = 'data/skills.csv'
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return
        
    count = 0
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['skill_name'].strip()
            category = row['category'].strip()
            
            skill, created = Skill.objects.get_or_create(
                name=name,
                defaults={'category': category}
            )
            if created:
                count += 1
                
    print(f"Successfully seeded {count} new skills.")

def seed_job_roles():
    print("Seeding job roles and generating embeddings...")
    csv_path = 'data/job_roles.csv'
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return
        
    embedder = SBERTModelManager()
    
    count = 0
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            role_name = row['job_role'].strip()
            industry = row['industry'].strip()
            min_exp = int(row['minimum_experience'].strip())
            
            # Extract skills lists
            req_skills = [s.strip() for s in row['required_skills'].split('|') if s.strip()]
            pref_skills = [s.strip() for s in row['preferred_skills'].split('|') if s.strip()]
            
            # Combine details to create a rich job description text for SBERT embedding
            job_text = f"Job Role: {role_name}. Industry: {industry}. Required Skills: {', '.join(req_skills)}. Preferred Skills: {', '.join(pref_skills)}."
            embedding_vector = embedder.get_embedding(job_text)
            serialized_emb = embedder.serialize_embedding(embedding_vector)
            
            # Create or update JobRole
            job_role, created = JobRole.objects.update_or_create(
                name=role_name,
                defaults={
                    'industry': industry,
                    'minimum_experience': min_exp,
                    'embedding': serialized_emb
                }
            )
            
            # Link required skills
            for s_name in req_skills:
                try:
                    skill = Skill.objects.get(name=s_name)
                    JobSkill.objects.update_or_create(
                        job_role=job_role,
                        skill=skill,
                        defaults={'is_required': True}
                    )
                except Skill.DoesNotExist:
                    print(f"Warning: Skill '{s_name}' required for '{role_name}' does not exist in Skills database.")
                    
            # Link preferred skills
            for s_name in pref_skills:
                try:
                    skill = Skill.objects.get(name=s_name)
                    JobSkill.objects.update_or_create(
                        job_role=job_role,
                        skill=skill,
                        defaults={'is_required': False}
                    )
                except Skill.DoesNotExist:
                    print(f"Warning: Skill '{s_name}' preferred for '{role_name}' does not exist in Skills database.")
            
            count += 1
            
    print(f"Successfully seeded {count} job roles.")

def seed_transitions():
    print("Seeding career states and transitions...")
    csv_path = 'data/career_transitions.csv'
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return
        
    # Read raw transition data
    transitions_data = []
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            from_role = row['from_role'].strip()
            to_role = row['to_role'].strip()
            count = int(row['transition_count'].strip())
            industry = row['industry'].strip()
            transitions_data.append((from_role, to_role, count, industry))
            
            # Ensure CareerStates exist
            CareerState.objects.get_or_create(name=from_role)
            CareerState.objects.get_or_create(name=to_role)
            
    # Save/Update Transition counts
    for from_role, to_role, count, industry in transitions_data:
        from_state = CareerState.objects.get(name=from_role)
        to_state = CareerState.objects.get(name=to_role)
        
        CareerTransition.objects.update_or_create(
            from_state=from_state,
            to_state=to_state,
            defaults={
                'transition_count': count,
                'industry': industry
            }
        )
        
    # Calculate transition probabilities
    print("Normalizing Markov Chain transition probabilities...")
    states = CareerState.objects.all()
    for state in states:
        outgoing = CareerTransition.objects.filter(from_state=state)
        total_count = sum(t.transition_count for t in outgoing)
        if total_count > 0:
            for t in outgoing:
                t.probability = t.transition_count / total_count
                t.save()
                
    print(f"Successfully seeded career states and transition probabilities.")

if __name__ == '__main__':
    seed_skills()
    seed_job_roles()
    seed_transitions()
    print("Database seeding completed successfully.")
