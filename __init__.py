import json
import datetime
import urllib.request
import urllib.error
import re
import html
import time
from aqt import mw, gui_hooks

# --- Load configuration from config.json ---
# All values are empty by default. Users must set them via Anki's add-on config screen.
config = mw.addonManager.getConfig(__name__)

NOTION_TOKEN = config.get("NOTION_TOKEN", "")
DATABASE_ID = config.get("DATABASE_ID", "")
GEMINI_API_KEY = config.get("GEMINI_API_KEY", "")
TARGET_NOTE_TYPE = config.get("TARGET_NOTE_TYPE", "")
FIELD_SENTENCE = config.get("FIELD_SENTENCE", "")
FIELD_TRANSLATION = config.get("FIELD_TRANSLATION", "")

def clean_text(text):
    """Remove HTML tags, sound tags, and normalize whitespaces."""
    if not text: return ""
    text = re.sub(r"\[sound:.*?\]", "", text)
    text = html.unescape(text)
    text = text.replace('\xa0', ' ')
    text = re.sub(r"<.*?>", "", text)
    return re.sub(r"\s+", " ", text).strip()

def map_category(raw_category):
    """Map AI-generated category to one of the 5 predefined labels for Notion consistency."""
    valid_categories = ["Liaison", "Flapping", "Vocabulary", "Grammar", "Speed"]
    cat_str = str(raw_category).lower()
    for valid in valid_categories:
        if valid.lower() in cat_str:
            return valid
    return "Vocabulary"

def analyze_with_gemini(text, retry=True):
    """Analyze the English sentence using Gemini API for linguistic listening barriers."""
    if not GEMINI_API_KEY:
        return {"category": "Error", "analysis": "Gemini API Key is missing in config."}
        
    model_id = "models/gemini-flash-latest"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_id}:generateContent?key={GEMINI_API_KEY}"
    
    prompt = (
        "You are an expert English listening coach for Japanese learners.\n"
        f"Target English Phrase: '{text}'\n\n"
        "Task: Analyze why a Japanese speaker might struggle to catch this phrase aurally.\n"
        "Constraints: 1. NO meaning/topic explanation. 2. Output ONLY JSON.\n"
        "JSON Format: {\"category\": \"...\", \"analysis_ja\": \"...\"}"
    )
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as res:
            content = json.loads(res.read().decode("utf-8"))['candidates'][0]['content']['parts'][0]['text']
            content = re.sub(r'```(?:json)?\s*(.*?)\s*```', r'\1', content, flags=re.DOTALL)
            start, end = content.find('{'), content.rfind('}')
            if start != -1 and end != -1:
                res_json = json.loads(content[start:end+1])
                return {"category": map_category(res_json.get('category')), "analysis": res_json.get('analysis_ja')}
            return {"category": "Error", "analysis": "Failed to parse AI response."}
    except urllib.error.HTTPError as e:
        if e.code == 429 and retry:
            time.sleep(3)
            return analyze_with_gemini(text, retry=False)
        return {"category": "Error", "analysis": f"API Error {e.code}"}
    except Exception as e:
        return {"category": "Error", "analysis": str(e)}

def push_to_notion(note):
    """Assemble data and send a POST request to the Notion API."""
    # Check if necessary Notion settings are provided
    if not NOTION_TOKEN or not DATABASE_ID:
        return

    # Check if specified fields exist in the current note
    if FIELD_SENTENCE not in note or FIELD_TRANSLATION not in note:
        return

    eng_text = clean_text(note[FIELD_SENTENCE])
    ja_translation = clean_text(note[FIELD_TRANSLATION])
    
    # Skip if the target sentence is empty
    if not eng_text:
        return

    analysis_result = analyze_with_gemini(eng_text)
    
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    data = {
        "parent": {"database_id": DATABASE_ID},
        "properties": {
            "English study": {"title": [{"text": {"content": eng_text}}]},
            "日本語訳": {"rich_text": [{"text": {"content": ja_translation}}]},
            "日付": {"date": {"start": datetime.date.today().isoformat()}},
            "エラーカテゴリ": {"multi_select": [{"name": str(analysis_result.get('category'))}]},
            "分析": {"rich_text": [{"text": {"content": str(analysis_result.get('analysis'))}}]}
        }
    }
    
    try:
        req = urllib.request.Request("https://api.notion.com/v1/pages", data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req) as res: pass
    except Exception as e:
        print(f"Notion Error: {e}")

def on_note_added(note):
    """Hook function triggered when a new note is added to Anki."""
    # Only proceed if the note type matches the user's config
    if TARGET_NOTE_TYPE and note.model()['name'] == TARGET_NOTE_TYPE:
        push_to_notion(note)

gui_hooks.add_cards_did_add_note.append(on_note_added)
