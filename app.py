import streamlit as st
import json
import streamlit.components.v1 as components
import google.generativeai as genai
import time

# -------------------------------------------------------------------
# 1. 初期設定とUIの固定テキスト（英語）
# -------------------------------------------------------------------
st.set_page_config(page_title="Washoku Voice Dictionary", layout="centered")

ui = {
    "input_label": "⌨️ Enter term (Romaji, Hiragana, Kanji):",
    "submit": "Search", 
    "thinking": "Searching & Translating...", 
    "warning": "Please enter a term.",
    "answer": "**Dictionary Result:**",
    "not_found_msg": "Term not found in our database. Please check the spelling and try again.",
    "voice": "🗣️ Voice:", "speed": "⏱️ Speed:",
    "note": "ℹ️ If you change the voice or speed, please click '⏹ Stop' then '▶ Play' again.",
    "play": "▶ Play", "pause": "⏸ Pause", "resume": "⏯ Resume", "stop": "⏹ Stop", "not_found": "Voice not found"
}

lang_options = {
    "English": "en-US", "Español (Spanish)": "es-ES", "Français (French)": "fr-FR", 
    "Deutsch (German)": "de-DE", "Italiano (Italian)": "it-IT", "Português (Portuguese)": "pt-PT",
    "Nederlands (Dutch)": "nl-NL", "Русский (Russian)": "ru-RU", "中文 (Chinese)": "zh-CN",
    "한국어 (Korean)": "ko-KR", "العربية (Arabic)": "ar-SA", "हिन्दी (Hindi)": "hi-IN",
    "বাংলা (Bengali)": "bn-IN", "Türkçe (Turkish)": "tr-TR", "Tiếng Việt (Vietnamese)": "vi-VN",
    "Bahasa Indonesia (Indonesian)": "id-ID", "ภาษาไทย (Thai)": "th-TH", "Polski (Polish)": "pl-PL"
}

# -------------------------------------------------------------------
# 2. データの読み込み
# -------------------------------------------------------------------
@st.cache_data
def load_data():
    # 💡 ファイル名を新しいデータベースに変更
    try:
        with open("master_data_final.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

data = load_data()

# -------------------------------------------------------------------
# 3. AI（Gemini）の設定
# -------------------------------------------------------------------
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    pass

# -------------------------------------------------------------------
# 4. 関数定義
# -------------------------------------------------------------------
def search_dictionary(query):
    query = query.replace(" ", "").replace("　", "")
    for item in data:
        if query in item.get("検索キーワード", []):
            return item
    return None

def ai_correct_query(query):
    try:
        prompt = f"ユーザーが和食用語「{query}」を入力しましたが辞書に見つかりません。最も可能性の高い正しい「ひらがな1単語」だけを出力してください。"
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return query

def translate_text(term, yomi, meaning, target_lang):
    try:
        prompt = f"以下の和食用語の解説を、指定された言語（{target_lang}）に翻訳してください。出力は「【用語（ローマ字）- 翻訳した用語】\n\n翻訳した解説」の形式にしてください。\n用語: {term} ({yomi})\n解説: {meaning}"
        
        # 指数バックオフによるリトライ機能
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = model.generate_content(prompt)
                return response.text
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return f"Error: API is currently busy. Please try again later.\n\nOriginal Text: {meaning}"
    except:
        return f"Error: Translation failed.\n\nOriginal Text: {meaning}"

# -------------------------------------------------------------------
# 5. セッションステート管理
# -------------------------------------------------------------------
if "selected_lang_name" not in st.session_state:
    st.session_state.selected_lang_name = "English"
if "answer" not in st.session_state:
    st.session_state.answer = ""
if "found_item" not in st.session_state:
    st.session_state.found_item = None

# -------------------------------------------------------------------
# 6. アプリケーションUIとロジック
# -------------------------------------------------------------------
st.title("Washoku Voice Dictionary")

# 言語選択
selected_lang = st.selectbox("🌐 Select Language:", list(lang_options.keys()))
st.session_state.selected_lang_name = selected_lang

with st.expander("🌍 Supported Languages"):
    st.write(", ".join(list(lang_options.keys())))

# 入力フォーム
user_input = st.text_input(ui["input_label"])
submit_button = st.button(ui["submit"])

if submit_button:
    if user_input:
        # === 👇 スマホのキーボードを強制的に引っ込める魔法（全端末・安全対応版） 👇 ===
        components.html(
            """
            <script>
            try {
                var inputs = window.parent.document.querySelectorAll('input');
                for (var i = 0; i < inputs.length; i++) {
                    inputs[i].blur();
                }
            } catch (e) {
            }
            </script>
            """,
            height=0
        )
        # === 👆 ここまで 👆 ===
        
        with st.spinner(ui["thinking"]):
            found_item = search_dictionary(user_input)
            
            if not found_item:
                corrected_input = ai_correct_query(user_input)
                found_item = search_dictionary(corrected_input)

            if found_item:
                # 💡 JSONの新しい項目名「辞書用_100文字要約」からデータを取得
                meaning = found_item.get("辞書用_100文字要約", "")
                st.session_state.answer = translate_text(
                    found_item.get('用語', ''), 
                    found_item.get('読み', ''), 
                    meaning, 
                    st.session_state.selected_lang_name
                )
                st.session_state.found_item = found_item
            else:
                st.session_state.answer = ui["not_found_msg"]
                st.session_state.found_item = None
                
                # === 👇 スマホのキーボードを強制的に引っ込める魔法（データなし時） 👇 ===
                components.html(
                    """
                    <script>
                    try {
                        var inputs = window.parent.document.querySelectorAll('input');
                        for (var i = 0; i < inputs.length; i++) {
                            inputs[i].blur();
                        }
                    } catch (e) {}
                    </script>
                    """,
                    height=0
                )
                # === 👆 ここまで 👆 ===
    else:
        # === 👇 スマホのキーボードを強制的に引っ込める魔法（空欄時） 👇 ===
        components.html(
            """
            <script>
            try {
                var inputs = window.parent.document.querySelectorAll('input');
                for (var i = 0; i < inputs.length; i++) {
                    inputs[i].blur();
                }
            } catch (e) {}
            </script>
            """,
            height=0
        )
        # === 👆 ここまで 👆 ===
        
        st.warning(ui["warning"])

# 結果表示
if st.session_state.answer:
    st.write(ui["answer"])
    st.info(st.session_state.answer)
    
    # ミニコラムへの誘導ボタン
    if st.session_state.found_item and st.session_state.found_item.get("has_column"):
        romaji = st.session_state.found_item.get("検索キーワード", [""])[-1]
        link_url = f"https://nihongosound.com/column/{romaji}"
        st.markdown(f'<a href="{link_url}" target="_blank"><button style="background-color:#4CAF50;color:white;padding:10px;border:none;border-radius:5px;cursor:pointer;">View Photos & Column</button></a>', unsafe_allow_html=True)
    
    # 音声再生
    st.write("---")
    st.write(ui["voice"])
    components.html(
        f"""
        <div style="text-align: center; margin-top: 10px;">
            <button onclick="speakText()">🔊 Play Audio</button>
        </div>
        <script>
        function speakText() {{
            const text = `{st.session_state.answer.replace('`', '')}`;
            const langCode = "{lang_options.get(st.session_state.selected_lang_name, 'en-US')}";
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = langCode;
            window.speechSynthesis.speak(utterance);
        }}
        </script>
        """,
        height=50
    )

# -------------------------------------------------------------------
# 7. フッター・注意書き・利用規約（泥棒対策＆案内）
# -------------------------------------------------------------------
st.markdown("---")

# 一般ユーザーへの優しいご案内（PC推奨、リトライなど）
st.markdown("<div style='font-size: 0.8rem; color: gray; text-align: center;'>"
            "※If the app doesn't load or an error occurs, please wait a moment and retry, or try accessing it from a PC browser.<br>"
            "※Pronunciation may sound unnatural depending on your device's TTS engine."
            "</div>", unsafe_allow_html=True)

# 泥棒への威嚇（折りたたまない）
st.markdown("<div style='font-size: 0.8rem; color: gray; text-align: center; margin-top: 10px; font-weight: bold;'>"
            "Data extraction and AI training are strictly prohibited."
            "</div>", unsafe_allow_html=True)

# 利用規約の折りたたみ（免責と違約金）
with st.expander("📜 Terms of Use & Disclaimer"):
    st.markdown("""
    **Disclaimer:**
    This application is provided for free. We do not offer support or respond to inquiries regarding errors or compatibility issues. 
    
    **Prohibited Actions & Penalty:**
    Any unauthorized extraction of dictionary data or use of this site's content for AI training purposes is strictly prohibited. 
    By violating this rule, you agree to pay a penalty of 1,000,000 JPY per extracted item.
    
    **Credits:**
    Powered by Streamlit and Google AI.
    """)