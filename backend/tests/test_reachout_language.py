import pytest


@pytest.mark.django_db
def test_user_can_read_and_update_reachout_language(auth_a, user_a):
    settings_url = '/api/users/settings/'

    response = auth_a.get(settings_url)

    assert response.status_code == 200
    assert response.data['reachout_language'] == 'en'
    assert {'value': 'ur', 'label': 'Urdu (اردو)'} in response.data['reachout_language_choices']

    response = auth_a.post(settings_url, {'reachout_language': 'es'}, format='json')

    assert response.status_code == 200
    assert response.data['reachout_language'] == 'es'
    user_a.refresh_from_db()
    assert user_a.reachout_language == 'es'


@pytest.mark.parametrize('invalid_value', ['xx', '', ['ur']])
@pytest.mark.django_db
def test_user_cannot_set_unsupported_reachout_language(auth_a, user_a, invalid_value):
    response = auth_a.post(
        '/api/users/settings/', {'reachout_language': invalid_value}, format='json',
    )

    assert response.status_code == 400
    user_a.refresh_from_db()
    assert user_a.reachout_language == 'en'


@pytest.mark.django_db
def test_outreach_prompt_uses_selected_language(lead_a):
    from ai_engine.services import _build_prompts

    system_prompt, _user_prompt, _signal_text = _build_prompts(
        lead_a, template=None, reachout_language='ur',
    )

    assert 'OUTREACH LANGUAGE: Write the subject line and complete email body in Urdu (اردو).' in system_prompt
