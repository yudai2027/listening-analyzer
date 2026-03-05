import json
import datetime
import urllib.request
import urllib.error
import re
import html
import time
from aqt import mw, gui_hooks
from aqt.utils import showInfo
from aqt.qt import QAction

# --- Load configuration from config.json ---
config = mw.addonManager.getConfig(__name__)

NOTION_TOKEN = config.get("NOTION_TOKEN", "")
DATABASE_ID = config.get("DATABASE_ID", "")
GEMINI_API_KEY = config.get("GEMINI_API_KEY", "")
TARGET_NOTE_TYPE = config.get("TARGET_NOTE_TYPE", "")
FIELD_SENTENCE = config.get("FIELD_SENTENCE", "")
FIELD_TRANSLATION = config.get("FIELD_TRANSLATION", "")

TAG_ERROR = "notion_error"
TAG_MISSING = "notion_missing"

def clean_text(text):
    """Remove HTML tags, sound tags, and normalize whitespaces."""
    if not text: return ""
    text = re.sub(r"\[sound:.*?\]", "", text)
    text = html.unescape(text)
    text = text.replace('\xa0', ' ')
    text = re.sub(r"<.*?>", "", text)
    return re.sub(r"\s+", " ", text).strip()

def map_categories(raw_categories):
    """Map AI-generated categories to predefined labels for Notion multi-select."""
    valid_categories = ["Liaison", "Flapping", "Vocabulary", "Grammar", "Speed"]
    if not isinstance(raw_categories, list):
        raw_categories = [raw_categories]
    mapped = []
    for raw in raw_categories:
        cat_str = str(raw).lower()
        for valid in valid_categories:
            if valid.lower() in cat_str and valid not in mapped:
                mapped.append(valid)
    return mapped if mapped else ["Vocabulary"]

def analyze_with_gemini(text, retry=True):
    """Analyze the English sentence using Gemini API for linguistic listening barriers."""
    if not GEMINI_API_KEY:
        return {"categories": ["Error"], "analysis": "Gemini API Key is missing in config."}

    model_id = "models/gemini-flash-latest"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_id}:generateContent?key={GEMINI_API_KEY}"

    prompt = (
        "You are an expert English listening coach for Japanese learners.\n"
        f"Target English Phrase: '{text}'\n\n"
        "Task: Analyze why a Japanese speaker might struggle to catch this phrase aurally.\n"
        "Constraints: 1. NO meaning/topic explanation. 2. Output ONLY JSON.\n"
        "JSON Format: {\"category\": [\"...\", \"...\"], \"analysis_ja\": \"...\"}\n"
        "category must be an array of one or more values from: Liaison, Flapping, Vocabulary, Grammar, Speed."
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
                return {"categories": map_categories(res_json.get('category')), "analysis": res_json.get('analysis_ja')}
            return {"categories": ["Error"], "analysis": "Failed to parse AI response."}
    except urllib.error.HTTPError as e:
        if e.code in (429, 503) and retry:
            time.sleep(3)
            return analyze_with_gemini(text, retry=False)
        return {"categories": ["Error"], "analysis": f"API Error {e.code}"}
    except Exception as e:
        return {"categories": ["Error"], "analysis": str(e)}

def push_to_notion(note):
    """Assemble data and send a POST request to the Notion API."""
    if not NOTION_TOKEN or not DATABASE_ID:
        return
    if FIELD_SENTENCE not in note or FIELD_TRANSLATION not in note:
        return

    eng_text = clean_text(note[FIELD_SENTENCE])
    ja_translation = clean_text(note[FIELD_TRANSLATION])

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
            "エラーカテゴリ": {"multi_select": [{"name": c} for c in analysis_result.get('categories', [])]},
            "分析": {"rich_text": [{"text": {"content": str(analysis_result.get('analysis'))}}]}
        }
    }

    try:
        req = urllib.request.Request("https://api.notion.com/v1/pages", data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req) as res: pass
        # Success: remove error tag if it was previously set
        if note.has_tag(TAG_ERROR):
            note.remove_tag(TAG_ERROR)
            note.flush()
    except Exception as e:
        # Failure: tag the note so user can find it later
        note.add_tag(TAG_ERROR)
        note.flush()
        print(f"Notion Error: {e}")

# --- Notion comparison feature ---

def fetch_notion_titles():
    """Fetch all 'English study' titles from the Notion database."""
    titles = set()
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    has_more = True
    start_cursor = None

    while has_more:
        payload = {}
        if start_cursor:
            payload["start_cursor"] = start_cursor
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req) as res:
            result = json.loads(res.read().decode("utf-8"))
        for page in result.get("results", []):
            title_prop = page.get("properties", {}).get("English study", {}).get("title", [])
            if title_prop:
                titles.add(title_prop[0].get("text", {}).get("content", ""))
        has_more = result.get("has_more", False)
        start_cursor = result.get("next_cursor")

    return titles

def sync_check_with_notion():
    """Compare Anki notes with Notion DB and tag missing ones."""
    if not NOTION_TOKEN or not DATABASE_ID or not TARGET_NOTE_TYPE:
        showInfo("設定が不足しています（NOTION_TOKEN, DATABASE_ID, TARGET_NOTE_TYPE）")
        return

    try:
        notion_titles = fetch_notion_titles()
    except Exception as e:
        showInfo(f"Notion取得エラー: {e}")
        return

    # Search Anki for all notes of the target type
    model = None
    for m in mw.col.models.all():
        if m['name'] == TARGET_NOTE_TYPE:
            model = m
            break
    if not model:
        showInfo(f"ノートタイプ '{TARGET_NOTE_TYPE}' が見つかりません")
        return

    note_ids = mw.col.find_notes(f'"note:{TARGET_NOTE_TYPE}"')
    missing_count = 0
    found_count = 0

    for nid in note_ids:
        note = mw.col.get_note(nid)
        if FIELD_SENTENCE not in note:
            continue
        eng_text = clean_text(note[FIELD_SENTENCE])
        if not eng_text:
            continue

        if eng_text not in notion_titles:
            if not note.has_tag(TAG_MISSING):
                note.add_tag(TAG_MISSING)
                note.flush()
            missing_count += 1
        else:
            # Already in Notion: remove missing tag if present
            if note.has_tag(TAG_MISSING):
                note.remove_tag(TAG_MISSING)
                note.flush()
            found_count += 1

    showInfo(
        f"比較完了\n\n"
        f"Notion登録済み: {found_count} 件\n"
        f"Notion未登録 (タグ '{TAG_MISSING}' 付与): {missing_count} 件\n\n"
        f"ブラウザで tag:{TAG_MISSING} を検索してください"
    )

# --- Menu setup ---
action = QAction("Notion同期チェック", mw)
action.triggered.connect(sync_check_with_notion)
mw.form.menuTools.addAction(action)

# --- Hook ---
def on_note_added(note):
    """Hook function triggered when a new note is added to Anki."""
    if TARGET_NOTE_TYPE and note.model()['name'] == TARGET_NOTE_TYPE:
        push_to_notion(note)

gui_hooks.add_cards_did_add_note.append(on_note_added)
