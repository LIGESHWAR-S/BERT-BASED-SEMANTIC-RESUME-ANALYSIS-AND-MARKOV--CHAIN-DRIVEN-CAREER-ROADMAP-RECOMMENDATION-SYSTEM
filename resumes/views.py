import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, generics

from .models import Resume, Education, Experience, Skill, ResumeSkill
from .serializers import ResumeSerializer, ResumeDetailSerializer, SkillSerializer
from nlp_engine.parser import extract_text, detect_sections, extract_contact_info
from nlp_engine.extractor import SkillExtractor
from nlp_engine.embedder import SBERTModelManager
from jobs.models import AnalysisResult, JobRole

# === Helper for Parsing Sub-records from Section Text ===

def parse_education_heuristics(edu_text):
    """
    Tries to extract basic Education records from the education section text.
    """
    records = []
    if not edu_text:
        return records
        
    lines = [line.strip() for line in edu_text.split('\n') if line.strip()]
    
    # Very simple heuristic: search for university names and degrees in lines
    for line in lines:
        degree = None
        institution = None
        
        # Check degrees
        for deg in ["bachelor", "master", "ph.d", "phd", "b.s", "b.a", "m.s", "m.a", "bsc", "msc", "degree", "diploma", "btech", "mtech"]:
            if re_match := re_search_word(deg, line):
                degree = line[:re_match.end() + 20].strip() # Take the degree phrase
                break
                
        # Check institution keywords
        for inst in ["university", "college", "institute", "school", "academy"]:
            if re_match := re_search_word(inst, line):
                institution = line.strip()
                break
                
        if degree or institution:
            # Parse dates if any (e.g. 2018 - 2022)
            dates = re_find_years(line)
            start_date = str(dates[0]) if len(dates) > 0 else None
            end_date = str(dates[1]) if len(dates) > 1 else (str(dates[0]) if len(dates) == 1 else None)
            
            records.append({
                'degree': degree or "Degree / Certificate",
                'institution': institution or "Educational Institution",
                'field_of_study': "General Studies",
                'start_date': start_date,
                'end_date': end_date
            })
            
    # Default fallback if nothing was matched
    if not records:
        records.append({
            'degree': "Extracted Education (Details in Text)",
            'institution': "See Summary",
            'field_of_study': "N/A",
            'start_date': None,
            'end_date': None
        })
    return records

def parse_experience_heuristics(exp_text):
    """
    Tries to extract basic Job Experience records from the experience section text.
    """
    records = []
    if not exp_text:
        return records
        
    # Split by double newline to segment paragraphs
    paragraphs = [p.strip() for p in exp_text.split('\n\n') if p.strip()]
    if len(paragraphs) <= 1:
        # Fallback to single lines if not double-spaced
        paragraphs = [p.strip() for p in exp_text.split('\n') if p.strip() and len(p.strip()) > 30]
        
    for p in paragraphs[:5]: # Take top 5 entries max
        lines = p.split('\n')
        title_line = lines[0].strip()
        
        # Look for dates
        dates = re_find_years(p)
        start_date = str(dates[0]) if len(dates) > 0 else None
        end_date = str(dates[1]) if len(dates) > 1 else (str(dates[0]) if len(dates) == 1 else "Present")
        
        # Split title_line into title and company (often separated by at, |, -, or comma)
        company = "Company Name"
        title = title_line
        
        for separator in [" at ", " @ ", " - ", " | ", ", "]:
            if separator in title_line:
                parts = title_line.split(separator, 1)
                title = parts[0].strip()
                company = parts[1].strip()
                break
                
        records.append({
            'job_title': title[:100],
            'company': company[:100],
            'location': "Remote/Office",
            'start_date': start_date,
            'end_date': end_date,
            'description': p
        })
        
    if not records:
        records.append({
            'job_title': "Extracted Experience",
            'company': "See Summary",
            'location': None,
            'start_date': None,
            'end_date': None,
            'description': exp_text
        })
    return records

import re
def re_search_word(word, text):
    return re.search(r'\b' + re.escape(word) + r'\b', text, re.IGNORECASE)

def re_find_years(text):
    # Find numbers that look like years (e.g. 2015, 2022) or words like "Present"
    years = re.findall(r'\b(19\d{2}|20\d{2})\b', text)
    return [int(y) for y in years]


# === HTML Template Views ===

@login_required
def dashboard_home(request):
    """
    Renders main User Dashboard with resume stats and list.
    """
    resumes = Resume.objects.filter(user=request.user).order_by('-uploaded_at')
    analyses = AnalysisResult.objects.filter(user=request.user).order_by('-created_at')
    
    # Calculate some stats
    total_resumes = resumes.count()
    total_analyses = analyses.count()
    
    latest_resume = resumes.first()
    latest_analysis = analyses.first()
    
    context = {
        'resumes': resumes,
        'analyses': analyses,
        'total_resumes': total_resumes,
        'total_analyses': total_analyses,
        'latest_resume': latest_resume,
        'latest_analysis': latest_analysis,
    }
    return render(request, 'dashboard/index.html', context)

@login_required
def resume_upload_view(request):
    """
    Renders/handles Resume Upload Form.
    """
    if request.method == 'POST':
        if 'resume_file' not in request.FILES:
            messages.error(request, "No file uploaded.")
            return render(request, 'dashboard/upload.html')
            
        uploaded_file = request.FILES['resume_file']
        
        # Validations
        filename = uploaded_file.name
        ext = filename.split('.')[-1].lower()
        if ext not in ['pdf', 'docx', 'txt']:
            messages.error(request, f"Unsupported file type .{ext}. Please upload a PDF, DOCX, or TXT file.")
            return render(request, 'dashboard/upload.html')
            
        if uploaded_file.size > 5 * 1024 * 1024: # 5MB limit
            messages.error(request, "File size exceeds 5MB limit.")
            return render(request, 'dashboard/upload.html')
            
        if uploaded_file.size == 0:
            messages.error(request, "Uploaded file is empty.")
            return render(request, 'dashboard/upload.html')
            
        try:
            # Wrap processing in a transaction
            with transaction.atomic():
                # Read file bytes
                file_bytes = uploaded_file.read()
                
                # Extract text (this also serves to validate file corruption)
                try:
                    raw_text = extract_text(file_bytes, filename)
                except Exception as e:
                    messages.error(request, "Could not extract text. The file might be corrupted.")
                    return render(request, 'dashboard/upload.html')
                    
                if not raw_text.strip():
                    messages.error(request, "No text content could be extracted from the resume.")
                    return render(request, 'dashboard/upload.html')
                
                # Create Resume instance
                resume = Resume(
                    user=request.user,
                    file=uploaded_file,
                    filename=filename,
                    file_size=uploaded_file.size,
                    content_type=uploaded_file.content_type,
                    extracted_text=raw_text
                )
                
                # Section detection
                parsed_sections = detect_sections(raw_text)
                resume.sections = parsed_sections
                resume.summary = parsed_sections.get('summary', '')[:1000]
                
                # Contact info extraction
                contact = extract_contact_info(raw_text)
                resume.contact_info = contact
                
                # SBERT Embedding generation
                embedder = SBERTModelManager()
                # Create a representative text of the resume: summary + skills + experience
                rep_text = f"Summary: {resume.summary or ''}\nSkills: {parsed_sections.get('skills', '')}\nExperience: {parsed_sections.get('experience', '')}"
                embedding_vector = embedder.get_embedding(rep_text)
                resume.embedding = embedder.serialize_embedding(embedding_vector)
                
                resume.save()
                
                # Skill Extraction & Normalization
                extractor = SkillExtractor()
                extracted_skills = extractor.extract_skills(raw_text)
                
                # Link skills to Resume
                for skill_name, raw_match in extracted_skills.items():
                    skill, _ = Skill.objects.get_or_create(
                        name=skill_name,
                        defaults={'category': extractor.get_category(skill_name)}
                    )
                    ResumeSkill.objects.get_or_create(
                        resume=resume,
                        skill=skill,
                        defaults={'matched_text': raw_match}
                    )
                    
                # Extract and populate Education & Experience sub-records
                edu_data = parse_education_heuristics(parsed_sections.get('education', ''))
                for edu in edu_data:
                    Education.objects.create(resume=resume, **edu)
                    
                exp_data = parse_experience_heuristics(parsed_sections.get('experience', ''))
                for exp in exp_data:
                    Experience.objects.create(resume=resume, **exp)
                    
                # Try to auto-detect current job title from experience
                if exp_data:
                    request.user.profile.current_role = exp_data[0]['job_title']
                    # Simple heuristic: experience years calculation
                    request.user.profile.experience_years = len(exp_data) * 1.5 
                    request.user.profile.save()
                    
            messages.success(request, f"Resume '{filename}' uploaded and parsed successfully!")
            return redirect('resume_detail', resume_id=resume.id)
            
        except Exception as e:
            messages.error(request, f"An error occurred during parsing: {str(e)}")
            return render(request, 'dashboard/upload.html')
            
    return render(request, 'dashboard/upload.html')

@login_required
def resume_detail_view(request, resume_id):
    resume = get_object_or_404(Resume, id=resume_id, user=request.user)
    job_roles = JobRole.objects.all()
    context = {
        'resume': resume,
        'job_roles': job_roles,
    }
    return render(request, 'dashboard/resume_detail.html', context)


# === REST API Viewsets / Views ===

class ResumeUploadAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if 'resume_file' not in request.FILES:
            return Response({"error": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)
            
        uploaded_file = request.FILES['resume_file']
        filename = uploaded_file.name
        
        ext = filename.split('.')[-1].lower()
        if ext not in ['pdf', 'docx', 'txt']:
            return Response({"error": "Unsupported file extension."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            with transaction.atomic():
                file_bytes = uploaded_file.read()
                raw_text = extract_text(file_bytes, filename)
                
                resume = Resume.objects.create(
                    user=request.user,
                    file=uploaded_file,
                    filename=filename,
                    file_size=uploaded_file.size,
                    content_type=uploaded_file.content_type,
                    extracted_text=raw_text
                )
                
                sections = detect_sections(raw_text)
                resume.sections = sections
                resume.summary = sections.get('summary', '')[:1000]
                resume.contact_info = extract_contact_info(raw_text)
                
                embedder = SBERTModelManager()
                rep_text = f"Summary: {resume.summary or ''}\nSkills: {sections.get('skills', '')}\nExperience: {sections.get('experience', '')}"
                embedding_vector = embedder.get_embedding(rep_text)
                resume.embedding = embedder.serialize_embedding(embedding_vector)
                resume.save()
                
                extractor = SkillExtractor()
                extracted_skills = extractor.extract_skills(raw_text)
                for skill_name, raw_match in extracted_skills.items():
                    skill, _ = Skill.objects.get_or_create(
                        name=skill_name,
                        defaults={'category': extractor.get_category(skill_name)}
                    )
                    ResumeSkill.objects.get_or_create(resume=resume, skill=skill, defaults={'matched_text': raw_match})
                    
                edu_data = parse_education_heuristics(sections.get('education', ''))
                for edu in edu_data:
                    Education.objects.create(resume=resume, **edu)
                    
                exp_data = parse_experience_heuristics(sections.get('experience', ''))
                for exp in exp_data:
                    Experience.objects.create(resume=resume, **exp)
                    
            serializer = ResumeDetailSerializer(resume)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": f"Failed to process resume: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ResumeAnalyzeAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        resume_id = request.data.get('resume_id')
        resume = get_object_or_404(Resume, id=resume_id, user=request.user)
        # Re-run SBERT generation if requested
        embedder = SBERTModelManager()
        sections = resume.sections
        rep_text = f"Summary: {resume.summary or ''}\nSkills: {sections.get('skills', '')}\nExperience: {sections.get('experience', '')}"
        embedding_vector = embedder.get_embedding(rep_text)
        resume.embedding = embedder.serialize_embedding(embedding_vector)
        resume.save()
        
        return Response({"message": "Resume re-analyzed successfully.", "id": resume.id})

class SkillListAPIView(generics.ListAPIView):
    queryset = Skill.objects.all().order_by('name')
    serializer_class = SkillSerializer
    permission_classes = [permissions.IsAuthenticated]
