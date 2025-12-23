import streamlit as st
import requests
import json
from datetime import datetime
import os
import re
import time
import uuid
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_URL = os.getenv("API_URL", "http://api:8000")
WEBSITE_URL = os.getenv("WEB_URL", "http://localhost:8501")
TG_BOT_URL = "https://t.me/moodboard_creator_bot"

st.set_page_config(
    page_title="MoodBoard - Ваше пространство для вдохновения",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)


def get_file_url(filepath: str) -> str:
    if not filepath:
        return ""

    if filepath.startswith(("http://", "https://")):
        return filepath

    if filepath.startswith("/static/"):
        base_url = os.getenv("BASE_URL", WEBSITE_URL)
        return f"{base_url}{filepath}"

    return filepath


st.markdown("""
<style>
    .main-container {
        display: flex;
        width: 100vw;
        height: 100vh;
        overflow: hidden;
    }

    .board-area {
        background: #FFFFFF;
        min-height: 100vh;
        display: flex;
        flex-direction: column;
        align-items: center;
    }

    .board-area.full-width {
        margin-left: 0;
        background: #FFFFFF;
    }

    .panel-toggle-btn {
        position: fixed;
        left: 20px;
        top: 20px;
        z-index: 1001;
        background: #667eea;
        color: white;
        border: none;
        border-radius: 50%;
        width: 50px;
        height: 50px;
        font-size: 24px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 10px rgba(102, 126, 234, 0.3);
        transition: all 0.3s ease;
    }

    .panel-toggle-btn:hover {
        transform: scale(1.1);
        background: #5a67d8;
    }

    .board-container {
        background: #E0FFFF !important;
        border: 4px solid #5D4037 !important;
        border-radius: 12px !important;
        box-shadow: 0 12px 35px rgba(93, 64, 55, 0.25) !important;
        position: relative !important;
        min-height: 700px !important;
        width: 100% !important;
        max-width: 1200px !important;
        aspect-ratio: 4/3 !important;
        overflow: hidden !important;
        cursor: default !important;
        margin: 20px auto !important;
        display: block !important;
    }

    .board-elements-container {
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        width: 100% !important;
        height: 100% !important;
        pointer-events: none !important;
    }

    .board-element {
        position: absolute;
        border-radius: 6px;
        box-shadow: 0 3px 12px rgba(0,0,0,0.2);
        border: 2px solid #999;
        overflow: hidden;
        cursor: default;
        transition: none;
        user-select: none;
        min-width: 50px;
        min-height: 50px;
        pointer-events: auto;
        background: white;
        box-sizing: border-box;
    }

    .board-element:hover {
        border-color: #777;
    }

    .board-element.text {
        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
        padding: 12px 15px;
        border: 1px solid #aaa;
    }

    .board-element.image {
        background: white;
        padding: 8px;
        border: 1px solid #aaa;
    }

    .element-text-content {
        font-size: 16px;
        line-height: 1.5;
        color: #333;
        width: 100%;
        height: 100%;
        overflow: auto;
        word-wrap: break-word;
    }

    .element-image-content {
        width: 100%;
        height: 100%;
        object-fit: contain;
        border-radius: 4px;
    }

    .panel-section {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        border: 1px solid #e0e0e0;
    }

    .section-title {
        color: #667eea;
        font-weight: bold;
        margin-bottom: 15px;
        padding-bottom: 10px;
        border-bottom: 2px solid #e9ecef;
        font-size: 16px;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .cursor-coords {
        position: fixed;
        background: rgba(93, 64, 55, 0.95);
        color: white;
        padding: 10px 18px;
        border-radius: 10px;
        font-size: 14px;
        font-weight: bold;
        z-index: 2000;
        box-shadow: 0 6px 15px rgba(0,0,0,0.3);
        pointer-events: none;
        border: 1px solid rgba(255,255,255,0.2);
    }

    .element-button {
        width: 100%;
        padding: 12px 15px;
        margin-bottom: 8px;
        text-align: left;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        background: white;
        cursor: pointer;
        transition: all 0.2s ease;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .element-button:hover {
        background: #f8f9fa;
        border-color: #667eea;
    }

    .element-button.active {
        background: #667eea;
        color: white;
        border-color: #667eea;
    }

    .element-button .status {
        margin-left: auto;
        font-size: 12px;
        padding: 2px 8px;
        border-radius: 10px;
        background: #e9ecef;
        color: #6c757d;
    }

    .element-button.active .status {
        background: rgba(255,255,255,0.2);
        color: white;
    }

    .element-button .status.on-board {
        background: #d4edda;
        color: #155724;
    }

    .element-button .status.off-board {
        background: #f8d7da;
        color: #721c24;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    .element-info-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 20px;
    }

    .stApp {
        background: #FFFFFF !important;
    }

    .main .block-container {
        background: #FFFFFF !important;
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }

    .st-emotion-cache-1v0mbdj {
        background: transparent !important;
    }

    div[data-testid="stVerticalBlock"] > div > div > div > div {
        background: transparent !important;
    }

    iframe[title="streamlitComponent"] {
        background: transparent !important;
        border: none !important;
    }

    .st-emotion-cache-1y4p8pa {
        background: transparent !important;
    }

    h1, h2, h3 {
        color: #333 !important;
    }

    .stAlert {
        background: rgba(255, 255, 255, 0.9) !important;
        border: 1px solid #ddd !important;
    }

    .stButton > button {
        width: 100% !important;
        border-radius: 8px !important;
        border: 1px solid #ddd !important;
        transition: all 0.3s ease !important;
    }

    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
    }

    .stTextInput > div > div > input {
        border-radius: 8px !important;
        border: 1px solid #ccc !important;
    }

    .stSelectbox > div > div {
        border-radius: 8px !important;
        border: 1px solid #ccc !important;
    }

    .stSlider > div > div {
        border-radius: 8px !important;
    }

    .stSpinner > div {
        background: rgba(255, 255, 255, 0.9) !important;
        border-radius: 10px !important;
        padding: 20px !important;
    }

    .stTooltip {
        background: rgba(93, 64, 55, 0.95) !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        background: white !important;
        border-radius: 10px !important;
        padding: 5px !important;
        margin-bottom: 20px !important;
    }

    .stTabs [data-baseweb="tab-panel"] {
        background: transparent !important;
    }

    .stTable table {
        background: white !important;
        border-radius: 10px !important;
        overflow: hidden !important;
        border: 1px solid #ddd !important;
    }

    [data-baseweb="modal"] {
        background: rgba(0,0,0,0.5) !important;
    }

    .stCard {
        background: white !important;
        border-radius: 12px !important;
        border: 1px solid #e0e0e0 !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08) !important;
    }

    hr {
        border-color: #ddd !important;
        margin: 30px 0 !important;
    }

    [data-testid="stSidebar"] {
        background:  #f8f9fa !important;
        border-right: 2px solid #e0e0e0 !important;
        min-width: 350px !important;
        max-width: 400px !important;
    }

    [data-testid="stSidebar"] > div:first-child {
        background: #f8f9fa !important;
    }    

    [data-testid="stSidebar"] .stMarkdown {
        color: #333 !important;
    }

    section[data-testid="stSidebar"] {
        visibility: visible !important;
        opacity: 1 !important;
        transform: none !important;
    }

    .panel-control-btn {
        background: #667eea !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 8px 16px !important;
        font-size: 14px !important;
        cursor: pointer !important;
        transition: all 0.3s ease !important;
    }

    .panel-control-btn:hover {
        background: #5a67d8 !important;
        transform: translateY(-2px) !important;
    }

    .sidebar-collapsed [data-testid="stSidebar"] {
        display: none !important;
    }

    .close-panel-btn {
        background: #ff6b6b !important;
        color: white !important;
        border: none !important;
        border-radius: 50% !important;
        width: 36px !important;
        height: 36px !important;
        font-size: 18px !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        margin-left: auto !important;
    }

    .close-panel-btn:hover {
        background: #ff5252 !important;
        transform: scale(1.1) !important;
    }

    @media (max-width: 768px) {
        .board-area {
            padding: 20px !important;
            margin-left: 0 !important;
        }

        .board-container {
            max-width: 95% !important;
            min-height: 500px !important;
        }

        .control-panel {
            width: 300px !important;
        }

        [data-testid="stSidebar"] {
            min-width: 300px !important;
            max-width: 350px !important;
        }
    }
</style>
""", unsafe_allow_html=True)


def call_api(endpoint, method="GET", data=None, params=None, token=None):
    try:
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint

        url = f"{API_URL}{endpoint}"
        headers = {"Content-Type": "application/json"}

        if token:
            headers["Authorization"] = f"Bearer {token}"

        if method == "GET":
            response = requests.get(url, params=params, headers=headers, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, params=params, headers=headers, timeout=10)
        elif method == "PUT":
            response = requests.put(url, json=data, params=params, headers=headers, timeout=10)
        elif method == "DELETE":
            response = requests.delete(url, params=params, headers=headers, timeout=10)
        else:
            return None, "Неподдерживаемый метод"

        if response.status_code in [200, 201, 204]:
            if response.text.strip():
                try:
                    return response.json(), None
                except json.JSONDecodeError:
                    return {"text": response.text}, None
            else:
                return {"success": True}, None
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get("detail",
                                           error_data.get("message",
                                                          error_data.get("error",
                                                                         f"Ошибка {response.status_code}")))
                return None, error_msg
            except json.JSONDecodeError:
                return None, f"Ошибка {response.status_code}: {response.text[:200]}"

    except requests.exceptions.ConnectionError as e:
        return None, f"Не могу подключиться к серверу API: {str(e)}"
    except requests.exceptions.Timeout as e:
        return None, f"Таймаут подключения: {str(e)}"
    except Exception as e:
        return None, f"Ошибка при вызове API: {str(e)}"


def create_board_component(elements, board_id, view_only=False):
    board_width = st.session_state.get('board_width', 1200)
    board_height = st.session_state.get('board_height', 900)
    background_color = st.session_state.get('board_background_color', '#FFFBF0')
    border_color = st.session_state.get('board_border_color', '#5D4037')
    logger.debug(f"Board settings - Width: {board_width}, Height: {board_height}")
    logger.debug(f"Board colors - Background: {background_color}, Border: {border_color}")
    elements_on_board = []
    for element in elements:
        x = element.get('x_position', 0) or 0
        y = element.get('y_position', 0) or 0
        width = element.get('width', 0) or 0
        height = element.get('height', 0) or 0
        if (x > 0 and y > 0) or (width > 0 and height > 0):
            elements_on_board.append(element)
    sorted_elements = sorted(elements_on_board, key=lambda x: x.get('z_index', 1) or 1)
    elements_html = ""
    for element in sorted_elements:
        element_id = element['id']
        x = element.get('x_position', 0) or 0
        y = element.get('y_position', 0) or 0
        width = max(element.get('width', 100) or 100, 50)
        height = max(element.get('height', 80) or 80, 50)
        z_index = element.get('z_index', 1) or 1
        element_type = element.get('type', 'text')
        styles = f"""
            position: absolute;
            left: {x}px;
            top: {y}px;
            width: {width}px;
            height: {height}px;
            z-index: {z_index};
            border-radius: 6px;
            box-shadow: 0 3px 12px rgba(0,0,0,0.2);
            border: 2px solid #999;
            overflow: hidden;
            cursor: default;
            user-select: none;
            pointer-events: auto;
            box-sizing: border-box;
        """
        if element_type == 'text':
            content = element.get('content', '')
            styles += "background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%); border: 1px solid #aaa; padding: 12px 15px;"
            inner_html = f'<div style="font-size: 16px; line-height: 1.5; color: #333; width: 100%; height: 100%; overflow: auto; word-wrap: break-word;">{content}</div>'
        else:
            image_url = element.get('content_url') or element.get('content', '')
            if not image_url.startswith(('http://', 'https://', '/')):
                image_url = get_file_url(image_url)
            styles += "background: white; border: 1px solid #aaa; padding: 8px;"
            inner_html = f'''
            <div style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; background: #f8f9fa;">
                <img src="{image_url}" style="max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 2px;" alt="Изображение">
            </div>
            '''
        elements_html += f'''
        <div style="{styles}" 
             data-id="{element_id}" 
             data-type="{element_type}">
            {inner_html}
        </div>
        '''
    html = f'''
    <div style="display: flex; justify-content: center; align-items: flex-start; width: 100%; height: 100%; padding: 20px;">
        <div id="board-{board_id}" 
             style="background: {background_color}; 
                    border: 4px solid {border_color}; 
                    border-radius: 12px; 
                    box-shadow: 0 12px 35px rgba(93, 64, 55, 0.25); 
                    position: relative; 
                    min-height: {board_height}px; 
                    width: 100%; 
                    max-width: {board_width}px; 
                    aspect-ratio: {board_width}/{board_height}; 
                    overflow: hidden; 
                    cursor: default; 
                    margin: 20px auto;">

            <div id="board-container-{board_id}"
                 style="position: absolute; 
                        top: 0; 
                        left: 0; 
                        width: 100%; 
                        height: 100%; 
                        pointer-events: none;">
                {elements_html}
            </div>

            <div id="cursor-coords" style="display: none; position: fixed; background: rgba(93, 64, 55, 0.95); color: white; padding: 10px 18px; border-radius: 10px; font-size: 14px; font-weight: bold; z-index: 2000; box-shadow: 0 6px 15px rgba(0,0,0,0.3); pointer-events: none; border: 1px solid rgba(255,255,255,0.2);">
                📍 X: <span id="cursor-x">0</span> | Y: <span id="cursor-y">0</span>
            </div>
        </div>
    </div>

    <script>
        function sendClickData(type, data) {{
            window.parent.postMessage({{
                type: type,
                ...data
            }}, '*');
        }}
        const boardElement = document.getElementById('board-{board_id}');
        const boardContainer = document.getElementById('board-container-{board_id}');
        boardElement.addEventListener('click', function(event) {{
            if (event.target === boardElement || event.target === boardContainer) {{
                const rect = boardContainer.getBoundingClientRect();
                const x = Math.round(event.clientX - rect.left);
                const y = Math.round(event.clientY - rect.top);
                console.log('Board click at:', x, y);
                sendClickData('boardClicked', {{
                    x: x,
                    y: y,
                    boardId: '{board_id}'
                }});
            }}
        }});
        boardElement.addEventListener('mousemove', function(event) {{
            const rect = boardContainer.getBoundingClientRect();
            const x = Math.round(event.clientX - rect.left);
            const y = Math.round(event.clientY - rect.top);
            const coords = document.getElementById('cursor-coords');
            document.getElementById('cursor-x').textContent = x;
            document.getElementById('cursor-y').textContent = y;
            coords.style.display = 'block';
            coords.style.left = (event.clientX + 20) + 'px';
            coords.style.top = (event.clientY - 50) + 'px';
        }});
        boardElement.addEventListener('mouseleave', function() {{
            document.getElementById('cursor-coords').style.display = 'none';
        }});
        window.addEventListener('message', function(event) {{
            const data = event.data;
            console.log('Received message:', data);
            if (data.type === 'updateElement') {{
                const element = document.querySelector(`div[data-id="${{data.elementId}}"]`);
                if (element) {{
                    if (data.x !== undefined && data.x !== null) {{
                        element.style.left = data.x + 'px';
                    }}
                    if (data.y !== undefined && data.y !== null) {{
                        element.style.top = data.y + 'px';
                    }}
                    if (data.width !== undefined && data.width !== null) {{
                        element.style.width = data.width + 'px';
                    }}
                    if (data.height !== undefined && data.height !== null) {{
                        element.style.height = data.height + 'px';
                    }}
                    if (data.zIndex !== undefined && data.zIndex !== null) {{
                        element.style.zIndex = data.zIndex;
                    }}
                    const x = data.x || 0;
                    const y = data.y || 0;
                    const width = data.width || 0;
                    const height = data.height || 0;
                    if (x === 0 && y === 0 && width === 0 && height === 0) {{
                        element.style.display = 'none';
                    }} else {{
                        element.style.display = 'block';
                    }}
                }}
            }}
            else if (data.type === 'updateBoardColors') {{
                if (data.background_color) {{
                    boardElement.style.background = data.background_color;
                }}
                if (data.border_color) {{
                    boardElement.style.borderColor = data.border_color;
                }}
            }}
            else if (data.type === 'updateBoardSize') {{
                if (data.width) {{
                    boardElement.style.maxWidth = data.width + 'px';
                    boardElement.style.aspectRatio = data.width + '/' + (data.height || boardHeight);
                }}
                if (data.height) {{
                    boardElement.style.minHeight = data.height + 'px';
                    boardElement.style.aspectRatio = (data.width || boardWidth) + '/' + data.height;
                }}
            }}
        }});
    </script>
    '''
    import streamlit.components.v1 as components
    return components.html(html, height=board_height + 100)


def load_board_settings(board_id):
    telegram_id = st.session_state.get("telegram_id")
    if not telegram_id:
        return None
    result, error = call_api(
        f"/api/boards/{board_id}/settings",
        method="GET",
        params={"telegram_id": telegram_id},
        token=st.session_state.get('access_token')
    )
    if error:
        st.error(f"❌ Ошибка при загрузке настроек: {error}")
        return None
    return result


def save_board_settings(board_id, settings):
    telegram_id = st.session_state.get("telegram_id")
    if not telegram_id:
        st.error("❌ Ошибка: не найден Telegram ID")
        return False
    result, error = call_api(
        f"/api/boards/{board_id}/settings",
        method="PUT",
        data=settings,
        params={"telegram_id": telegram_id},
        token=st.session_state.get('access_token')
    )
    if error:
        st.error(f"❌ Ошибка при сохранении настроек: {error}")
        return False
    return True


def render_control_panel():
    st.markdown("### 🎛️ Панель управления")
    st.markdown("---")
    st.markdown('<div class="panel-section">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📐 Размер доски</div>', unsafe_allow_html=True)
    current_width = st.session_state.get('board_width', 1200)
    current_height = st.session_state.get('board_height', 900)
    current_aspect = st.session_state.get('board_aspect_ratio', '4:3')
    new_aspect = st.selectbox(
        "Соотношение сторон:",
        options=["4:3", "16:9", "1:1", "3:2", "Свободное"],
        index=["4:3", "16:9", "1:1", "3:2", "Свободное"].index(current_aspect) if current_aspect in ["4:3", "16:9",
                                                                                                     "1:1", "3:2",
                                                                                                     "Свободное"] else 0,
        key="board_aspect_selector",
        help="Выберите соотношение сторон доски"
    )
    if new_aspect != current_aspect:
        st.session_state.board_aspect_ratio = new_aspect
        if new_aspect != "Свободное":
            ratio_parts = new_aspect.split(":")
            width_ratio = int(ratio_parts[0])
            height_ratio = int(ratio_parts[1])
            st.session_state.board_height = int(current_width * height_ratio / width_ratio)
    col1, col2 = st.columns(2)
    with col1:
        new_width = st.number_input(
            "Ширина доски (px):",
            min_value=400,
            max_value=2500,
            value=current_width,
            step=50,
            key="board_width_input",
            help="Ширина доски в пикселях"
        )
        if new_width != current_width:
            st.session_state.board_width = new_width
            aspect = st.session_state.get('board_aspect_ratio', '4:3')
            if aspect != "Свободное":
                ratio_parts = aspect.split(":")
                width_ratio = int(ratio_parts[0])
                height_ratio = int(ratio_parts[1])
                st.session_state.board_height = int(new_width * height_ratio / width_ratio)
    with col2:
        current_height = st.session_state.get('board_height', 900)
        if st.session_state.get('board_aspect_ratio', '4:3') != "Свободное":
            st.metric(
                "Высота доски (px):",
                f"{current_height}",
                help="Высота рассчитывается автоматически по соотношению сторон"
            )
        else:
            new_height = st.number_input(
                "Высота доски (px):",
                min_value=300,
                max_value=2000,
                value=current_height,
                step=50,
                key="board_height_input",
                help="Высота доски в пикселях"
            )
            if new_height != current_height:
                st.session_state.board_height = new_height
    current_width = st.session_state.get('board_width', 1200)
    current_height = st.session_state.get('board_height', 900)
    st.info(f"**Текущий размер:** {current_width}×{current_height}px")
    board_id = st.session_state.get('edit_board_id')
    if st.button("💾 Сохранить размер", use_container_width=True, key="save_size_btn"):
        if board_id:
            settings_to_save = {
                'board_width': st.session_state.board_width,
                'board_height': st.session_state.board_height
            }
            if save_board_settings(board_id, settings_to_save):
                st.success("✅ Размер сохранен!")
                time.sleep(1)
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-section">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🎨 Цвета доски</div>', unsafe_allow_html=True)
    board_id = st.session_state.get('edit_board_id')
    board_settings = load_board_settings(board_id) if board_id else None
    if board_settings:
        current_bg_color = board_settings.get('background_color', '#FFFBF0')
        current_border_color = board_settings.get('border_color', '#5D4037')
    else:
        current_bg_color = '#FFFBF0'
        current_border_color = '#5D4037'
    col_color1, col_color2 = st.columns(2)
    with col_color1:
        new_bg_color = st.color_picker(
            "Цвет фона:",
            value=current_bg_color,
            key="board_bg_color_picker",
            help="Выберите цвет фона доски"
        )
        st.markdown(f"""
        <div style="background: {new_bg_color}; 
                    border: 1px solid #ddd; 
                    border-radius: 5px; 
                    height: 30px; 
                    margin-top: 5px;">
        </div>
        """, unsafe_allow_html=True)
    with col_color2:
        new_border_color = st.color_picker(
            "Цвет рамки:",
            value=current_border_color,
            key="board_border_color_picker",
            help="Выберите цвет рамки доски"
        )
        st.markdown(f"""
        <div style="background: {new_border_color}; 
                    border: 1px solid #ddd; 
                    border-radius: 5px; 
                    height: 30px; 
                    margin-top: 5px;">
        </div>
        """, unsafe_allow_html=True)
    if st.button("💾 Сохранить цвета", use_container_width=True, key="save_colors_btn"):
        if board_id:
            settings_to_save = {
                'background_color': new_bg_color,
                'border_color': new_border_color
            }
            if save_board_settings(board_id, settings_to_save):
                st.success("✅ Цвета сохранены!")
                st.session_state.board_background_color = new_bg_color
                st.session_state.board_border_color = new_border_color
                time.sleep(1)
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### 📋 Элементы доски")
    board_elements = st.session_state.get('board_elements', [])
    if not board_elements:
        st.info("ℹ️ На этой доске пока нет элементов")
    else:
        for element in board_elements:
            element_id = element['id']
            element_type = element['type']
            content = element.get('content', '')[:50] + ('...' if len(element.get('content', '')) > 50 else '')
            x = element.get('x_position', 0) or 0
            y = element.get('y_position', 0) or 0
            width = element.get('width', 0) or 0
            height = element.get('height', 0) or 0
            is_on_board = x > 0 or y > 0 or width > 0 or height > 0
            icon = "📝" if element_type == 'text' else "🖼️"
            status_text = "На доске" if is_on_board else "Не на доске"
            if st.button(
                    f"{icon} {content}",
                    key=f"element_btn_{element_id}",
                    help=f"ID: {element_id} | Статус: {status_text}",
                    use_container_width=True
            ):
                st.session_state.selected_element_id = element_id
                selected_element = None
                for elem in board_elements:
                    if str(elem['id']) == str(element_id):
                        selected_element = elem
                        break
                if selected_element:
                    st.session_state.current_element_data = {
                        'id': selected_element['id'],
                        'type': selected_element['type'],
                        'x': selected_element.get('x_position', 0) or 0,
                        'y': selected_element.get('y_position', 0) or 0,
                        'width': selected_element.get('width', 0) or 0,
                        'height': selected_element.get('height', 0) or 0,
                        'z_index': selected_element.get('z_index', 1) or 1,
                        'content': selected_element.get('content', ''),
                        'content_url': selected_element.get('content_url', '')
                    }
                st.rerun()
    st.markdown("---")
    st.markdown('<div class="panel-section">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">⚙️ Управление элементом</div>', unsafe_allow_html=True)
    if st.session_state.get('selected_element_id'):
        element_data = st.session_state.get('current_element_data', {})
        if element_data:
            st.markdown('<div class="element-info-card">', unsafe_allow_html=True)
            element_type_ru = "📝 Текст" if element_data.get('type') == 'text' else "🖼️ Изображение"
            st.markdown(f"**{element_type_ru}**")
            st.markdown(f"**ID:** `{element_data.get('id')}`")
            x = element_data.get('x', 0)
            y = element_data.get('y', 0)
            width = element_data.get('width', 0)
            height = element_data.get('height', 0)
            if x > 0 or y > 0 or width > 0 or height > 0:
                st.markdown(f"**Статус:** На доске")
                st.markdown(f"**Позиция:** ({x}, {y})")
                st.markdown(f"**Размер:** {width}×{height}")
                st.markdown(f"**Слой:** {element_data.get('z_index', 1)}")
            else:
                st.markdown(f"**Статус:** Не на доске")
            st.markdown('</div>', unsafe_allow_html=True)
            with st.form(key=f"edit_element_form_{element_data.get('id')}"):
                col1, col2 = st.columns(2)
                with col1:
                    board_width = st.session_state.get('board_width', 1200)
                    current_x = element_data.get('x', 0)
                    element_width = element_data.get('width', 0) or 0
                    max_x = board_width - element_width if element_width > 0 else board_width
                    new_x = st.number_input(
                        "Координата X:",
                        min_value=0,
                        max_value=max_x,
                        value=x,
                        step=10,
                        key=f"edit_x_{element_data.get('id')}",
                        help=f"0 = элемент не на доске, максимум {max_x}px"
                    )
                with col2:
                    board_height = st.session_state.get('board_height', 900)
                    current_y = element_data.get('y', 0)
                    element_height = element_data.get('height', 0) or 0
                    max_y = board_height - element_height if element_height > 0 else board_height
                    new_y = st.number_input(
                        "Координата Y:",
                        min_value=0,
                        max_value=max_y,
                        value=y,
                        step=10,
                        key=f"edit_y_{element_data.get('id')}",
                        help=f"0 = элемент не на доске, максимум {max_y}px"
                    )
                col3, col4 = st.columns(2)
                with col3:
                    min_width = 50
                    current_width = element_data.get('width', 0) or 0
                    if current_width > 0 and current_width < min_width:
                        current_width = min_width
                    max_width = board_width - new_x if new_x > 0 else board_width
                    new_width = st.number_input(
                        "Ширина (px):",
                        min_value=0,
                        max_value=max_width,
                        value=current_width,
                        step=10,
                        key=f"edit_width_{element_data.get('id')}",
                        help=f"0 = элемент не на доске, минимум 50px если на доске, максимум {max_width}px"
                    )
                with col4:
                    min_height = 50
                    current_height = element_data.get('height', 0) or 0
                    if current_height > 0 and current_height < min_height:
                        current_height = min_height
                    max_height = board_height - new_y if new_y > 0 else board_height
                    new_height = st.number_input(
                        "Высота (px):",
                        min_value=0,
                        max_value=max_height,
                        value=current_height,
                        step=10,
                        key=f"edit_height_{element_data.get('id')}",
                        help=f"0 = элемент не на доске, минимум 50px если на доске, максимум {max_height}px"
                    )
                board_elements = st.session_state.get('board_elements', [])
                elements_on_board = [e for e in board_elements if (e.get('x_position', 0) or 0) > 0 or
                                     (e.get('y_position', 0) or 0) > 0 or
                                     (e.get('width', 0) or 0) > 0 or
                                     (e.get('height', 0) or 0) > 0]
                max_z = max([(e.get('z_index', 1) or 1) for e in elements_on_board], default=1)
                current_z = element_data.get('z_index', 1)
                new_z = st.number_input(
                    "Слой (z-index):",
                    min_value=1,
                    max_value=100,
                    value=current_z if current_z > 0 else 1,
                    step=1,
                    key=f"edit_zindex_{element_data.get('id')}",
                    help="1 = самый нижний слой"
                )
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    is_valid = True
                    validation_message = ""
                    if new_x > 0 or new_y > 0:
                        if new_width <= 0 or new_height <= 0:
                            is_valid = False
                            validation_message = "Для элементов на доске размеры должны быть > 0"
                        elif new_width < 50 or new_height < 50:
                            is_valid = False
                            validation_message = "Минимальный размер: 50×50px"
                        if new_width > 0 and new_x + new_width > board_width:
                            is_valid = False
                            validation_message = f"Элемент выходит за пределы доски (ширина доски: {board_width}px)"
                        if new_height > 0 and new_y + new_height > board_height:
                            is_valid = False
                            validation_message = f"Элемент выходит за пределы доски (высота доски: {board_height}px)"
                    submit_disabled = not is_valid
                    submit_help = validation_message or "Заполните все поля корректно"
                    if x > 0 or y > 0 or width > 0 or height > 0:
                        submit_label = "✅ Применить изменения"
                    else:
                        submit_label = "📌 Добавить на доску"
                    submit_button = st.form_submit_button(
                        submit_label,
                        use_container_width=True,
                        type="primary",
                        disabled=submit_disabled,
                        help=submit_help if submit_disabled else None
                    )
                with col_btn2:
                    if x == 0 and y == 0 and width == 0 and height == 0:
                        add_with_defaults = st.form_submit_button(
                            "🎯 Добавить со значениями по умолчанию",
                            use_container_width=True,
                            help="Разместить элемент на доске с координатами по умолчанию"
                        )
                    else:
                        add_with_defaults = False
                if submit_button and is_valid:
                    for elem in st.session_state.board_elements:
                        if str(elem['id']) == str(element_data.get('id')):
                            elem['x_position'] = new_x
                            elem['y_position'] = new_y
                            elem['width'] = new_width
                            elem['height'] = new_height
                            elem['z_index'] = new_z
                            break
                    update_element_on_board(
                        element_data.get('id'),
                        x=new_x,
                        y=new_y,
                        width=new_width,
                        height=new_height,
                        zIndex=new_z
                    )
                    save_element_changes(
                        st.session_state.get('edit_board_id'),
                        element_data.get('id')
                    )
                if add_with_defaults:
                    default_x = 100
                    default_y = 100
                    default_width = 200
                    default_height = 150
                    for elem in st.session_state.board_elements:
                        if str(elem['id']) == str(element_data.get('id')):
                            elem['x_position'] = default_x
                            elem['y_position'] = default_y
                            elem['width'] = default_width
                            elem['height'] = default_height
                            break
                    update_element_on_board(
                        element_data.get('id'),
                        x=default_x,
                        y=default_y,
                        width=default_width,
                        height=default_height
                    )
                    save_element_changes(
                        st.session_state.get('edit_board_id'),
                        element_data.get('id')
                    )
            if st.button("⚠️ Удалить элемент",
                         key=f"delete_{element_data.get('id')}",
                         use_container_width=True):
                delete_element(
                    st.session_state.get('edit_board_id'),
                    element_data.get('id')
                )
            if st.button("🧹 Снять выделение",
                         key=f"deselect_{element_data.get('id')}",
                         use_container_width=True):
                st.session_state.selected_element_id = None
                if 'current_element_data' in st.session_state:
                    del st.session_state.current_element_data
                st.rerun()
        else:
            st.info("ℹ️ Данные элемента не загружены")
    else:
        st.info("👈 Выберите элемент из списка выше для управления")
        with st.form(key="empty_element_form"):
            col1, col2 = st.columns(2)
            with col1:
                st.number_input(
                    "Координата X:",
                    min_value=0,
                    max_value=2000,
                    value=0,
                    step=10,
                    key="empty_x",
                    disabled=True
                )
            with col2:
                st.number_input(
                    "Координата Y:",
                    min_value=0,
                    max_value=2000,
                    value=0,
                    step=10,
                    key="empty_y",
                    disabled=True
                )
            col3, col4 = st.columns(2)
            with col3:
                st.number_input(
                    "Ширина (px):",
                    min_value=0,
                    max_value=1000,
                    value=0,
                    step=10,
                    key="empty_width",
                    disabled=True
                )
            with col4:
                st.number_input(
                    "Высота (px):",
                    min_value=0,
                    max_value=1000,
                    value=0,
                    step=10,
                    key="empty_height",
                    disabled=True
                )
            st.number_input(
                "Слой (z-index):",
                min_value=1,
                max_value=100,
                value=1,
                step=1,
                key="empty_zindex",
                disabled=True
            )
            st.form_submit_button(
                "✅ Применить изменения",
                use_container_width=True,
                disabled=True
            )
    st.markdown('</div>', unsafe_allow_html=True)


def update_element_on_board(element_id, x=None, y=None, width=None, height=None, zIndex=None):
    for element in st.session_state.get('board_elements', []):
        if str(element['id']) == str(element_id):
            if x is not None:
                element['x_position'] = x
            if y is not None:
                element['y_position'] = y
            if width is not None:
                element['width'] = width
            if height is not None:
                element['height'] = height
            if zIndex is not None:
                element['z_index'] = zIndex
            break
    if st.session_state.get('selected_element_id') == str(element_id):
        if 'current_element_data' in st.session_state:
            if x is not None:
                st.session_state.current_element_data['x'] = x
            if y is not None:
                st.session_state.current_element_data['y'] = y
            if width is not None:
                st.session_state.current_element_data['width'] = width
            if height is not None:
                st.session_state.current_element_data['height'] = height
            if zIndex is not None:
                st.session_state.current_element_data['z_index'] = zIndex
    js_code = f"""
    <script>
        window.parent.postMessage({{
            type: 'updateElement',
            elementId: '{element_id}',
            x: {x if x is not None else 'null'},
            y: {y if y is not None else 'null'},
            width: {width if width is not None else 'null'},
            height: {height if height is not None else 'null'},
            zIndex: {zIndex if zIndex is not None else 'null'}
        }}, '*');
    </script>
    """
    st.markdown(js_code, unsafe_allow_html=True)


def save_element_changes(board_id, element_id):
    telegram_id = st.session_state.get("telegram_id")
    if not telegram_id:
        st.error("❌ Ошибка: не найден Telegram ID")
        return
    element = None
    for elem in st.session_state.get('board_elements', []):
        if str(elem['id']) == str(element_id):
            element = elem
            break
    if not element:
        st.error("❌ Элемент не найден")
        return
    x_pos = element.get('x_position', 0) or 0
    y_pos = element.get('y_position', 0) or 0
    width_val = element.get('width', 0) or 0
    height_val = element.get('height', 0) or 0
    if x_pos > 0 or y_pos > 0:
        if width_val <= 0:
            width_val = 50
        elif width_val < 50:
            width_val = 50
        if height_val <= 0:
            height_val = 50
        elif height_val < 50:
            height_val = 50
        for elem in st.session_state.board_elements:
            if str(elem['id']) == str(element_id):
                elem['width'] = width_val
                elem['height'] = height_val
                break
    update_data = {
        "x_position": x_pos,
        "y_position": y_pos,
        "z_index": element.get('z_index', 1) or 1,
        "width": width_val,
        "height": height_val
    }
    if element['type'] == 'text' and 'content' in element:
        update_data['content'] = element['content']
    params = {"telegram_id": telegram_id}
    result, error = call_api(
        f"/api/boards/{board_id}/content/{element_id}/position",
        method="PUT",
        data=update_data,
        params=params,
        token=st.session_state.get('access_token')
    )
    if error:
        st.error(f"❌ Ошибка при сохранении: {error}")
    else:
        st.success("✅ Изменения сохранены на сервере!")
        time.sleep(1.5)
        st.rerun()


def delete_element(board_id, element_id):
    telegram_id = st.session_state.get("telegram_id")
    if not telegram_id:
        st.error("❌ Ошибка: не найден Telegram ID")
        return
    params = {"telegram_id": telegram_id}
    result, error = call_api(
        f"/api/boards/{board_id}/content/{element_id}",
        method="DELETE",
        params=params,
        token=st.session_state.get('access_token')
    )
    if error:
        st.error(f"❌ Ошибка: {error}")
    else:
        st.success("✅ Элемент удален!")
        st.session_state.board_elements = [
            elem for elem in st.session_state.get('board_elements', [])
            if str(elem['id']) != str(element_id)
        ]
        st.session_state.selected_element_id = None
        if 'current_element_data' in st.session_state:
            del st.session_state.current_element_data
        time.sleep(1)
        st.rerun()


def save_all_changes(board_id):
    telegram_id = st.session_state.get("telegram_id")
    if not telegram_id:
        st.error("❌ Ошибка: не найден Telegram ID")
        return
    elements = st.session_state.get('board_elements', [])
    if not elements:
        st.info("ℹ️ Нет элементов для сохранения")
        return
    success_count = 0
    error_count = 0
    with st.spinner(f"💾 Сохраняем {len(elements)} элементов..."):
        for element in elements:
            x_pos = element.get('x_position', 0) or 0
            y_pos = element.get('y_position', 0) or 0
            width_val = element.get('width', 0) or 0
            height_val = element.get('height', 0) or 0
            if (x_pos > 0 or y_pos > 0 or width_val > 0 or height_val > 0):
                if width_val > 0 and width_val < 10:
                    width_val = 10
                if height_val > 0 and height_val < 10:
                    height_val = 10
            update_data = {
                "x_position": x_pos,
                "y_position": y_pos,
                "z_index": element.get('z_index', 1) or 1,
                "width": width_val,
                "height": height_val
            }
            if element['type'] == 'text' and 'content' in element:
                update_data['content'] = element['content']
            params = {"telegram_id": telegram_id}
            result, error = call_api(
                f"/api/boards/{board_id}/content/{element['id']}/position",
                method="PUT",
                data=update_data,
                params=params,
                token=st.session_state.get('access_token')
            )
            if error:
                error_count += 1
                st.error(f"❌ Элемент {element['id']}: {error}")
                st.info(f"Данные: {update_data}")
            else:
                success_count += 1
    if success_count > 0:
        st.success(f"✅ Успешно сохранено {success_count} элементов")
    if error_count > 0:
        st.error(f"⚠️ Ошибка при сохранении {error_count} элементов")


def edit_board_page():
    board_id = st.session_state.get("edit_board_id")
    if not board_id:
        st.error("❌ ID доски не указан")
        if st.button("← Назад"):
            st.session_state.page = "dashboard"
            st.rerun()
        return
    if "access_token" not in st.session_state:
        st.error("❌ Требуется вход в систему")
        st.session_state.page = "login"
        st.rerun()
        return
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("✏️ Редактор доски")
    with col2:
        sidebar_collapsed = st.session_state.get('sidebar_collapsed', False)
        button_label = "📊 Показать панель" if sidebar_collapsed else "❌ Скрыть панель"
        if st.button(button_label, key="toggle_sidebar_main", type="secondary"):
            st.session_state.sidebar_collapsed = not sidebar_collapsed
            st.rerun()
    if 'board_data' not in st.session_state or st.session_state.get('current_board_id') != board_id:
        with st.spinner("🔄 Загружаем доску..."):
            board_data, board_error = call_api(
                f"/api/boards/{board_id}",
                token=st.session_state.access_token
            )
            if board_error:
                st.error(f"❌ Ошибка при загрузке доски: {board_error}")
                return
            board_settings = load_board_settings(board_id)
            if board_settings:
                st.session_state.board_width = board_settings.get('board_width', 1200)
                st.session_state.board_height = board_settings.get('board_height', 900)
                st.session_state.board_background_color = board_settings.get('background_color', '#FFFBF0')
                st.session_state.board_border_color = board_settings.get('border_color', '#5D4037')
                st.session_state.board_aspect_ratio = "Свободное"
            else:
                st.session_state.board_width = 1200
                st.session_state.board_height = 900
                st.session_state.board_background_color = '#FFFBF0'
                st.session_state.board_border_color = '#5D4037'
                st.session_state.board_aspect_ratio = '4:3'
            content_data, content_error = call_api(
                f"/api/boards/{board_id}/content",
                token=st.session_state.access_token
            )
            if content_error:
                st.warning(f"⚠️ Не удалось загрузить контент: {content_error}")
                content_data = []
            st.session_state.board_data = board_data
            st.session_state.board_elements = content_data if content_data else []
            st.session_state.current_board_id = board_id
            st.session_state.selected_element_id = None
    board_data = st.session_state.board_data
    emoji = "🌐" if board_data.get('is_public', False) else "🔒"
    st.markdown(f"### {emoji} {board_data.get('name', 'Без названия')}")
    if board_data.get('description'):
        st.markdown(f"*{board_data.get('description')}*")
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.markdown(f"**🔑 Код:** `{board_data.get('board_code', 'Неизвестно')}`")
    with col_info2:
        st.markdown(f"**👤 Владелец:** {board_data.get('owner_username', 'Неизвестно')}")
    with col_info3:
        elements_on_board = len([e for e in st.session_state.get('board_elements', [])
                                 if (e.get('x_position', 0) or 0) > 0 or
                                 (e.get('y_position', 0) or 0) > 0])
        total_elements = len(st.session_state.get('board_elements', []))
        st.markdown(f"**📊 Элементов:** {elements_on_board}/{total_elements}")
    st.markdown("---")
    sidebar_collapsed = st.session_state.get('sidebar_collapsed', False)
    if not sidebar_collapsed:
        with st.sidebar:
            render_control_panel()
    st.markdown("### 🎨 Доска")
    board_component = create_board_component(
        st.session_state.get('board_elements', []),
        board_id
    )
    if hasattr(st.session_state, '_component_messages'):
        for msg in st.session_state._component_messages:
            print(f"Processing message: {msg}")
            if msg['type'] == 'boardClicked':
                print(f"Board clicked at: {msg['x']}, {msg['y']}")
                st.toast(f"📌 Координаты клика: ({msg['x']}, {msg['y']})")
            elif msg['type'] == 'toggleControlPanel':
                st.session_state.sidebar_collapsed = msg.get('state', True)
                st.rerun()
        st.session_state._component_messages = []
    st.markdown("---")
    if st.button("← Назад к списку", use_container_width=True, type="primary"):
        clear_editor_state()
        st.session_state.page = "dashboard"
        st.rerun()


def login_page():
    init_session_state()
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1 style="color: #667eea; margin-bottom: 0.5rem;">🎨 MoodBoard</h1>
        <p style="color: #6c757d;">Ваше пространство для творчества и вдохновения</p>
    </div>
    """, unsafe_allow_html=True)
    if "access_token" in st.session_state and st.session_state.access_token:
        username = st.session_state.get('username', 'пользователь')
        if not username or username == 'None':
            username = 'пользователь'
        st.success(f"✅ Вы уже авторизованы как {username}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📋 Личный кабинет", use_container_width=True):
                st.session_state.page = "dashboard"
                st.rerun()
        with col2:
            if st.button("🚪 Выйти", use_container_width=True):
                st.session_state.clear()
                init_session_state()
                st.rerun()
        st.markdown("---")
    with st.form("login_form"):
        st.markdown("### 🔐 Вход в систему")
        login = st.text_input("Логин:", placeholder="Введите ваш логин")
        password = st.text_input("Пароль:", type="password", placeholder="Введите ваш пароль")
        if st.form_submit_button("🚀 Войти", use_container_width=True):
            if not login.strip() or not password.strip():
                st.error("❌ Пожалуйста, заполните все поля")
            else:
                auth_data = {"login": login.strip(), "password": password.strip()}
                with st.spinner("🔐 Проверяем данные..."):
                    result, error = call_api("/api/auth/login", method="POST", data=auth_data)
                if error:
                    st.error(f"❌ Ошибка входа: {error}")
                elif result and result.get('success'):
                    st.session_state.access_token = result.get('access_token')
                    st.session_state.user_id = result.get('user_id')
                    st.session_state.username = result.get('username', login)
                    st.session_state.telegram_id = result.get('telegram_id')
                    st.session_state.page = "dashboard"
                    st.success(f"✅ Добро пожаловать, {st.session_state.username}!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Неверный логин или пароль")
    st.markdown("---")
    st.markdown("### 📱 Нет аккаунта?")
    st.markdown(f"""
    Зарегистрируйтесь через нашего Telegram бота:
    1. Перейдите в [Telegram бота]({TG_BOT_URL})
    2. Отправьте команду **/start**
    3. Следуйте инструкциям бота
    4. Получите логин и пароль
    5. Вернитесь на эту страницу
    """)
    st.markdown("---")
    st.markdown("### 👁 Просмотр доски по коду")
    board_code = st.text_input("Код доски:", placeholder="XXX-XXX-XXX", max_chars=11).upper()
    if st.button("🔍 Найти доску", use_container_width=True):
        if board_code and len(board_code) == 11:
            st.session_state.board_code = board_code
            st.session_state.page = "board_access"
            st.rerun()
        else:
            st.error("❌ Введите корректный код доски")


def main_page():
    st.session_state.page = "login"
    st.rerun()


def board_access_page():
    board_code = st.session_state.get("board_code", "")
    if not board_code:
        st.error("❌ Код доски не указан")
        if st.button("← Назад"):
            st.session_state.page = "login"
            st.rerun()
        return
    st.title("🔑 Доступ к доске")
    st.info(f"Код доски: `{board_code}`")
    with st.spinner("🔍 Ищем доску..."):
        result, error = call_api(f"/api/boards/code/{board_code}/view")
        if error:
            if "Доска приватная" in error:
                if "access_token" in st.session_state:
                    telegram_id = st.session_state.get("telegram_id")
                    if telegram_id:
                        access_result, access_error = call_api(
                            f"/api/boards/code/{board_code}",
                            params={"with_content": False},
                            token=st.session_state.get('access_token')
                        )
                        if access_result:
                            board_info = access_result
                            content_data, content_error = call_api(
                                f"/api/boards/{board_info['id']}/content",
                                token=st.session_state.get('access_token')
                            )
                            if not content_error:
                                st.session_state.view_board_data = board_info
                                st.session_state.view_board_content = content_data if content_data else []
                                st.session_state.page = "view_board_by_code"
                                st.rerun()
                                return
                st.error(f"❌ {error}")
            else:
                st.error(f"❌ Ошибка: {error}")
            if st.button("← Назад"):
                st.session_state.page = "login"
                st.rerun()
            return
        if not result or 'board' not in result:
            st.error("❌ Доска не найдена или произошла ошибка")
            if st.button("← Назад"):
                st.session_state.page = "login"
                st.rerun()
            return
    board_info = result['board']
    content = result.get('content', [])
    st.success(f"✅ Доска найдена: **{board_info.get('name')}**")
    emoji = "🌐" if board_info.get('is_public') else "🔒"
    st.markdown(f"### {emoji} {board_info.get('name', 'Без названия')}")
    if board_info.get('description'):
        st.markdown(f"*{board_info.get('description')}*")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**👤 Владелец:** {board_info.get('owner_username', 'Неизвестно')}")
    with col2:
        st.markdown(f"**📅 Создана:** {board_info.get('created_at', '')[:10]}")
    with col3:
        st.markdown(f"**📊 Элементов:** {len(content)}")
    st.markdown("---")
    if st.button("👁 Просмотреть доску", use_container_width=True, type="primary"):
        st.session_state.view_board_data = board_info
        st.session_state.view_board_content = content
        st.session_state.page = "view_board_by_code"
        st.rerun()
    st.markdown("---")
    if st.button("← На главную", use_container_width=True):
        st.session_state.page = "login"
        st.rerun()


def create_board_auth_page():
    st.title("➕ Создание доски")
    st.warning("Эта функция в разработке")
    if st.button("← На главную"):
        st.session_state.page = "login"
        st.rerun()


def create_board_form_page():
    st.title("🎨 Создание доски")
    with st.form("create_board_form"):
        board_name = st.text_input("Название доски:", placeholder="Моя новая доска")
        board_description = st.text_area("Описание:", placeholder="Опишите вашу доску...", height=100)
        is_public = st.checkbox("Сделать публичной")
        if st.form_submit_button("🎨 Создать доску", use_container_width=True):
            if not board_name.strip():
                st.error("❌ Введите название доски")
            else:
                telegram_id = st.session_state.get("telegram_id")
                if not telegram_id:
                    st.error("❌ Ошибка: не найден Telegram ID")
                else:
                    board_data = {
                        "name": board_name.strip(),
                        "description": board_description.strip(),
                        "is_public": is_public
                    }
                    params = {"telegram_id": telegram_id}
                    result, error = call_api(
                        "/api/boards",
                        method="POST",
                        data=board_data,
                        params=params,
                        token=st.session_state.get('access_token')
                    )
                    if error:
                        st.error(f"❌ Ошибка: {error}")
                    else:
                        st.success("✅ Доска создана!")
                        st.session_state.page = "dashboard"
                        st.rerun()
    if st.button("← Назад"):
        st.session_state.page = "dashboard"
        st.rerun()


def dashboard_page():
    if "access_token" not in st.session_state:
        st.error("❌ Требуется вход в систему")
        st.session_state.page = "login"
        st.rerun()
        return
    st.title("📋 Личный кабинет")
    col_user, col_logout = st.columns([3, 1])
    with col_user:
        st.markdown(f"### 👤 {st.session_state.get('username', 'Гость')}")
        if st.session_state.get('telegram_id'):
            st.markdown(f"**Telegram ID:** `{st.session_state.telegram_id}`")
    with col_logout:
        if st.button("🚪 Выйти", use_container_width=True):
            for key in ["access_token", "user_id", "username", "telegram_id"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.page = "login"
            st.rerun()
    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["📋 Мои доски", "➕ Создать доску", "🔑 Ввести код"])
    with tab1:
        st.subheader("Мои доски")
        telegram_id = st.session_state.get("telegram_id")
        if telegram_id:
            data, error = call_api(f"/api/users/{telegram_id}/boards")
            if error:
                st.error(f"❌ Ошибка: {error}")
            elif not data:
                st.info("ℹ️ У вас пока нет досок")
            else:
                for board in data:
                    with st.container():
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            emoji = "🌐" if board.get('is_public') else "🔒"
                            st.markdown(f"#### {emoji} {board.get('name', 'Без названия')}")
                            if board.get('description'):
                                st.markdown(f"*{board.get('description')[:100]}...*")
                        with col2:
                            if st.button("✏️ Редактировать", key=f"edit_{board['id']}"):
                                st.session_state.edit_board_id = board['id']
                                st.session_state.page = "edit_board"
                                st.rerun()
                        st.markdown("---")
    with tab2:
        st.subheader("Создать новую доску")
        if st.button("🎨 Создать доску", use_container_width=True, type="primary"):
            st.session_state.page = "create_board_form"
            st.rerun()
    with tab3:
        st.subheader("Ввести код доски")
        board_code = st.text_input("Код доски:", placeholder="XXX-XXX-XXX",
                                   max_chars=11, key="dashboard_board_code").upper()
        if st.button("🔓 Открыть доску", use_container_width=True):
            if board_code and len(board_code) == 11:
                st.session_state.board_code = board_code
                st.session_state.page = "board_access"
                st.rerun()
            else:
                st.error("❌ Введите корректный код доски")


def view_board_page():
    token = st.session_state.get("view_token")
    if not token:
        st.error("❌ Токен доски не указан")
        if st.button("← На главную"):
            st.session_state.page = "login"
            st.rerun()
        return
    st.title("👁 Просмотр доски")
    with st.spinner("🔄 Загружаем доску..."):
        board_data, board_error = call_api(f"/api/boards/token/{token}")
        if board_error:
            st.error(f"❌ Ошибка: {board_error}")
            if st.button("← На главную"):
                st.session_state.page = "login"
                st.rerun()
            return
        content_data, content_error = call_api(f"/api/boards/{board_data['id']}/content")
        if content_error:
            st.warning(f"⚠️ Не удалось загрузить контент: {content_error}")
            content_data = []
        board_id = board_data['id']
        board_settings = None
        try:
            settings_result, settings_error = call_api(f"/api/boards/{board_id}/settings")
            if settings_result and not settings_error:
                board_settings = settings_result
                st.session_state.board_width = board_settings.get('board_width', 1200)
                st.session_state.board_height = board_settings.get('board_height', 900)
                st.session_state.board_background_color = board_settings.get('background_color', '#FFFBF0')
                st.session_state.board_border_color = board_settings.get('border_color', '#5D4037')
            else:
                st.session_state.board_width = 1200
                st.session_state.board_height = 900
                st.session_state.board_background_color = '#FFFBF0'
                st.session_state.board_border_color = '#5D4037'
        except Exception as e:
            st.session_state.board_width = 1200
            st.session_state.board_height = 900
            st.session_state.board_background_color = '#FFFBF0'
            st.session_state.board_border_color = '#5D4037'
    emoji = "🌐" if board_data.get('is_public') else "🔒"
    st.markdown(f"## {emoji} {board_data.get('name', 'Без названия')}")
    if board_data.get('description'):
        st.markdown(f"*{board_data.get('description')}*")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**👤 Владелец:** {board_data.get('owner_username', 'Неизвестно')}")
    with col2:
        st.markdown(f"**📅 Создана:** {board_data.get('created_at', '')[:10]}")
    with col3:
        st.markdown(f"**📊 Элементов:** {len(content_data)}")
    if board_settings:
        col4, col5 = st.columns(2)
        with col4:
            bg_color = board_settings.get('background_color', '#FFFBF0')
            border_color = board_settings.get('border_color', '#5D4037')
            st.markdown(f"**🎨 Цвета:** фон: `{bg_color}`, рамка: `{border_color}`")
        with col5:
            width = board_settings.get('board_width', 1200)
            height = board_settings.get('board_height', 900)
            st.markdown(f"**📐 Размер:** {width}×{height}px")
    st.markdown("---")
    if content_data:
        elements_on_board = []
        for element in content_data:
            x = element.get('x_position', 0) or 0
            y = element.get('y_position', 0) or 0
            width = element.get('width', 0) or 0
            height = element.get('height', 0) or 0
            if x > 0 or y > 0 or width > 0 or height > 0:
                elements_on_board.append(element)
        if elements_on_board:
            board_component = create_board_component(
                elements_on_board,
                board_data['id'],
                view_only=True
            )
        else:
            st.info("📭 На этой доске пока нет элементов")
    else:
        st.info("📭 На этой доске пока нет элементов")
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Назад", use_container_width=True):
            if "access_token" in st.session_state:
                st.session_state.page = "dashboard"
            else:
                st.session_state.page = "login"
            st.rerun()
    with col2:
        if st.button("🔗 Копировать ссылку", use_container_width=True):
            try:
                import pyperclip
                pyperclip.copy(f"{WEBSITE_URL}/?view={token}")
                st.success("✅ Ссылка скопирована!")
            except:
                st.warning("⚠️ Не удалось скопировать ссылку")


def view_board_by_code_page():
    if 'view_board_data' not in st.session_state or 'view_board_content' not in st.session_state:
        st.error("❌ Данные доски не загружены")
        if st.button("← Назад"):
            st.session_state.page = "login"
            st.rerun()
        return
    board_data = st.session_state.view_board_data
    content_data = st.session_state.view_board_content
    st.title("👁 Просмотр доски")
    board_id = board_data.get('id')
    board_settings = None
    if board_id:
        try:
            logger.info(f"Загрузка настроек доски {board_id} для просмотра по коду")
            settings_result, settings_error = call_api(
                f"/api/boards/{board_id}/public-settings"
            )
            if settings_result and not settings_error:
                board_settings = settings_result
                logger.info(f"Настройки получены через public-settings: {board_settings}")
            else:
                logger.warning(f"Не удалось получить настройки через public-settings: {settings_error}")
                if 'board_settings' in board_data:
                    board_settings = board_data['board_settings']
                    logger.info(f"Настройки получены из board_data: {board_settings}")
                else:
                    board_info, board_error = call_api(
                        f"/api/boards/code/{board_data.get('board_code')}"
                    )
                    if board_info and not board_error and 'board_settings' in board_info:
                        board_settings = board_info['board_settings']
                        logger.info(f"Настройки получены из get_board_by_code: {board_settings}")
            if board_settings:
                st.session_state.board_width = board_settings.get('board_width', 1200)
                st.session_state.board_height = board_settings.get('board_height', 900)
                st.session_state.board_background_color = board_settings.get('background_color', '#FFFBF0')
                st.session_state.board_border_color = board_settings.get('border_color', '#5D4037')
                logger.info(f"Настройки сохранены в session state: "
                            f"width={st.session_state.board_width}, "
                            f"height={st.session_state.board_height}, "
                            f"bg={st.session_state.board_background_color}, "
                            f"border={st.session_state.board_border_color}")
            else:
                logger.warning(f"Не удалось получить настройки доски {board_id}, используем значения по умолчанию")
                st.session_state.board_width = 1200
                st.session_state.board_height = 900
                st.session_state.board_background_color = '#FFFBF0'
                st.session_state.board_border_color = '#5D4037'
        except Exception as e:
            logger.error(f"Ошибка при загрузке настроек доски: {e}")
            st.session_state.board_width = 1200
            st.session_state.board_height = 900
            st.session_state.board_background_color = '#FFFBF0'
            st.session_state.board_border_color = '#5D4037'
    emoji = "🌐" if board_data.get('is_public') else "🔒"
    st.markdown(f"## {emoji} {board_data.get('name', 'Без названия')}")
    if board_data.get('description'):
        st.markdown(f"*{board_data.get('description')}*")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**👤 Владелец:** {board_data.get('owner_username', 'Неизвестно')}")
    with col2:
        st.markdown(f"**📅 Создана:** {board_data.get('created_at', '')[:10]}")
    with col3:
        st.markdown(f"**📊 Элементов:** {len(content_data)}")
    if board_settings:
        col4, col5 = st.columns(2)
        with col4:
            bg_color = board_settings.get('background_color', '#FFFBF0')
            border_color = board_settings.get('border_color', '#5D4037')
            st.markdown(f"**🎨 Цвета:** фон: `{bg_color}`, рамка: `{border_color}`")
        with col5:
            width = board_settings.get('board_width', 1200)
            height = board_settings.get('board_height', 900)
            st.markdown(f"**📐 Размер:** {width}×{height}px")
    else:
        col4, col5 = st.columns(2)
        with col4:
            st.markdown(
                f"**🎨 Цвета:** фон: `{st.session_state.board_background_color}`, рамка: `{st.session_state.board_border_color}`")
        with col5:
            st.markdown(f"**📐 Размер:** {st.session_state.board_width}×{st.session_state.board_height}px")
    st.markdown("---")
    if content_data:
        elements_on_board = []
        for element in content_data:
            x = element.get('x_position', 0) or 0
            y = element.get('y_position', 0) or 0
            width = element.get('width', 0) or 0
            height = element.get('height', 0) or 0
            if x > 0 or y > 0 or width > 0 or height > 0:
                elements_on_board.append(element)
        if elements_on_board:
            board_component = create_board_component(
                elements_on_board,
                board_id
            )
        else:
            st.info("📭 На этой доске пока нет элементов")
    else:
        st.info("📭 На этой доске пока нет элементов")
    st.markdown("---")
    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        if st.button("← Назад", use_container_width=True):
            if "access_token" in st.session_state and st.session_state.access_token:
                st.session_state.page = "dashboard"
            else:
                st.session_state.page = "login"
            st.rerun()


def clear_editor_state():
    keys_to_clear = ['board_data', 'board_elements', 'current_board_id',
                     'selected_element_id', 'current_element_data',
                     'sidebar_collapsed', 'edit_board_id']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]


def init_session_state():
    defaults = {
        "page": "login",
        "board_elements": [],
        "selected_element_id": None,
        "current_element_data": None,
        "current_board_id": None,
        "_component_messages": [],
        "access_token": "",
        "user_id": "",
        "username": "",
        "telegram_id": "",
        "edit_board_id": None,
        "board_code": None,
        "view_token": None,
        "view_board_data": None,
        "view_board_content": None,
        "board_data": None,
        "board_width": 1200,
        "board_height": 900,
        "board_aspect_ratio": "4:3",
        "board_background_color": "#FFFBF0",
        "board_border_color": "#5D4037",
        "sidebar_collapsed": False
    }
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


def main():
    init_session_state()
    pages = {
        "login": login_page,
        "main": main_page,
        "board_access": board_access_page,
        "create_board_auth": create_board_auth_page,
        "create_board_form": create_board_form_page,
        "dashboard": dashboard_page,
        "view_board": view_board_page,
        "view_board_by_code": view_board_by_code_page,
        "edit_board": edit_board_page,
    }
    current_page = st.session_state.get("page", "login")
    if current_page in pages:
        pages[current_page]()
    else:
        st.session_state.page = "login"
        st.rerun()


if __name__ == "__main__":
    main()