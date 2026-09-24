import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'richlead_backend.settings')
django.setup()

from leads.models import Lead, ScoreBreakdown, IntentSignal, AIResearch
from django.contrib.auth import get_user_model

User = get_user_model()

def seed():
    # Clear existing data
    Lead.objects.all().delete()
    User.objects.filter(username="testadmin").delete()
    
    # Create test user
    user = User.objects.create_superuser("testadmin", "admin@richlead.com", "password")
    
    # Lead 1
    l1 = Lead.objects.create(user=user, name="Alice Johnson", company="TechCorp", niche="SaaS", status="replied", email="alice@techcorp.com", icp_score=92)
    ScoreBreakdown.objects.create(lead=l1, factor="Company Fit", score=25, max_score=25)
    ScoreBreakdown.objects.create(lead=l1, factor="Job Title", score=20, max_score=20)
    IntentSignal.objects.create(lead=l1, signal="🔥 Recently funded ($5M Series A)")
    IntentSignal.objects.create(lead=l1, signal="🚀 Hiring 5 new Sales Reps")
    AIResearch.objects.create(lead=l1, summary="TechCorp is scaling aggressively post-funding.", generated_message="Hi Alice, saw the $5M raise...")

    # Lead 2
    l2 = Lead.objects.create(user=user, name="Bob Smith", company="Innovate Inc", niche="E-commerce", status="reached", email="bob@innovate.com", icp_score=85)
    IntentSignal.objects.create(lead=l2, signal="📈 Website visit detected")
    AIResearch.objects.create(lead=l2, summary="Innovate Inc has seen a 20% drop in cart abandonment.", generated_message="Hey Bob...")

    # Lead 3
    l3 = Lead.objects.create(user=user, name="Charlie Davis", company="Growthify", niche="Marketing", status="pending", email="charlie@growthify.com", icp_score=78)
    IntentSignal.objects.create(lead=l3, signal="💼 New CMO appointed")
    AIResearch.objects.create(lead=l3, summary="Growthify brought on a new CMO last month.", generated_message="Hi Charlie, I noticed Growthify is scaling...")

    print("Database successfully seeded with mock leads!")

if __name__ == '__main__':
    seed()
