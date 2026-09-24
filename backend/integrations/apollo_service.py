from leads.models import Lead, IntentSignal
from integrations.models import APIIntegration
from ai_engine.services import generate_outreach_message
from integrations.services import send_outreach_email
import random

def fetch_apollo_leads(user, search_params):
    """
    Fetches leads from Apollo based on search parameters.
    Then orchestrates AI generation and autopilot sending.
    """
    # 1. Get Apollo API Key (Mocked checking for MVP)
    try:
        integration = APIIntegration.objects.get(user=user, provider='apollo', is_active=True)
        api_key = integration.get_api_key()
    except APIIntegration.DoesNotExist:
        api_key = None # Will use mock data

    # 2. Mock Apollo API Call (Sandbox Mode)
    job_titles = search_params.get('job_titles', 'CEO')
    location = search_params.get('location', 'United States')
    keywords = search_params.get('keywords', 'Tech')
    count = int(search_params.get('count', 10))
    fields = search_params.get('fields', [])
    
    mock_leads_data = []
    for i in range(count):
        mock_leads_data.append({
            "name": f"Lead {random.randint(1000,9999)}", 
            "email": f"lead{random.randint(100,999)}@example.com", 
            "company": f"{keywords} Company {i}", 
            "title": job_titles, 
            "niche": keywords
        })

    fetched_leads = []

    # 3. Process each fetched lead
    for data in mock_leads_data:
        # Create Lead
        lead = Lead.objects.create(
            user=user,
            name=data['name'],
            email=data['email'],
            company=data['company'],
            title=data['title'],
            niche=data['niche'],
            icpScore=random.randint(70, 99),
            status='pending'
        )
        
        # Add mock intent signal
        IntentSignal.objects.create(lead=lead, signal=f"Searching for {keywords} services")
        
        fetched_leads.append(lead)

        # 4. Trigger AI Engine
        ai_result = generate_outreach_message(lead.id, user)
        
        if ai_result.get('success'):
            # 5. Check Autopilot logic
            if user.autopilot_active:
                # Send immediately if Autopilot is ON
                send_result = send_outreach_email(lead.id, user, ai_result['message'])
                if send_result.get('success'):
                    # Status is updated to 'reached' inside send_outreach_email
                    pass
            else:
                # Leave as pending for manual review
                pass

    return {"success": True, "fetched_count": len(fetched_leads)}
