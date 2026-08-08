import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, generics

from resumes.models import Resume, Skill, ResumeSkill
from jobs.models import JobRole, JobSkill
from .models import CareerState, CareerTransition, CareerRecommendation
from .serializers import CareerRecommendationSerializer
from nlp_engine.markov import MarkovCareerRecommender
from nlp_engine.embedder import SBERTModelManager

# === Helper to Gather Predefined Job Roles Data ===

def get_job_roles_data_dict():
    """
    Constructs a dictionary of all predefined JobRoles with their required skills and embeddings,
    suitable for use by the Markov recommendation engine.
    """
    embedder = SBERTModelManager()
    roles = JobRole.objects.all()
    data = {}
    for r in roles:
        req_skills = [js.skill.name for js in r.job_skills.filter(is_required=True)]
        
        # Deserialize embedding
        emb = None
        if r.embedding:
            emb = embedder.deserialize_embedding(r.embedding)
            
        data[r.name] = {
            'required_skills': req_skills,
            'embedding': emb
        }
    return data


# === Certification Mapping Database ===

CERTIFICATION_MAPPING = {
    'Software Developer': [
        {'name': 'Python for Everybody Specialization', 'provider': 'Coursera / University of Michigan', 'type': 'Free (Audit)', 'duration': '2-3 months', 'info': 'Excellent foundation in python variables, data structures, and web scraping.'},
        {'name': 'AWS Certified Developer - Associate', 'provider': 'Amazon Web Services', 'type': 'Paid ($150)', 'duration': '1-2 months', 'info': 'Industry-standard validation for developing and maintaining AWS-based applications.'},
        {'name': 'Meta Back-End Developer Professional Certificate', 'provider': 'Coursera / Meta', 'type': 'Paid (Subscription)', 'duration': '3-6 months', 'info': 'Comprehensive track covering Django, Databases, APIs, and Version Control.'}
    ],
    'Junior Developer': [
        {'name': 'Responsive Web Design Certification', 'provider': 'freeCodeCamp', 'type': 'Free', 'duration': '1-2 months', 'info': 'Learn HTML, CSS, Flexbox, Grid, and responsive web design best practices.'},
        {'name': 'CS50\'s Introduction to Computer Science', 'provider': 'Harvard / edX', 'type': 'Free (Audit)', 'duration': '3 months', 'info': 'Legendary foundational course covering algorithms, memory structures, C, Python, and SQL.'}
    ],
    'Senior Developer': [
        {'name': 'AWS Certified Solutions Architect - Associate', 'provider': 'Amazon Web Services', 'type': 'Paid ($150)', 'duration': '2-3 months', 'info': 'Design resilient, high-performing, and secure architectures on AWS.'},
        {'name': 'Certified Kubernetes Application Developer (CKAD)', 'provider': 'The Linux Foundation', 'type': 'Paid ($375)', 'duration': '1-2 months', 'info': 'Validates ability to design, build, configure, and expose cloud-native applications.'}
    ],
    'Data Scientist': [
        {'name': 'IBM Data Science Professional Certificate', 'provider': 'Coursera / IBM', 'type': 'Paid (Subscription)', 'duration': '3-6 months', 'info': 'Master Python, SQL, data analysis, visualization, and machine learning models.'},
        {'name': 'Kaggle Machine Learning Track', 'provider': 'Kaggle', 'type': 'Free', 'duration': '2 weeks', 'info': 'Hands-on micro-courses for quick implementation of Random Forests and XGBoost.'}
    ],
    'Data Analyst': [
        {'name': 'Google Data Analytics Professional Certificate', 'provider': 'Coursera / Google', 'type': 'Free (Audit)', 'duration': '3-4 months', 'info': 'Learn spreadsheet basics, SQL queries, Tableau, and R programming.'},
        {'name': 'Microsoft Certified: Power BI Data Analyst Associate', 'provider': 'Microsoft', 'type': 'Paid ($165)', 'duration': '1 month', 'info': 'Demonstrate expert skills in data cleansing, modeling, and dashboard creation in Power BI.'}
    ],
    'Cloud Engineer': [
        {'name': 'AWS Certified Solutions Architect - Associate', 'provider': 'Amazon Web Services', 'type': 'Paid ($150)', 'duration': '2 months', 'info': 'Core certification covering compute, storage, networking, and security solutions on AWS.'},
        {'name': 'Google Cloud Associate Cloud Engineer', 'provider': 'Google Cloud', 'type': 'Paid ($125)', 'duration': '1-2 months', 'info': 'Covers deploying applications, monitoring operations, and managing enterprise projects on GCP.'}
    ],
    'DevOps Engineer': [
        {'name': 'Certified Kubernetes Administrator (CKA)', 'provider': 'The Linux Foundation', 'type': 'Paid ($375)', 'duration': '2-3 months', 'info': 'Validates capability to build, scale, and troubleshoot Kubernetes clusters.'},
        {'name': 'HashiCorp Certified: Terraform Associate', 'provider': 'HashiCorp', 'type': 'Paid ($70)', 'duration': '3-4 weeks', 'info': 'Validate skills in Infrastructure as Code (IaC) and Terraform cloud workflows.'}
    ],
    'Cybersecurity Analyst': [
        {'name': 'Google Cybersecurity Professional Certificate', 'provider': 'Coursera / Google', 'type': 'Free (Audit)', 'duration': '3-6 months', 'info': 'Covers Linux commands, SQL, python scripting, networks, and SIEM tools.'},
        {'name': 'CompTIA Security+', 'provider': 'CompTIA', 'type': 'Paid ($392)', 'duration': '1-2 months', 'info': 'Global benchmark certification for foundational IT security principles and threats.'}
    ],
    'UI/UX Designer': [
        {'name': 'Google UX Design Professional Certificate', 'provider': 'Coursera / Google', 'type': 'Free (Audit)', 'duration': '4-5 months', 'info': 'Master wireframing, Figma designs, user research, and high-fidelity mockups.'},
        {'name': 'Interaction Design Foundation Courses', 'provider': 'IxDF', 'type': 'Paid (Membership)', 'duration': 'Self-paced', 'info': 'Industry-respected theoretical and practical courses on design patterns and user psychology.'}
    ],
    'Product Manager': [
        {'name': 'Product Management First Steps', 'provider': 'LinkedIn Learning', 'type': 'Free (Trial)', 'duration': '2 weeks', 'info': 'Foundational concepts on product lifecycle, stakeholder management, and roadmap scoping.'},
        {'name': 'Professional Scrum Product Owner (PSPO I)', 'provider': 'Scrum.org', 'type': 'Paid ($150)', 'duration': '2 weeks', 'info': 'Demonstrate deep understanding of Agile product management and maximizing value.'}
    ]
}

def get_certifications_for_role(role_name):
    # Try exact match first
    for k, v in CERTIFICATION_MAPPING.items():
        if k.lower() == role_name.lower():
            return v
    # Try partial match next
    for k, v in CERTIFICATION_MAPPING.items():
        if k.lower() in role_name.lower() or role_name.lower() in k.lower():
            return v
    # Fallback default
    return [
        {'name': 'Google Project Management Professional Certificate', 'provider': 'Coursera / Google', 'type': 'Free (Audit)', 'duration': '3-4 months', 'info': 'Valuable organizational skills, agile operations, and leadership concepts.'},
        {'name': 'Professional Development Track', 'provider': 'Udemy / Coursera', 'type': 'Free/Paid', 'duration': '2-3 months', 'info': 'General career validation tracks in technology and system development.'}
    ]


# === Core Recommendation Logic ===

def compute_career_recommendations(user, resume, current_role_override=None, target_role_override=None):
    """
    Executes the Markov chain career recommendation logic.
    Returns a CareerRecommendation object (unsaved).
    """
    # 1. Determine Current Role
    current_role = current_role_override or user.profile.current_role
    if not current_role:
        # Fallback to first experience record job title
        first_exp = resume.experience_records.first()
        if first_exp and first_exp.job_title:
            current_role = first_exp.job_title
        else:
            current_role = "Junior Developer" # Default fallback
            
    # Try to map user-input role to the closest predefined JobRole
    all_job_roles = [role.name for role in JobRole.objects.all()]
    matched_current_role = "Junior Developer" # default fallback
    
    # Simple match: check for substring or exact match
    for role_name in all_job_roles:
        if role_name.lower() in current_role.lower() or current_role.lower() in role_name.lower():
            matched_current_role = role_name
            break
            
    # Ensure current role is recorded as profile current role
    user.profile.current_role = matched_current_role
    user.profile.save()
    
    # 2. Load transitions and construct Markov Recommender
    db_transitions = CareerTransition.objects.all()
    recommender = MarkovCareerRecommender(db_transitions)
    
    # 3. Gather user capabilities
    user_skills = [rs.skill.name for rs in resume.resume_skills.all()]
    embedder = SBERTModelManager()
    user_emb = embedder.deserialize_embedding(resume.embedding) if resume.embedding else None
    
    # 4. Get job roles dataset
    job_roles_data = get_job_roles_data_dict()
    
    # Adjust weights if configured in settings
    weights = getattr(settings, 'CAREER_RECOMMENDATION_WEIGHTS', {
        'markov': 0.50,
        'skill': 0.30,
        'semantic': 0.20
    })
    
    # 5. Rank next possible roles
    ranked_paths = recommender.rank_next_roles(
        current_role=matched_current_role,
        user_skills=user_skills,
        user_embedding=user_emb,
        job_roles_data=job_roles_data,
        embedder_manager=embedder,
        w_markov=weights['markov'],
        w_skill=weights['skill'],
        w_semantic=weights['semantic']
    )
    
    # 6. Generate Roadmap sequence (Current -> Next -> Future -> Advanced)
    roadmap_sequence = recommender.generate_roadmap(
        current_role=matched_current_role,
        user_skills=user_skills,
        user_embedding=user_emb,
        job_roles_data=job_roles_data,
        embedder_manager=embedder,
        max_steps=3
    )
    
    # Enrich roadmap sequence with skill gaps and explanations
    enriched_roadmap = []
    
    # Start node (Current Role)
    enriched_roadmap.append({
        'role': matched_current_role,
        'step': 0,
        'type': 'current',
        'probability': 1.0,
        'missing_skills': [],
        'explanation': "Your current career state parsed from experience.",
        'certifications': []
    })
    
    # Roadmap steps
    for idx, step in enumerate(roadmap_sequence):
        role_name = step['role']
        prob = step['transition_probability']
        
        # Calculate specific missing skills for this career state
        role_info = job_roles_data.get(role_name, {})
        req_skills = role_info.get('required_skills', [])
        
        missing_skills = [s for s in req_skills if s.lower() not in {us.lower() for us in user_skills}]
        
        # Generate learning sequence explanation
        if missing_skills:
            learn_seq = " -> ".join(missing_skills[:3])
            explanation = f"Recommended learning path: focus on acquiring '{learn_seq}' to bridge the gap."
        else:
            explanation = "You already possess the core skills required for this state!"
            
        enriched_roadmap.append({
            'role': role_name,
            'step': idx + 1,
            'type': 'progression',
            'probability': prob,
            'missing_skills': missing_skills,
            'explanation': explanation,
            'certifications': get_certifications_for_role(role_name)
        })
        
    target_role = target_role_override or (roadmap_sequence[0]['role'] if roadmap_sequence else "Software Developer")
    
    # Construct recommendation database model
    recommendation = CareerRecommendation(
        user=user,
        current_role=matched_current_role,
        target_role=target_role,
        roadmap_data=enriched_roadmap,
        alternative_paths=ranked_paths
    )
    return recommendation
    return recommendation


# === HTML Template Views ===

@login_required
def career_recommend_view(request):
    """
    Handles career roadmap input form and execution.
    """
    if request.method == 'POST':
        resume_id = request.POST.get('resume_id')
        current_role_override = request.POST.get('current_role', '').strip()
        
        resume = get_object_or_404(Resume, id=resume_id, user=request.user)
        
        try:
            recommendation = compute_career_recommendations(
                user=request.user,
                resume=resume,
                current_role_override=current_role_override or None
            )
            recommendation.save()
            
            messages.success(request, "Career roadmap recommendation generated!")
            return redirect('roadmap_detail', recommendation_id=recommendation.id)
            
        except Exception as e:
            messages.error(request, f"Failed to generate career path: {str(e)}")
            return redirect('career_recommend')
            
    resumes = Resume.objects.filter(user=request.user).order_by('-uploaded_at')
    # Fetch career states for custom user select override
    states = CareerState.objects.all().order_by('name')
    return render(request, 'dashboard/career_recommend.html', {
        'resumes': resumes,
        'states': states
    })

@login_required
def roadmap_detail_view(request, recommendation_id):
    recommendation = get_object_or_404(CareerRecommendation, id=recommendation_id, user=request.user)
    
    # Extract data from recommendation JSON fields
    roadmap = recommendation.roadmap_data
    alternatives = recommendation.alternative_paths
    
    # We want to identify the primary next role (step 1 in roadmap) and its detailed info
    next_role_data = None
    if len(roadmap) > 1:
        next_role_data = roadmap[1]
        
    context = {
        'recommendation': recommendation,
        'roadmap': roadmap,
        'alternatives': alternatives,
        'next_role': next_role_data,
    }
    return render(request, 'dashboard/roadmap_detail.html', context)


# === REST API Views ===

class CareerRecommendAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        resume_id = request.data.get('resume_id')
        current_role = request.data.get('current_role')
        target_role = request.data.get('target_role')
        
        if not resume_id:
            return Response({"error": "resume_id is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        resume = get_object_or_404(Resume, id=resume_id, user=request.user)
        
        try:
            recommendation = compute_career_recommendations(
                user=request.user,
                resume=resume,
                current_role_override=current_role,
                target_role_override=target_role
            )
            recommendation.save()
            
            serializer = CareerRecommendationSerializer(recommendation)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": f"Failed recommending career path: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CareerRoadmapAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        latest = CareerRecommendation.objects.filter(user=request.user).order_by('-created_at').first()
        if not latest:
            return Response({"error": "No career roadmaps found. Run a recommendation first."}, status=status.HTTP_404_NOT_FOUND)
            
        serializer = CareerRecommendationSerializer(latest)
        return Response(serializer.data)

from django.http import HttpResponse

@login_required
def download_roadmap_markdown_view(request, recommendation_id):
    rec = get_object_or_404(CareerRecommendation, id=recommendation_id, user=request.user)
    
    md = []
    md.append(f"# AI CAREER DEVELOPMENT ROADMAP STUDY GUIDE")
    md.append(f"==================================================")
    md.append(f"**Candidate**: {rec.user.username}")
    md.append(f"**Current Role**: {rec.current_role}")
    md.append(f"**Target Advanced State**: {rec.target_role}")
    md.append(f"**Generation Date**: {rec.created_at.strftime('%Y-%m-%d %H:%M UTC')}\n")
    md.append("This study guide outlines your personalized multi-step progression roadmap, including transition probabilities, required skills to develop, actionable self-study guides, and valuable professional certifications (free & paid).\n")
    md.append("---")
    
    md.append("\n## 📈 PATHWAY PROGRESSION TIMELINE\n")
    for step in rec.roadmap_data:
        step_num = step.get('step', 0)
        role = step.get('role', '')
        prob = step.get('probability', 0.0)
        explanation = step.get('explanation', '')
        missing = step.get('missing_skills', [])
        
        # Pull certifications
        certs = step.get('certifications') or get_certifications_for_role(role)
        
        if step.get('type') == 'current':
            md.append(f"### 📍 CURRENT CAREER STATE: **{role}**")
            md.append(f"* **Role Stage**: Starting State")
            md.append(f"* **Summary**: {explanation}\n")
        else:
            md.append(f"### 🚀 STEP {step_num}: **{role}**")
            md.append(f"* **Markov Transition Probability**: **{prob * 100:.0f}%**")
            md.append(f"* **Advisory Brief**: {explanation}")
            
            # Actionable skill learning guide
            if missing:
                md.append(f"* **Technical & Soft Skill Gaps**: {', '.join(missing)}")
                md.append("\n📚 **Actionable Skill Study Guide**:")
                for idx, sk in enumerate(missing):
                    md.append(f"  {idx+1}. **{sk} Self-Study Guide**:")
                    md.append(f"     * *How to Learn*: Search online courses on Coursera, Udemy, or free tutorials (YouTube / freeCodeCamp). Focus on building a mini-project applying {sk}.")
                    md.append(f"     * *Practical Practice*: Implement 2-3 code repositories or hands-on tasks implementing {sk} concepts to put on your portfolio.")
            else:
                md.append(f"* **Skills Status**: 100% overlay compatibility. Ready to transition!")
                
            # Recommended certifications
            if certs:
                md.append("\n🏆 **Valuable Professional Certifications to Earn**:")
                for cert in certs:
                    md.append(f"  * **{cert['name']}** — *Provider: {cert['provider']}*")
                    md.append(f"    * *Cost/type*: {cert['type']} | *Est. Duration*: {cert['duration']}")
                    md.append(f"    * *Why it is valuable*: {cert['info']}")
            md.append("\n")
            
    md.append("---")
    md.append("\n## 🔍 ALTERNATIVE STOCHASTIC PATHS\n")
    md.append("If you want to branch out, the Markov transition model has scored these alternative paths from your current state:")
    for idx, alt in enumerate(rec.alternative_paths[:5]):
        md.append(f"- **{alt['role']}**: Markov Transition Probability = {alt['transition_probability']*100:.0f}%, Skill Compatibility = {alt['skill_compatibility']*100:.0f}%, Overall Career Score = {alt['career_score']*100:.1f}%")
        
    md.append("\n\n---\n*Report generated by CareerChain AI Advisor.*")
    
    md_text = "\n".join(md)
    response = HttpResponse(md_text, content_type='text/markdown')
    response['Content-Disposition'] = f'attachment; filename="career_roadmap_{rec.user.username}_{rec.id}.md"'
    return response


# === PDF Generation Logic using PyMuPDF ===

def generate_career_recommendation_pdf(recommendation):
    import fitz  # PyMuPDF
    import textwrap
    
    # Create document A4
    doc = fitz.open()
    page = doc.new_page()
    
    x_margin = 50
    y_margin = 50
    y = y_margin
    
    font_bold = "helvetica-bold"
    font_regular = "helvetica"
    
    def draw_heading(text, size=16, color=(0.3, 0.3, 0.8)):
        nonlocal y, page
        if y > 740:
            page = doc.new_page()
            y = y_margin
        page.insert_text(fitz.Point(x_margin, y + size), text, fontsize=size, fontname=font_bold, color=color)
        y += size + 15
        
    def draw_subheading(text, size=11, color=(0.2, 0.3, 0.5)):
        nonlocal y, page
        if y > 760:
            page = doc.new_page()
            y = y_margin
        page.insert_text(fitz.Point(x_margin, y + size), text, fontsize=size, fontname=font_bold, color=color)
        y += size + 10
        
    def draw_text_line(text, size=9, color=(0.1, 0.1, 0.1), bold=False):
        nonlocal y, page
        if y > 780:
            page = doc.new_page()
            y = y_margin
        font = font_bold if bold else font_regular
        page.insert_text(fitz.Point(x_margin, y + size), text, fontsize=size, fontname=font, color=color)
        y += size + 5
        
    def draw_divider():
        nonlocal y, page
        if y > 780:
            page = doc.new_page()
            y = y_margin
        page.draw_line(fitz.Point(x_margin, y), fitz.Point(595 - x_margin, y), color=(0.85, 0.85, 0.85), width=1)
        y += 15

    # 1. Document Title
    draw_heading("CAREERCHAIN AI - CAREER ADVISORY REPORT", size=15, color=(0.25, 0.27, 0.6))
    draw_text_line(f"Candidate Profile: {recommendation.user.username}", bold=True)
    draw_text_line(f"Current Career State: {recommendation.current_role}")
    draw_text_line(f"Target Career State: {recommendation.target_role}")
    draw_text_line(f"Report Date: {recommendation.created_at.strftime('%B %d, %Y')}")
    draw_divider()
    
    # 2. Executive Summary
    draw_subheading("Executive Summary")
    summary_text = (
        f"Based on our BERT-based semantic profile matching and stochastic Markov Chain path optimization, "
        f"we have analyzed the suitability gap between your experience/skills and the target role '{recommendation.target_role}'. "
        f"To achieve progression, we recommend targeting the step-by-step career timeline outlined below."
    )
    for line in textwrap.wrap(summary_text, width=95):
        draw_text_line(line)
    y += 10
    
    # 3. Pathway Progression Steps
    draw_subheading("Pathway Progression Steps")
    
    for step in recommendation.roadmap_data:
        step_num = step.get('step', 0)
        role = step.get('role', '')
        prob = step.get('probability', 0.0)
        explanation = step.get('explanation', '')
        missing = step.get('missing_skills', [])
        
        y += 5
        if step.get('type') == 'current':
            draw_text_line(f"Current State: {role}", bold=True, color=(0.1, 0.5, 0.1))
            draw_text_line(f"Details: {explanation}", size=8, color=(0.3, 0.3, 0.3))
        else:
            draw_text_line(f"Step {step_num}: {role} (Probability: {prob*100:.0f}%)", bold=True, color=(0.2, 0.2, 0.7))
            
            for line in textwrap.wrap(explanation, width=100):
                draw_text_line(f"  Info: {line}", size=8, color=(0.3, 0.3, 0.3))
                
            if missing:
                draw_text_line(f"  Missing Skills to Acquire: {', '.join(missing)}", size=8.5, bold=True, color=(0.7, 0.1, 0.1))
                
                draw_text_line("  Actionable Study Plan:", size=8, bold=True)
                for sk in missing[:3]:
                    draw_text_line(f"    * {sk}: Search online courses (Coursera/Udemy). Practice implementing concepts in mini-projects.", size=8, color=(0.2, 0.2, 0.2))
                    
            certs = step.get('certifications') or get_certifications_for_role(role)
            if certs:
                draw_text_line("  Recommended Professional Certifications:", size=8, bold=True)
                for cert in certs[:2]:
                    draw_text_line(f"    * {cert['name']} ({cert['provider']}) - {cert['type']}", size=8, color=(0.2, 0.2, 0.2))
        y += 10
        
    draw_divider()
    
    # 4. Alternative Career Vectors
    draw_subheading("Alternative Career Options")
    draw_text_line("The Markov model has scored alternative transitions from your current role:")
    for idx, alt in enumerate(recommendation.alternative_paths[:4]):
        draw_text_line(f"  {idx+1}. {alt['role']} (Transition Prob: {alt['transition_probability']*100:.0f}%, Overall Score: {alt['career_score']*100:.1f}%)", size=8, color=(0.3, 0.3, 0.3))
        
    y += 15
    draw_text_line("Report automatically generated by CareerChain AI Career Advisor Platform.", size=7, color=(0.5, 0.5, 0.5))
    
    # Save document
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


# === Download PDF Endpoint Views ===

@login_required
def download_roadmap_pdf_view(request, recommendation_id):
    rec = get_object_or_404(CareerRecommendation, id=recommendation_id, user=request.user)
    try:
        pdf_bytes = generate_career_recommendation_pdf(rec)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="career_roadmap_{rec.user.username}_{rec.id}.pdf"'
        return response
    except Exception as e:
        messages.error(request, f"Failed to generate PDF report: {str(e)}")
        return redirect('roadmap_detail', recommendation_id=rec.id)

@login_required
def generate_match_recommendation_pdf_view(request, analysis_id):
    from jobs.models import AnalysisResult
    analysis = get_object_or_404(AnalysisResult, id=analysis_id, user=request.user)
    
    try:
        # Dynamically compute career recommendation in database context
        recommendation = compute_career_recommendations(
            user=request.user,
            resume=analysis.resume,
            current_role_override=analysis.job_description.title
        )
        recommendation.save()
        
        pdf_bytes = generate_career_recommendation_pdf(recommendation)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="career_recommendation_{request.user.username}_{analysis.id}.pdf"'
        return response
    except Exception as e:
        messages.error(request, f"Failed to generate career recommendation report: {str(e)}")
        return redirect('analysis_detail', analysis_id=analysis.id)
