import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, generics

from resumes.models import Resume, Skill, ResumeSkill, Education, Experience
from .models import JobRole, JobSkill, JobDescription, AnalysisResult, SkillGap
from .serializers import (
    JobRoleSerializer, JobDescriptionSerializer, 
    AnalysisResultSerializer, SkillGapSerializer
)
from nlp_engine.extractor import SkillExtractor
from nlp_engine.embedder import SBERTModelManager

# === Heuristics for Experience & Education Match ===

def calculate_experience_score(resume, required_experience):
    """
    Compares resume experience years to the job's minimum experience.
    """
    if required_experience <= 0:
        return 1.0
        
    # Get user experience from profile
    user_exp = float(resume.user.profile.experience_years)
    if user_exp >= required_experience:
        return 1.0
    return float(user_exp / required_experience)

def calculate_education_score(resume, job_text_lower):
    """
    Heuristic to score education match. Searches for degree requirements in job text 
    and checks if the resume education records meet them.
    """
    # Detect if job requires PhD/Master/Bachelor
    requires_phd = "phd" in job_text_lower or "ph.d" in job_text_lower or "doctorate" in job_text_lower
    requires_master = "master" in job_text_lower or "m.s." in job_text_lower or "mba" in job_text_lower or "postgraduate" in job_text_lower
    requires_bachelor = "bachelor" in job_text_lower or "b.s." in job_text_lower or "undergraduate" in job_text_lower or "btech" in job_text_lower
    
    user_degrees = [edu.degree.lower() for edu in resume.education_records.all() if edu.degree]
    user_text = " ".join(user_degrees)
    
    has_phd = "phd" in user_text or "ph.d" in user_text or "doctor" in user_text
    has_master = "master" in user_text or "m.s" in user_text or "mba" in user_text or "mtech" in user_text
    has_bachelor = "bachelor" in user_text or "b.s" in user_text or "btech" in user_text or "bsc" in user_text
    
    if requires_phd:
        return 1.0 if has_phd else (0.6 if has_master else 0.3)
    if requires_master:
        return 1.0 if (has_master or has_phd) else (0.7 if has_bachelor else 0.4)
    if requires_bachelor:
        return 1.0 if (has_bachelor or has_master or has_phd) else 0.5
        
    return 1.0 # Default if no specific education mentioned

def calculate_project_score(resume, job_embedding, embedder):
    """
    Checks semantic similarity of the resume's Projects section against the job embedding.
    """
    project_text = resume.sections.get('projects', '')
    if not project_text.strip():
        return 0.5 # Baseline default if no project section
        
    proj_embedding = embedder.get_embedding(project_text)
    similarity = embedder.calculate_similarity(proj_embedding, job_embedding)
    return similarity


# === Core Match Logic ===

def perform_matching(resume, job_desc):
    """
    Core function that matches a Resume against a JobDescription.
    Creates and returns the AnalysisResult (unsaved, to allow transactional wrappings).
    """
    embedder = SBERTModelManager()
    
    # 1. Semantic Similarity Score
    resume_emb = embedder.deserialize_embedding(resume.embedding)
    job_emb = embedder.deserialize_embedding(job_desc.embedding)
    semantic_score = embedder.calculate_similarity(resume_emb, job_emb)
    
    # 2. Skill Match Score
    # Extract job required and preferred skills
    job_skills_data = job_desc.extracted_skills # dict: {skill_name: raw_text}
    
    user_skills = {rs.skill.name for rs in resume.resume_skills.all()}
    
    # Predefined role evaluation
    job_role = job_desc.job_role
    required_skills = set()
    preferred_skills = set()
    
    if job_role:
        for js in JobSkill.objects.filter(job_role=job_role):
            if js.is_required:
                required_skills.add(js.skill.name)
            else:
                preferred_skills.add(js.skill.name)
    else:
        # Fallback for custom pasted job description: treat all extracted skills as required
        required_skills = set(job_skills_data.keys())
        
    total_skills_to_evaluate = required_skills.union(preferred_skills)
    
    if total_skills_to_evaluate:
        matched_required = user_skills.intersection(required_skills)
        matched_preferred = user_skills.intersection(preferred_skills)
        
        # Weighted skill score: required matched = 1.0 weight, preferred matched = 0.5 weight
        total_weight = len(required_skills) * 1.0 + len(preferred_skills) * 0.5
        matched_weight = len(matched_required) * 1.0 + len(matched_preferred) * 0.5
        
        skill_score = float(matched_weight / total_weight) if total_weight > 0 else 1.0
    else:
        skill_score = 0.5 # Baseline
        
    # 3. Experience Score
    min_exp = job_role.minimum_experience if job_role else 1
    experience_score = calculate_experience_score(resume, min_exp)
    
    # 4. Education Score
    education_score = calculate_education_score(resume, job_desc.raw_text.lower())
    
    # 5. Project Relevance Score
    project_score = calculate_project_score(resume, job_emb, embedder)
    
    # Certification Relevance Score (calculated from certifications section similarity)
    cert_text = resume.sections.get('certifications', '')
    if cert_text.strip():
        cert_emb = embedder.get_embedding(cert_text)
        certification_score = embedder.calculate_similarity(cert_emb, job_emb)
    else:
        certification_score = 0.5 # default
        
    # Combine scores with weights from settings
    weights = getattr(settings, 'NLP_MATCH_WEIGHTS', {
        'semantic': 0.40,
        'skill': 0.30,
        'experience': 0.10,
        'education': 0.10,
        'project': 0.10
    })
    
    # Let's adjust weight matching if project is a portion, the default is:
    # 40% semantic, 30% skill, 10% exp, 10% edu, 10% project/cert combined
    # Let's use:
    overall_score = (
        weights['semantic'] * semantic_score +
        weights['skill'] * skill_score +
        weights['experience'] * experience_score +
        weights['education'] * education_score +
        weights['project'] * (project_score * 0.7 + certification_score * 0.3)
    ) * 100.0 # Convert to percentage
    
    # Generate Natural Language Explanation
    matched_skills_str = ", ".join(list(user_skills.intersection(total_skills_to_evaluate))[:6])
    missing_required = required_skills.difference(user_skills)
    missing_skills_str = ", ".join(list(missing_required)[:6])
    
    fit_level = "strong" if overall_score >= 80 else ("moderate" if overall_score >= 55 else "weak")
    
    explanation_text = f"Your profile shows a {fit_level} match ({overall_score:.1f}%) for the {job_desc.title} role. "
    
    if matched_skills_str:
        explanation_text += f"Key matched skills contributing to this match include: {matched_skills_str}. "
    else:
        explanation_text += "There were no primary technical keyword matches detected. "
        
    if missing_skills_str:
        explanation_text += f"Critical skill gaps identified are: {missing_skills_str}. Developing competencies in these areas will significantly improve your profile suitability. "
    else:
        explanation_text += "You possess all key technical requirements listed in the job description! "
        
    if experience_score < 1.0:
        explanation_text += f"The role prefers at least {min_exp} years of experience, while your profile lists around {resume.user.profile.experience_years} years. "
        
    # Create the object
    result = AnalysisResult(
        user=resume.user,
        resume=resume,
        job_description=job_desc,
        overall_score=overall_score,
        semantic_score=semantic_score * 100.0,
        skill_score=skill_score * 100.0,
        experience_score=experience_score * 100.0,
        education_score=education_score * 100.0,
        project_score=project_score * 100.0,
        certification_score=certification_score * 100.0,
        explanation=explanation_text
    )
    return result, required_skills, preferred_skills


# === HTML Template Views ===

@login_required
def match_view(request):
    """
    Renders selection page and processes matches.
    """
    if request.method == 'POST':
        resume_id = request.POST.get('resume_id')
        job_role_id = request.POST.get('job_role_id')
        custom_jd = request.POST.get('custom_jd', '').strip()
        custom_title = request.POST.get('custom_title', '').strip()
        
        resume = get_object_or_404(Resume, id=resume_id, user=request.user)
        
        try:
            with transaction.atomic():
                job_role = None
                
                # Check if predefined job role or custom JD is used
                if job_role_id:
                    job_role = get_object_or_404(JobRole, id=job_role_id)
                    title = job_role.name
                    raw_text = job_role.description or f"Job Description for {job_role.name}."
                    
                    # Construct job description model
                    job_desc = JobDescription.objects.create(
                        user=request.user,
                        job_role=job_role,
                        title=title,
                        raw_text=raw_text,
                        embedding=job_role.embedding # Re-use cached embedding
                    )
                else:
                    if not custom_jd or not custom_title:
                        messages.error(request, "Please enter both a custom job title and description.")
                        return redirect('match_create')
                        
                    title = custom_title
                    raw_text = custom_jd
                    
                    # Extract skills for custom JD
                    extractor = SkillExtractor()
                    extracted_skills = extractor.extract_skills(raw_text)
                    
                    # Generate SBERT embedding for custom JD
                    embedder = SBERTModelManager()
                    embedding_vector = embedder.get_embedding(raw_text)
                    serialized_emb = embedder.serialize_embedding(embedding_vector)
                    
                    job_desc = JobDescription.objects.create(
                        user=request.user,
                        title=title,
                        raw_text=raw_text,
                        extracted_skills=extracted_skills,
                        embedding=serialized_emb
                    )
                    
                # Run core match algorithm
                result, required_skills, preferred_skills = perform_matching(resume, job_desc)
                result.save()
                
                # Populate Skill Gaps
                user_skills = {rs.skill.name for rs in resume.resume_skills.all()}
                
                # 1. Matched Skills
                all_target_skills = required_skills.union(preferred_skills)
                matched_skills = user_skills.intersection(all_target_skills)
                for s_name in matched_skills:
                    skill = Skill.objects.get(name=s_name)
                    SkillGap.objects.create(
                        analysis_result=result,
                        skill=skill,
                        status='matched',
                        priority='low',
                        explanation=f"You possess this skill as evidenced in your resume."
                    )
                    
                # 2. Missing Required Skills (Critical/High Priority)
                missing_required = required_skills.difference(user_skills)
                for s_name in missing_required:
                    skill = Skill.objects.get(name=s_name)
                    SkillGap.objects.create(
                        analysis_result=result,
                        skill=skill,
                        status='missing',
                        priority='critical' if len(required_skills) < 5 else 'high',
                        explanation=f"This skill is standard and required for the {title} role. Gaining this skill is highly recommended."
                    )
                    
                # 3. Missing Preferred Skills (Recommended/Medium/Low Priority)
                missing_preferred = preferred_skills.difference(user_skills)
                for s_name in missing_preferred:
                    skill = Skill.objects.get(name=s_name)
                    SkillGap.objects.create(
                        analysis_result=result,
                        skill=skill,
                        status='recommended',
                        priority='medium',
                        explanation=f"This is a preferred skill for {title}. Acquiring it will make your profile stand out."
                    )
                    
            messages.success(request, f"Semantic matching completed for '{title}'!")
            return redirect('analysis_detail', analysis_id=result.id)
            
        except Exception as e:
            messages.error(request, f"Failed to calculate match: {str(e)}")
            return redirect('match_create')
            
    resumes = Resume.objects.filter(user=request.user).order_by('-uploaded_at')
    job_roles = JobRole.objects.all().order_by('name')
    return render(request, 'dashboard/match_create.html', {
        'resumes': resumes,
        'job_roles': job_roles
    })

@login_required
def analysis_detail_view(request, analysis_id):
    analysis = get_object_or_404(AnalysisResult, id=analysis_id, user=request.user)
    skill_gaps = analysis.skill_gaps.all()
    
    # Classify into UI variables
    matched = [sg for sg in skill_gaps if sg.status == 'matched']
    missing = [sg for sg in skill_gaps if sg.status == 'missing']
    recommended = [sg for sg in skill_gaps if sg.status == 'recommended']
    
    dash_offset = 251.2 - (251.2 * (analysis.overall_score / 100.0))
    
    context = {
        'analysis': analysis,
        'matched_skills': matched,
        'missing_skills': missing,
        'recommended_skills': recommended,
        'dash_offset': dash_offset,
    }
    return render(request, 'dashboard/analysis_detail.html', context)


# === REST API Endpoints ===

class JobDescriptionAnalyzeAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        title = request.data.get('title')
        raw_text = request.data.get('raw_text')
        job_role_id = request.data.get('job_role_id')
        
        if not title or not raw_text:
            return Response({"error": "Title and description text are required."}, status=status.HTTP_400_BAD_REQUEST)
            
        extractor = SkillExtractor()
        extracted_skills = extractor.extract_skills(raw_text)
        
        embedder = SBERTModelManager()
        embedding_vector = embedder.get_embedding(raw_text)
        serialized_emb = embedder.serialize_embedding(embedding_vector)
        
        job_role = None
        if job_role_id:
            job_role = get_object_or_404(JobRole, id=job_role_id)
            
        job_desc = JobDescription.objects.create(
            user=request.user,
            job_role=job_role,
            title=title,
            raw_text=raw_text,
            extracted_skills=extracted_skills,
            embedding=serialized_emb
        )
        
        serializer = JobDescriptionSerializer(job_desc)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ResumeToJobMatchAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        resume_id = request.data.get('resume_id')
        job_desc_id = request.data.get('job_description_id')
        job_role_id = request.data.get('job_role_id')
        
        resume = get_object_or_404(Resume, id=resume_id, user=request.user)
        
        try:
            with transaction.atomic():
                if job_desc_id:
                    job_desc = get_object_or_404(JobDescription, id=job_desc_id, user=request.user)
                elif job_role_id:
                    job_role = get_object_or_404(JobRole, id=job_role_id)
                    job_desc = JobDescription.objects.create(
                        user=request.user,
                        job_role=job_role,
                        title=job_role.name,
                        raw_text=job_role.description or f"Job Description for {job_role.name}.",
                        embedding=job_role.embedding
                    )
                else:
                    return Response({"error": "Either job_description_id or job_role_id must be provided."}, status=status.HTTP_400_BAD_REQUEST)
                    
                result, required_skills, preferred_skills = perform_matching(resume, job_desc)
                result.save()
                
                # Populate gaps
                user_skills = {rs.skill.name for rs in resume.resume_skills.all()}
                all_target_skills = required_skills.union(preferred_skills)
                
                # Matched
                for s_name in user_skills.intersection(all_target_skills):
                    skill = Skill.objects.get(name=s_name)
                    SkillGap.objects.get_or_create(analysis_result=result, skill=skill, defaults={'status': 'matched', 'priority': 'low'})
                # Missing required
                for s_name in required_skills.difference(user_skills):
                    skill = Skill.objects.get(name=s_name)
                    SkillGap.objects.get_or_create(analysis_result=result, skill=skill, defaults={'status': 'missing', 'priority': 'high', 'explanation': f"Critical requirement for {job_desc.title}."})
                # Missing preferred
                for s_name in preferred_skills.difference(user_skills):
                    skill = Skill.objects.get(name=s_name)
                    SkillGap.objects.get_or_create(analysis_result=result, skill=skill, defaults={'status': 'recommended', 'priority': 'medium', 'explanation': f"Recommended requirement for {job_desc.title}."})
                    
            serializer = AnalysisResultSerializer(result)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": f"Failed matching: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SkillGapsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        analysis_id = request.query_params.get('analysis_id')
        analysis = get_object_or_404(AnalysisResult, id=analysis_id, user=request.user)
        gaps = analysis.skill_gaps.all()
        serializer = SkillGapSerializer(gaps, many=True)
        return Response(serializer.data)

class AnalysisResultRetrieveAPIView(generics.RetrieveAPIView):
    queryset = AnalysisResult.objects.all()
    serializer_class = AnalysisResultSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
