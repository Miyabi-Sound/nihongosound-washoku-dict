import streamlit as st
import google.generativeai as genai
import os
import streamlit.components.v1 as components
from dotenv import load_dotenv
import json
import time
from google.api_core import exceptions
import requests  # 👈 GitHubのAPI（裏口）と通信するためのパーツ

# 🌟 複数アプリ展開用：ブラウザのタブ名やアイコンを完全特化
st.set_page_config(page_title="Washoku Voice Dictionary", page_icon="🍣")

# --- 🌟 1. APIキーの読み込みとAIの初期化 ---
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    generation_config={"temperature": 0.0}
)

# --- 🌟 2. JSON辞書の読み込み（分離アーキテクチャ版：Private金庫から取得） ---
@st.cache_data
def load_dictionary():
    try:
        # Streamlitの「Secrets（電子金庫）」から合鍵を取り出す
        github_token = st.secrets["GITHUB_TOKEN"]
        repo_owner = st.secrets["REPO_OWNER"] # あなたのGitHubユーザー名 (Miyabi-Sound)
        repo_name = st.secrets["REPO_NAME"]   # 辞書データを隠したPrivateリポジトリ名
        file_path = "master_data_final.json" # 👈 【修正】ファイル名を変更

        # GitHubの専用裏口（API）にアクセスしてデータを直接もらう
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{file_path}"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3.raw"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status() # エラーがないかチェック
        return response.json()
    except Exception as e:
        # 💡【保険】手元のVS Codeでテストする時はSecretsがないため、同じフォルダのファイルを読む
        try:
            with open('master_data_final.json', 'r', encoding='utf-8') as f: # 👈 【修正】ここも変更
                return json.load(f)
        except:
            return []

dict_data = load_dictionary()

# カタカナを問答無用でひらがなに変換する魔法のツール（アイゴ対策！）
def kata_to_hira(text):
    return "".join(chr(ord(ch) - 96) if 0x30A1 <= ord(ch) <= 0x30F6 else ch for ch in text)

def search_dictionary(user_input):
    # 空白を消し、カタカナを「強制的にひらがな」に変換して検索！
    clean_input = user_input.lower().replace(" ", "").replace("　", "").strip()
    query = kata_to_hira(clean_input)
    
    for item in dict_data:
        term = item.get("用語", "").replace(" ", "").replace("　", "").lower()
        yomi = item.get("読み", "").replace(" ", "").replace("　", "").lower()
        keywords = [k.lower().replace(" ", "").replace("　", "") for k in item.get("検索キーワード", [])]
        if query == term or query == yomi or query in keywords:
            return item
    return None

# --- 🌟 3. 当て字と空白を「完璧なひらがな」に自動補正するAI ---
def ai_correct_query(text):
    prompt = f"""
ユーザーが和食用語を音声入力しましたが、誤変換や当て字、不要な空白が含まれています。
入力: 「{text}」
この言葉から推測される正しい和食用語の「ひらがな」のみを1単語で出力してください。
余計な記号や説明、空白は一切含めないでください。
"""
    try:
        response = model.generate_content(prompt)
        return response.text.strip().replace(" ", "").replace("　", "").replace("\n", "")
    except:
        return text

# --- 🌟 4. 課題要件：AI翻訳と自動リトライ機能（すべてのエラーに対応してリトライ） ---
@st.cache_data
def translate_text(term, yomi, meaning, target_lang, max_retries=3):
    if target_lang == "日本語 (Japanese)":
        return f"【{term}（{yomi}）】\n{meaning}"
        
    prompt = f"""
あなたはプロの翻訳家です。以下の和食用語と意味を「{target_lang}」に翻訳してください。
必ず以下のフォーマットで出力してください。元の意味にない情報は絶対に付け加えないでください。

【{term}（{yomi}） - [読みのローマ字表記（頭文字は大文字）]】
[意味の翻訳]

【データ】
意味: {meaning}
"""

    # 💡 改善：どんなAIのエラー（制限・混雑）が起きても、必ず数秒待ってから自動リトライする！
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt) # 1秒、2秒と徐々に待機時間を延ばして再挑戦
                continue
    return "AI translation is currently busy due to high traffic. Please wait a moment and try again."

POPULAR_TERMS = {
    "sushi": "【寿司（すし） - Sushi】\nVinegared rice combined with ingredients like raw seafood, representing traditional Japanese cuisine.",
    "tempura": "【天ぷら（てんぷら） - Tempura】\nSeafood or vegetables coated in a light batter and deep-fried until crispy.",
    "sashimi": "【刺身（さしみ） - Sashimi】\nThinly sliced, fresh raw seafood typically enjoyed with soy sauce and wasabi.",
    "dashi": "【出汁（だし） - Dashi】\nA foundational Japanese soup stock rich in Japanese umami, often made from kelp and bonito flakes.",
    "umami": "【旨味（うまみ） - Umami】\nThe fifth basic taste, translating to 'pleasant savory taste', fundamental to Japanese cuisine."
}

# --- 🌟 5. UIとアクセシビリティ ---
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "light"

theme_toggle = st.toggle("🌙 Eye-Care Mode (Dark Theme)", value=(st.session_state.theme_mode == "dark"))

if theme_toggle and st.session_state.theme_mode == "light":
    st.session_state.theme_mode = "dark"
    st._config.set_option("theme.backgroundColor", "#121212")
    st._config.set_option("theme.secondaryBackgroundColor", "#212529")
    st._config.set_option("theme.textColor", "#E0E0E0")
    st.rerun()
elif not theme_toggle and st.session_state.theme_mode == "dark":
    st.session_state.theme_mode = "light"
    st._config.set_option("theme.backgroundColor", "#FFFFFF")
    st._config.set_option("theme.secondaryBackgroundColor", "#F0F2F6")
    st._config.set_option("theme.textColor", "#333333")
    st.rerun()

is_dark = st.session_state.theme_mode == "dark"
html_text_color = "#E0E0E0" if is_dark else "#333333"
html_subtext_color = "#AAAAAA" if is_dark else "#666666"
tips_bg_color = "#1E1E1E" if is_dark else "#f8f9fa"
player_bg_color = "#1E1E1E" if is_dark else "#ffffff"
player_border_color = "#333333" if is_dark else "#ccc"
note_bg_color = "#2c3e50" if is_dark else "#f0f4f8"
note_text_color = "#E0E0E0" if is_dark else "#444444"
input_bg_color = "#212529" if is_dark else "#fdfefe"
input_text_color = "#ffffff" if is_dark else "#333333"

st.markdown(f"""
<style>
html {{ font-size: 18px; }}
textarea, input {{ font-size: 1.2rem!important; }}
body {{ font-family: 'Hiragino Mincho ProN', 'MS Mincho', serif; }}
.title-text {{ text-align: left; font-size: 32px; font-weight: bold; margin-bottom: 5px;}}
.itamae-answer {{ padding: 20px; border-radius: 8px; box-shadow: 2px 2px 10px rgba(0,0,0,0.1); line-height: 1.8; border: 1px solid #ddd;}}
[data-testid="stTextInput"] input {{ border: 2px solid #3498db !important; background-color: {input_bg_color} !important; color: {input_text_color} !important; padding: 10px !important; }}
div[data-testid="stSelectbox"] > div > div {{ background-color: {input_bg_color} !important; color: {input_text_color} !important; }}
div[data-testid="stSelectbox"] label p, div[data-testid="stTextInput"] label p {{
font-size: 1rem !important;
font-weight: normal !important;
color: {html_text_color} !important;
}}
div[data-testid="stForm"] {{ margin-top: 0px !important; }}
iframe {{ margin-top: -15px !important; }}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title-text">🍣 Washoku Voice Dictionary <span style="color: #e74c3c; font-size: 18px; font-weight: normal;">[Beta Test]</span></div>', unsafe_allow_html=True)

st.caption("※ [Notice] This app is currently in Beta testing.")
st.caption("※ Powered by Gemini AI")
st.caption("※ Gemini is an AI and may sometimes make mistakes.")
st.caption("※ This guide uses a free AI system.")
st.caption("※ Access may be temporarily unstable due to high traffic.")

with st.expander("ℹ️ Note on AI Response Time"):
    st.markdown("""
If the AI is experiencing high traffic, it may take a little longer to respond. Please wait a moment.
If you receive a 'High Traffic' error, please wait a few minutes and press the 'Search' button again.
""")

st.markdown("<hr style='margin-top: 0px; margin-bottom: 20px;'>", unsafe_allow_html=True)

if 'answer' not in st.session_state:
    st.session_state.answer = None

if 'main_user_input' not in st.session_state:
    st.session_state.main_user_input = ""

lang_options = {
    "English (US)": "en-US", "English (UK)": "en-GB", "日本語 (Japanese)": "ja-JP",
    "Français (French)": "fr-FR", "Español (Spanish)": "es-ES", "简体中文 (Chinese Simplified)": "zh-CN",
    "繁體中文 (Chinese Traditional)": "zh-TW", "한국어 (Korean)": "ko-KR", "Deutsch (German)": "de-DE",
    "Italiano (Italian)": "it-IT", "Português (Brazil)": "pt-BR", "Português (Portugal)": "pt-PT",
    "Русский (Russian)": "ru-RU", "العربية (Arabic)": "ar-SA", "हिन्दी (Hindi)": "hi-IN",
    "Afrikaans": "af-ZA", "Shqip (Albanian)": "sq-AL", "አማርኛ (Amharic)": "am-ET", "Հայերեն (Armenian)": "hy-AM",
    "Azərbaycan dili (Azerbaijani)": "az-AZ", "Euskara (Basque)": "eu-ES", "বাংলা (Bengali)": "bn-IN", "Bosanski (Bosnian)": "bs-BA",
    "Български (Bulgarian)": "bg-BG", "Català (Catalan)": "ca-ES", "Hrvatski (Croatian)": "hr-HR", "Čeština (Czech)": "cs-CZ",
    "Dansk (Danish)": "da-DK", "Nederlands (Dutch)": "nl-NL", "Eesti (Estonian)": "et-EE", "Filipino": "fil-PH",
    "Suomi (Finnish)": "fi-FI", "Galego (Galician)": "gl-ES", "ქართული (Georgian)": "ka-GE", "Ελληνικά (Greek)": "el-GR",
    "ગુજરાતી (Gujarati)": "gu-IN", "עברית (Hebrew)": "he-IL", "Magyar (Hungarian)": "hu-HU", "Íslenska (Icelandic)": "is-IS",
    "Bahasa Indonesia (Indonesian)": "id-ID", "Basa Jawa (Javanese)": "jv-ID", "ಕನ್ನಡ (Kannada)": "kn-IN", "Қазақ тілі (Kazakh)": "kk-KZ",
    "ខ្មែរ (Khmer)": "km-KH", "ລາວ (Lao)": "lo-LA", "Latviešu (Latvian)": "lv-LV", "Lietuvių (Lithuanian)": "lt-LT",
    "Македонски (Macedonian)": "mk-MK", "Bahasa Melayu (Malay)": "ms-MY", "മലയാളം (Malayalam)": "ml-IN", "मराठी (Marathi)": "mr-IN",
    "Монгол (Mongolian)": "mn-MN", "नेपाली (Nepali)": "ne-NP", "Norsk (Norwegian)": "no-NO", "فارسی (Persian)": "fa-IR",
    "Polski (Polish)": "pl-PL", "ਪੰਜਾਬੀ (Punjabi)": "pa-IN", "Română (Romanian)": "ro-RO", "Српски (Serbian)": "sr-RS",
    "සිංහල (Sinhala)": "si-LK", "Slovenčina (Slovak)": "sk-SK", "Slovenščina (Slovenian)": "sl-SI", "Basa Sunda (Sundanese)": "su-ID",
    "Kiswahili (Swahili)": "sw-KE", "Svenska (Swedish)": "sv-SE", "தமிழ் (Tamil)": "ta-IN", "తెలుగు (Telugu)": "te-IN",
    "ไทย (Thai)": "th-TH", "Türkçe (Turkish)": "tr-TR", "Українська (Ukrainian)": "uk-UA", "اردو (Urdu)": "ur-PK",
    "Oʻzbekcha (Uzbek)": "uz-UZ", "Tiếng Việt (Vietnamese)": "vi-VN", "isiZulu (Zulu)": "zu-ZA"
}

with st.expander("🌍 84 Langs (List only 👇)"):
    st.write(", ".join(list(lang_options.keys())))

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

default_lang_index = list(lang_options.keys()).index("English (US)")
st.selectbox("🌐 Select Language", list(lang_options.keys()), index=default_lang_index, key="selected_lang_name")
lang_code = lang_options[st.session_state.selected_lang_name]

st.markdown(f"""
<div style="background-color: {tips_bg_color}; padding: 10px; border-radius: 6px; margin-bottom: 15px; font-size: 15px;">
<b>🔥 Popular Terms:</b>
<a href="?word=sushi" target="_self" style="text-decoration: none; color: #3498db; font-weight: bold; margin: 0 5px;">sushi</a> |
<a href="?word=tempura" target="_self" style="text-decoration: none; color: #3498db; font-weight: bold; margin: 0 5px;">tempura</a> |
<a href="?word=sashimi" target="_self" style="text-decoration: none; color: #3498db; font-weight: bold; margin: 0 5px;">sashimi</a> |
<a href="?word=dashi" target="_self" style="text-decoration: none; color: #3498db; font-weight: bold; margin: 0 5px;">dashi</a> |
<a href="?word=umami" target="_self" style="text-decoration: none; color: #3498db; font-weight: bold; margin: 0 5px;">umami</a>
</div>
""", unsafe_allow_html=True)

if "word" in st.query_params and not st.session_state.get("query_processed", False):
    query_word = st.query_params["word"].lower()
    st.session_state.main_user_input = query_word
    lang_name = st.session_state.get("selected_lang_name", "English (US)")
    with st.spinner(ui["thinking"]):
        found_item = search_dictionary(query_word)
        if found_item:
            # 👈 【修正】新しい項目名「辞書用_100文字要約」を使う！
            st.session_state.answer = translate_text(found_item['用語'], found_item['読み'], found_item.get('辞書用_100文字要約', ''), lang_name)
            st.session_state.found_item = found_item
        elif query_word in POPULAR_TERMS and lang_name == "English (US)":
            st.session_state.answer = POPULAR_TERMS[query_word]
            st.session_state.found_item = None
        else:
            st.session_state.answer = ui["not_found_msg"]
            st.session_state.found_item = None
        st.session_state.query_processed = True

with st.form(key='chat_form'):
    user_input = st.text_input(ui["input_label"], key="main_user_input")
    submit_button = st.form_submit_button(ui["submit"])

    mic_html = f"""
    <div style="margin-bottom: 0px;">
    <div style="display: flex; align-items: center; background-color: {tips_bg_color}; padding: 12px 15px; border-radius: 6px; border-left: 4px solid #2ecc71;">
    <button type="button" id="mic-btn" style="padding: 7px 12px; border-radius: 20px; border: 2px solid #3498db; background: {player_bg_color}; color: #3498db; cursor: pointer; font-weight: bold; font-size: 14px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); flex-shrink: 0;">
    🎤 Voice Input
    </button>
    <span id="mic-status" style="font-size: 14px; color: {html_subtext_color}; margin-left: 8px; margin-right: 12px; font-family: sans-serif; white-space: nowrap; min-width: 20px;"></span>
    <div style="font-size: 13.5px; color: {html_text_color}; font-family: sans-serif; line-height: 1.4;">
    🔊 <b>Audio player</b> will be generated at the bottom.<br>
    💡 You can use <b>Voice</b>, or <b>type text</b> in the box above.<br>
    ⚠️ <b>Note:</b> Pronunciation or accents may occasionally sound unnatural.
    </div>
    </div>
    </div>
    <script>
    const micBtn = document.getElementById('mic-btn');
    const micStatus = document.getElementById('mic-status');
    if ('webkitSpeechRecognition' in window) {{
        const recognition = new webkitSpeechRecognition();
        recognition.lang = "ja-JP";
        recognition.interimResults = false;
        micBtn.addEventListener('click', () => {{
            recognition.start();
            micStatus.textContent = "🎙️ Listening...";
        }});
        recognition.onresult = (event) => {{
            const text = event.results.item(0).item(0).transcript;
            micStatus.textContent = "✅";
            const inputs = window.parent.document.querySelectorAll('input[type="text"]');
            let inputField = null;
            for (let i = 0; i < inputs.length; i++) {{
                if (inputs[i].getAttribute('aria-label') === "{ui['input_label']}") {{ inputField = inputs[i]; break; }}
            }}
            if (!inputField && inputs.length > 0) {{ inputField = inputs[inputs.length - 1]; }}
            if(inputField) {{
                let nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                nativeSetter.call(inputField, text);
                inputField.dispatchEvent(new Event('input', {{ bubbles: true}}));
                inputField.focus();
                setTimeout(() => {{
                    const buttons = window.parent.document.querySelectorAll('button');
                    buttons.forEach(btn => {{ if(btn.innerText.includes("{ui['submit']}")) {{ btn.click(); }} }});
                }}, 300);
            }}
        }};
        recognition.onerror = (event) => {{ micStatus.textContent = "❌ Error: " + event.error; }};
    }} else {{
        micBtn.style.display = 'none';
        micStatus.textContent = "Your browser does not support Voice Input.";
    }}
    </script>
    """
    components.html(mic_html, height=200)

if submit_button:
    if user_input:
        # 👇 魔法1：検索開始時にキーボードを隠す（古いiPhoneでもエラーが出ない安全版）
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
        
        with st.spinner(ui["thinking"]):
            found_item = search_dictionary(user_input)
            if not found_item:
                corrected_input = ai_correct_query(user_input)
                found_item = search_dictionary(corrected_input)
                
            if found_item:
                # 👈 【修正】新しい項目名「辞書用_100文字要約」を使う！
                st.session_state.answer = translate_text(found_item['用語'], found_item['読み'], found_item.get('辞書用_100文字要約', ''), st.session_state.selected_lang_name)
                st.session_state.found_item = found_item
            else:
                st.session_state.answer = ui["not_found_msg"]
                st.session_state.found_item = None
                
                # 👇 魔法2：データなし時にキーボードを隠す（古いiPhoneでもエラーが出ない安全版）
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
    else:
        # 👇 魔法3：空欄でボタンを押した時にキーボードを隠す（古いiPhoneでもエラーが出ない安全版）
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
        st.warning(ui["warning"])

if st.session_state.answer:
    answer = st.session_state.answer
    st.write(ui["answer"])
    st.markdown(f'<div class="itamae-answer">{answer}</div>', unsafe_allow_html=True)
    
    if st.session_state.get("found_item") and st.session_state.found_item.get("has_column"):
        romaji_words = [w for w in st.session_state.found_item["検索キーワード"] if w.isascii()]
        romaji_word = romaji_words if romaji_words else "washoku" # 👈 少し修正
        target_url = f"https://nihongosound.com/en/gallery/{romaji_word}"
        st.link_button("🖼️ View Photos & Column", target_url)
        
    js_answer = answer.replace('\\', '\\\\').replace('\n', ' ').replace('\r', '').replace('"', '\\"').replace("'", "\\'")
    
    html_code = f"""
    <div style="margin-top: 20px; padding: 15px; border: 1px solid {player_border_color}; border-radius: 8px; background-color: {player_bg_color}; color: {html_text_color}; font-family: sans-serif;">
    <div style="margin-bottom: 10px;">
    <label style="font-weight: bold; margin-right: 10px;">{ui['voice']} </label>
    <select id="voice-select" style="margin-right: 15px; padding: 5px; border-radius: 4px; max-width: 100%; background-color: {player_bg_color}; color: {html_text_color}; border: 1px solid {player_border_color};"></select>
    </div>
    <div style="margin-bottom: 15px;">
    <label style="font-weight: bold; margin-right: 10px;">{ui['speed']} </label>
    <input type="range" id="rate-slider" min="0.5" max="1.5" value="1.0" step="0.1" style="vertical-align: middle; width: 50%;">
    <span id="rate-value" style="margin-left: 5px; font-weight: bold;">1.0</span>
    </div>
    <div style="background-color: {note_bg_color}; border-left: 4px solid #3498db; padding: 10px; margin-bottom: 15px; border-radius: 2px;">
    <p style="font-size: 13px; font-weight: bold; margin: 0; color: {note_text_color};">{ui['note']}</p>
    </div>
    <div style="display: flex; flex-wrap: wrap; gap: 5px;">
    <button id="play-btn" style="padding: 8px 15px; background: #2c3e50; color: #fff; border: none; border-radius: 4px; cursor: pointer;">{ui['play']}</button>
    <button id="pause-btn" style="padding: 8px 15px; background: #f39c12; color: #fff; border: none; border-radius: 4px; cursor: pointer;">{ui['pause']}</button>
    <button id="resume-btn" style="padding: 8px 15px; background: #27ae60; color: #fff; border: none; border-radius: 4px; cursor: pointer;">{ui['resume']}</button>
    <button id="stop-btn" style="padding: 8px 15px; background: #c0392b; color: #fff; border: none; border-radius: 4px; cursor: pointer;">{ui['stop']}</button>
    </div>
    </div>
    <script>
    const text = "{js_answer}";
    const langCode = "{lang_code}";
    const notFoundText = "{ui['not_found']}";
    const voiceSelect = document.getElementById('voice-select');
    const rateSlider = document.getElementById('rate-slider');
    const rateValue = document.getElementById('rate-value');
    const playBtn = document.getElementById('play-btn');
    const pauseBtn = document.getElementById('pause-btn');
    const resumeBtn = document.getElementById('resume-btn');
    const stopBtn = document.getElementById('stop-btn');
    let voices = [];
    function populateVoiceList() {{
        voices = speechSynthesis.getVoices();
        if (voices.length === 0) return;
        voiceSelect.innerHTML = '';
        let filteredVoices = voices.filter(voice => voice.lang.startsWith(langCode.substring(0, 2)));
        if (langCode === "ja-JP") {{
            const googleVoices = filteredVoices.filter(voice => voice.name.includes("Google"));
            if (googleVoices.length > 0) {{ filteredVoices = googleVoices; }}
        }}
        if(filteredVoices.length === 0) {{
            const option = document.createElement('option');
            option.textContent = notFoundText;
            option.value = "";
            voiceSelect.appendChild(option);
        }} else {{
            filteredVoices.forEach(voice => {{
                const option = document.createElement('option');
                option.textContent = voice.name;
                option.value = voices.indexOf(voice);
                voiceSelect.appendChild(option);
            }});
        }}
    }}
    populateVoiceList();
    if (speechSynthesis.onvoiceschanged !== undefined) {{ speechSynthesis.onvoiceschanged = populateVoiceList; }}
    let retries = 0;
    let voiceTimer = setInterval(() => {{
        if(speechSynthesis.getVoices().length > 0) {{ populateVoiceList(); clearInterval(voiceTimer); }}
        retries++;
        if(retries > 50) clearInterval(voiceTimer);
    }}, 100);
    rateSlider.addEventListener('input', () => {{ rateValue.textContent = parseFloat(rateSlider.value).toFixed(1); }});
    playBtn.addEventListener('click', () => {{
        speechSynthesis.cancel();
        const utterThis = new SpeechSynthesisUtterance(text);
        const selectedGlobalIndex = voiceSelect.value;
        if(selectedGlobalIndex !== "") {{ utterThis.voice = voices[selectedGlobalIndex]; }}
        utterThis.lang = langCode;
        utterThis.rate = parseFloat(rateSlider.value);
        speechSynthesis.speak(utterThis);
    }});
    pauseBtn.addEventListener('click', () => {{ speechSynthesis.pause(); }});
    resumeBtn.addEventListener('click', () => {{ speechSynthesis.resume(); }});
    stopBtn.addEventListener('click', () => {{ speechSynthesis.cancel(); }});
    </script>
    """
    components.html(html_code, height=270)

st.markdown("""
<div style='text-align: center; color: #888; font-size: 12px; margin-top: 50px;'>
⚠️ Data extraction and AI training are strictly prohibited.<br>
By using this service, you agree to these terms. (No user support provided)<br>
&copy; 2026 Nihongo Sound. All rights reserved. Designed by Nihongosound
</div>
""", unsafe_allow_html=True)