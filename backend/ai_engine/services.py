import openai
from django.core.exceptions import ObjectDoesNotExist
from leads.models import Lead, AIResearch
from integrations.models import APIIntegration
from .models import PromptTemplate

def generate_outreach_message(lead_id, user):
    """
    Core AI Engine logic to research a lead and write an email.
    """
    try:
        lead = Lead.objects.get(id=lead_id, user=user)
    except Lead.DoesNotExist:
        return {"success": False, "error": "Lead not found."}

    # 1. Fetch user's active API key (Assuming OpenAI for MVP)
    try:
        integration = APIIntegration.objects.get(user=user, provider='openai', is_active=True)
        api_key = integration.get_api_key()
    except APIIntegration.DoesNotExist:
        # Fallback to mock response for testing if no key is found
        return _mock_ai_response(lead)

    # 2. Fetch user's prompt template
    prompt_template = PromptTemplate.objects.filter(user=user, is_active=True).first()
    system_prompt = (
        prompt_template.system_prompt if prompt_template 
        else "You are an expert sales representative. Write a short, personalized cold email."
    )
    system_prompt += "\n\nCRITICAL INSTRUCTIONS TO AVOID SPAM FILTERS:\n- Write in a natural, conversational, and plain-text style.\n- Do NOT use spam trigger words (e.g., 'Free', 'Guarantee', 'Act now', 'Limited time').\n- Do NOT use emojis.\n- Do NOT use em dashes (—) or en dashes (–). Use standard commas, periods, or simple hyphens (-) instead.\n- Keep sentences short and spacing natural."
    
    tone = prompt_template.tone_of_voice if prompt_template else "Professional"

    # 3. Construct Context
    signals = lead.intent_signals.all()
    signal_text = ", ".join([s.signal for s in signals]) if signals else "No recent intent signals."
    
    user_prompt = f"""
    Lead Name: {lead.name}
    Company: {lead.company}
    Niche: {lead.niche}
    Intent Signals: {signal_text}
    Tone: {tone}
    
    Based on the above, write a highly personalized, short cold email to {lead.name}.
    Ensure the email reads as a one-to-one plain text email from a real person.
    """

    # 4. Call OpenAI API
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Using cheaper/faster model for MVP
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=250,
            temperature=0.7
        )
        
        # Clean up generated message just in case the AI ignores the prompt
        generated_message = response.choices[0].message.content.strip()
        generated_message = generated_message.replace("—", " - ").replace("–", "-")
        
        research_summary = f"Analyzed {lead.company} in {lead.niche}. Focused on: {signal_text}"

        # 5. Save to Database
        ai_research, created = AIResearch.objects.get_or_create(lead=lead)
        ai_research.summary = research_summary
        ai_research.generated_message = generated_message
        ai_research.save()

        return {"success": True, "message": generated_message, "summary": research_summary}

    except Exception as e:
        return {"success": False, "error": str(e)}

def _mock_ai_response(lead):
    """Fallback mock response for development when no API key is provided."""
    mock_msg = f"Hi {lead.name},\n\nI noticed {lead.company} is doing great work in {lead.niche}. I wanted to see if you'd be open to a quick chat about scaling your outreach.\n\nBest,\nAdmin"
    mock_summary = f"Mock research for {lead.company} based on missing API key."
    
    ai_research, _ = AIResearch.objects.get_or_create(lead=lead)
    ai_research.summary = mock_summary
    ai_research.generated_message = mock_msg
    ai_research.save()
    
    return {"success": True, "message": mock_msg, "summary": mock_summary, "mocked": True}
