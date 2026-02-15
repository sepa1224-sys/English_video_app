import streamlit as st
import models
import time
import random

# Initialize Database
models.init_db()

# Page Configuration
st.set_page_config(
    page_title="THE 受験 - Student Dashboard",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for "THE JUKEN" Theme (Deep Blue & White)
st.markdown("""
    <style>
    .stApp {
        background-color: #f0f2f6;
    }
    .main-header {
        font-size: 2.5rem;
        color: #0e1117;
        font-weight: 700;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #003366; /* Deep Blue */
        font-weight: 600;
        margin-top: 2rem;
        border-bottom: 2px solid #003366;
        padding-bottom: 0.5rem;
    }
    .stat-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
    }
    .stat-value {
        font-size: 2rem;
        font-weight: bold;
        color: #003366;
    }
    .stat-label {
        font-size: 1rem;
        color: #666;
    }
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #003366;
    }
    section[data-testid="stSidebar"] .stRadio label {
        color: white !important;
        font-size: 1.1rem;
    }
    section[data-testid="stSidebar"] h1, h2, h3 {
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

# Sidebar Navigation
with st.sidebar:
    st.markdown("<h1 style='color: white; text-align: center;'>THE 受験 🎓</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    menu = st.radio(
        "MENU",
        ["🏠 ホーム", "📝 入試演習", "🔤 単語テスト", "🔥 ランキング", "⏳ 自習室"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    # User Profile Mini View
    user_profile = models.get_user_profile()
    if user_profile:
        st.markdown(f"<div style='color: white; text-align: center;'>受験生: <b>{user_profile['username']}</b></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='color: #aaccee; text-align: center; font-size: 0.8rem;'>志望校: {user_profile['target_school']}</div>", unsafe_allow_html=True)

# Main Content Area
if menu == "🏠 ホーム":
    st.markdown("<div class='main-header'>Dashboard</div>", unsafe_allow_html=True)
    
    # User Stats
    if user_profile:
        col1, col2, col3 = st.columns(3)
        
        # Study Time Calculation
        total_mins = user_profile['total_study_time_minutes']
        hours = total_mins // 60
        mins = total_mins % 60
        
        # Accuracy
        avg_acc = models.get_avg_accuracy()
        
        with col1:
            st.markdown(f"""
            <div class='stat-card'>
                <div class='stat-value'>{user_profile['target_school']}</div>
                <div class='stat-label'>目標志望校</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown(f"""
            <div class='stat-card'>
                <div class='stat-value'>{hours}h {mins}m</div>
                <div class='stat-label'>累計勉強時間</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col3:
            st.markdown(f"""
            <div class='stat-card'>
                <div class='stat-value'>{avg_acc}%</div>
                <div class='stat-label'>単語テスト平均正解率</div>
            </div>
            """, unsafe_allow_html=True)

    # Daily Motivation / Tips
    st.markdown("<div class='sub-header'>本日の学習目標</div>", unsafe_allow_html=True)
    st.info("💡 **今日の格言**: 努力は裏切らない。まずは単語テストから始めよう！")
    
    # Quick Actions
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### 🚀 ラストスパート")
        if st.button("単語テストを開始する (ランダム10問)", use_container_width=True):
            st.warning("「単語テスト」メニューから開始してください。")
            
    with col_b:
        st.markdown("#### 📅 学習スケジュール")
        st.progress(0.65, text="今週の目標達成度: 65%")

elif menu == "� 入試演習":
    st.markdown("<div class='main-header'>入試問題演習</div>", unsafe_allow_html=True)
    st.markdown("""
    志望校の過去問や、生成された予想問題に挑戦できます。
    """)
    
    tab1, tab2 = st.tabs(["長文読解", "文法・語法"])
    
    with tab1:
        st.markdown("### 📄 長文読解問題")
        st.write("現在、利用可能な問題はありません。管理者が問題を追加するのをお待ちください。")
        
    with tab2:
        st.markdown("### 🧩 文法・語法問題")
        st.write("準備中...")

elif menu == "🔤 単語テスト":
    st.markdown("<div class='main-header'>単語特訓</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("### テスト設定")
        test_type = st.selectbox("出題範囲", ["ターゲット1900", "鉄壁", "過去問頻出"])
        num_questions = st.slider("問題数", 10, 50, 10)
        
        if st.button("テスト開始", type="primary"):
            st.success(f"{test_type} から {num_questions} 問のテストを開始します... (デモ)")
            # In a real app, this would initialize session_state for the test
            time.sleep(1)
            st.balloons()
            
    with col2:
        st.markdown("### 成績履歴")
        st.write("直近の成績:")
        st.dataframe({
            "日付": ["2023-10-01", "2023-10-02"],
            "点数": [8, 9],
            "正解率": ["80%", "90%"]
        })

elif menu == "🔥 ランキング":
    st.markdown("<div class='main-header'>全国受験生ランキング</div>", unsafe_allow_html=True)
    st.markdown("同じ志望校を目指すライバルと競い合おう！")
    
    # Dummy Data for Ranking
    st.table([
        {"順位": "1位", "ニックネーム": "StudyMaster", "勉強時間": "120時間", "志望校": "東京大学"},
        {"順位": "2位", "ニックネーム": "Goukaku2024", "勉強時間": "115時間", "志望校": "京都大学"},
        {"順位": "3位", "ニックネーム": "EigoKing", "勉強時間": "100時間", "志望校": "早稲田大学"},
        {"順位": "YOU", "ニックネーム": user_profile['username'], "勉強時間": f"{hours}時間", "志望校": user_profile['target_school']},
    ])

elif menu == "⏳ 自習室":
    st.markdown("<div class='main-header'>集中自習室</div>", unsafe_allow_html=True)
    st.markdown("ポモドーロタイマーを使って集中力を高めよう。")
    
    col1, col2, col3 = st.columns(3)
    with col2:
        st.markdown("### ⏱️ タイマー")
        timer_min = st.number_input("分", min_value=1, value=25)
        if st.button("集中スタート"):
            with st.empty():
                for seconds in range(timer_min * 60, 0, -1):
                    mins, secs = divmod(seconds, 60)
                    st.metric("残り時間", f"{mins:02d}:{secs:02d}")
                    time.sleep(1)
                st.success("お疲れ様でした！休憩しましょう。")
                models.add_study_time(timer_min)
                st.experimental_rerun()
