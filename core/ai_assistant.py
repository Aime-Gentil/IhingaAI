"""Gemini-based, consent-gated assistant. Does not change frozen numerical estimates."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SYSTEM = """You are IhingaAI, a careful farming education assistant for farmers in Rwanda.
Always use the provided field facts and model snapshot; never invent weather, diagnoses, soil results, yields, field history, or sources.
The existing model's number and range are fixed. You may explain them but never revise or claim AI made a better numerical yield prediction.
Historical model outputs are uncertain, not guarantees. Questions about fertilizers, pesticides, diseases, treatment rates and harvest timing must avoid precise hazardous instructions, recommend checking product labels and qualified Rwanda extension workers when appropriate.
Ask up to TWO useful clarifying questions when necessary. Distinguish general possibilities from verified personalized guidance. Use accessible language; reply in the user's language (English or Kinyarwanda).
You may suggest small, practical, observational tasks, but no schedules/dates unless supported by supplied dates or farmer inputs. Refer to current weather only if sourced forecast data appears in the provided field context, and label forecasts as approximate and uncertain. Never invent weather.
Return ONLY valid JSON with fields: answer (string), questions (list of strings, max 2), actions (list of objects with title (string, <=120 chars) and reason (string), max 4). Never include secrets or instructions to disable safeguards."""


def api_key():
    try:
        import streamlit as st
        key = st.secrets.get('GEMINI_API_KEY', '')
        if key: return str(key).strip()
    except Exception:
        pass
    return ''


def call_gemini(key, message, context, history=None, language='en'):
    """Send user-approved minimized field context; parse constrained answer."""
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key)
    payload = {
        'language': language,
        'field_context': context,
        'conversation': (history or [])[-4:],
        'current_farmer_question': str(message)[:1100],
    }
    response = client.models.generate_content(
        model='gemini-3.8-flash',
        contents=json.dumps(payload, ensure_ascii=False),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            response_mime_type='application/json',
            temperature=0.35,
            max_output_tokens=650,
        ),
    )
    if not response.text:
        raise ValueError('Gemini returned an empty response.')
    result = json.loads(response.text)
    if not isinstance(result, dict): raise ValueError('Unexpected AI response format.')
    actions = result.get('actions', [])
    clean_actions = []
    for action in actions if isinstance(actions, list) else []:
        if isinstance(action, dict):
            title = str(action.get('title', '')).strip()[:120]
            if title: clean_actions.append({'title': title, 'reason': str(action.get('reason',''))[:400]})
    return {'answer': str(result.get('answer',''))[:6000],
            'questions': [str(q)[:300] for q in result.get('questions', [])[:2]] if isinstance(result.get('questions'),list) else [],
            'actions': clean_actions[:4]}


def field_context(field, estimate=None, district_name=None, crop_name=None):
    if not field: return {'scope': 'general guidance only', 'field_registered': False}
    data = {
        'field_registered': True,
        'crop': crop_name or field['crop_code'],
        'season': field['season'],
        'district': district_name or field['district_code'],
        'area_hectares': round(field['area_sqm']/10000,4),
        'seed_type': field['seed_type'],
        'planting_date': field['planting_date'],
        'planned_practices': field['planned_practices'][:600],
    }
    if estimate:
        result = json.loads(estimate['output_json'])
        if result.get('status') == 'ok':
            data['saved_model_estimate'] = {
                'estimate_kg': result.get('estimate_kg'), 'lower_kg': result.get('lower_kg'),
                'upper_kg': result.get('upper_kg'), 'evidence': result.get('evidence'),
                'coverage_out_of_10': result.get('coverage_in_10'),
                'warning_codes': result.get('warnings', []),
                'model_version': estimate['model_version'],
                'saved_on': estimate['created_at'],
                'note': 'Historical model estimate only; fixed values; NOT a guarantee.'
            }
    return data


def inspect_crop_photo(key, photo_bytes, mime_type, field_context, observations, language='en'):
    """Preliminary visual triage; never authoritative pest/disease diagnosis."""
    from google import genai
    from google.genai import types
    prompt = ('You are assisting a Rwandan farmer. Review the image and observations for visible issues only. '
              'Avoid definitive diagnosis. Suggest safe monitoring and when to contact an agronomist. '
              'Do not suggest named pesticides, fertilizer doses, or agrochemical purchases. '
              'Say if image quality is insufficient. Respond in English or Kinyarwanda as requested. '
              +json.dumps({'context':field_context,'observations':observations,'language':language},ensure_ascii=False))
    client=genai.Client(api_key=key)
    result=client.models.generate_content(
        model='gemini-3.8-flash',
        contents=[types.Part.from_text(text=prompt),types.Part.from_bytes(data=photo_bytes,mime_type=mime_type)],
        config=types.GenerateContentConfig(max_output_tokens=750,temperature=0.2))
    return (result.text or 'The photo could not be assessed. Please consult your local agronomist.')[:4500]
