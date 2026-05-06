# core/scrapers/categories.py

JOB_CATEGORIES = {
    "Software Engineering": [
        "Software Engineer", "Software Developer", "Backend Developer", "Full Stack Developer",
        "Frontend Developer", "Platform Engineer", "Systems Engineer", "Java Backend Developer",
        "Java Developer", "iOS Developer", "Android Developer", "React Native Developer",
        "Blockchain Developer", "Graphics Engineer", "SAP Developer", ".NET Developer",
        "Embedded Systems Engineer", "Power Platform Developer", "Software Development Engineer",
        "Fullstack Engineer", "Frontend Engineer", "Backend Engineer", "SDE", "SDE 1", "SDE 2",
        "Senior Software Engineer", "Staff Software Engineer", "Principal Software Engineer",
        "Senior Developer", "Lead Developer", "Software Architect"
    ],
    "Infrastructure & DevOps": [
        "Cloud Engineer", "DevOps Engineer", "Cloud Developer", "Site Reliability Engineer",
        "Security Engineer", "Network Engineer", "Systems Administrator", "AWS Java Developer",
        "AWS Azure", "AWS DevOps Engineer", "Infrastructure Engineer", "Kubernetes Engineer",
        "Senior DevOps Engineer", "Lead Cloud Engineer", "SRE"
    ],
    "Data & AI": [
        "Data Analyst", "Data Engineer", "Data Science", "Machine Learning Engineer",
        "AI Engineer", "Gen AI", "Analytics Engineer", "Business Intelligence Analyst",
        "ETL Developer", "SQL Developer", "Data Scientist", "ML Engineer", "Computer Vision Engineer",
        "NLP Engineer", "AI Researcher", "Senior Data Scientist", "Senior Data Engineer", "Lead Data Analyst"
    ],
    "Security": [
        "Security Engineer", "Cybersecurity Analyst", "Security Analyst", 
        "Application Security Engineer", "Network Security Engineer", "Information Security Analyst",
        "Security Consultant", "SOC Analyst", "Senior Security Engineer", "Lead Security Analyst"
    ],
    "Quality & Testing": [
        "QA Engineer", "Test Engineer", "Automation Test Engineer", "QA Analyst", "SDET", 
        "Quality Engineer", "Quality Control", "Testing Engineer", "Senior QA Engineer", "Lead SDET"
    ],
    "Management": [
        "Product Manager", "Engineering Manager", "Project Manager", "Program Manager",
        "Supply Chain Manager", "Finance Manager", "Product Owner", "Marketing Manager",
        "Technical Product Manager", "TPM", "Product Lead", "Senior Product Manager", "Director of Engineering"
    ],
    "Design": [
        "UI Designer", "UX Designer", "Product Designer", "UI UX Designer", "Interaction Designer",
        "Visual Designer", "Experience Designer", "UX Researcher", "Senior UX Designer", "Lead Product Designer"
    ],
    "Support & IT": [
        "IT Support Engineer", "Technical Support Engineer", "Salesforce Administrator",
        "Technical Support", "IT Specialist", "Desktop Support", "Senior IT Specialist"
    ],
    "Specialized": [
        "SAP", "Salesforce Developer", "Business Analyst", "Supply Chain", 
        "Marketing Analyst", "Aerospace Engineer", "Mechanical Engineer", 
        "Civil Engineer", "Physical Therapist", "Finance Analyst", "Risk Analyst", 
        "Product Analyst", "Clinical Research Scientist", "Drug Safety Associate",
        "Construction Engineer", "Quantitative Analyst", "Quant Developer", "Senior Business Analyst"
    ]
}

TARGET_KEYWORD_COUNT = 98

def get_all_titles():
    """Returns the exact configured keyword set (98 unique titles)."""
    titles = []
    seen = set()
    for cat in JOB_CATEGORIES.values():
        for title in cat:
            normalized = title.strip().lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            titles.append(title.strip())
            if len(titles) >= TARGET_KEYWORD_COUNT:
                return titles
    return titles

def matches_target_titles(title):
    """
    Check if a job title matches any of the target categories.
    Uses more flexible word-based matching to catch common variations.
    """
    if not title:
        return False
    
    title_lower = title.lower()
    all_titles = get_all_titles()
    
    for target in all_titles:
        target_lower = target.lower()
        
        # 1. Direct substring match (e.g., "Software Engineer" in "Senior Software Engineer")
        if target_lower in title_lower:
            if len(target_lower) > 3 or f" {target_lower} " in f" {title_lower} ":
                return True
        
        # 2. Fuzzy match for multi-word roles (e.g., "Software Engineer" matching "Software Development Engineer")
        target_words = target_lower.split()
        if len(target_words) > 1:
            # Check if ALL words of the target title exist in the job title
            if all(word in title_lower for word in target_words):
                return True
                
    return False
