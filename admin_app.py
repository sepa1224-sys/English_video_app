import streamlit as st
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

import main
import importlib
importlib.reload(main)
import video_gen
import script_gen
import uploader
import history_manager
import glob
import re
import datetime

st.set_page_config(page_title="AI Content Generator", page_icon="🎙️")

# Sidebar Global Settings
st.sidebar.header("Global Settings")
exec_mode = st.sidebar.radio(
    "Execution Mode",
    (
        "Production (ElevenLabs + OpenAI)", 
        "Standard (OpenAI Only)", 
        "Test Mode (Free / Edge-TTS)", 
        "Layout Check (No Audio)"
    )
)

# Set Environment Variables based on selection
if exec_mode == "Layout Check (No Audio)":
    os.environ["LAYOUT_CHECK_MODE"] = "true"
    os.environ["TEST_MODE"] = "false"
    os.environ["USE_ELEVENLABS"] = "false"
elif exec_mode == "Test Mode (Free / Edge-TTS)":
    os.environ["LAYOUT_CHECK_MODE"] = "false"
    os.environ["TEST_MODE"] = "true"
    os.environ["USE_ELEVENLABS"] = "false"
elif exec_mode == "Standard (OpenAI Only)":
    os.environ["LAYOUT_CHECK_MODE"] = "false"
    os.environ["TEST_MODE"] = "false"
    os.environ["USE_ELEVENLABS"] = "false"
else: # Production
    os.environ["LAYOUT_CHECK_MODE"] = "false"
    os.environ["TEST_MODE"] = "false"
    os.environ["USE_ELEVENLABS"] = "true"

st.sidebar.markdown("---")

# Sidebar Mode Selection
mode = st.sidebar.selectbox(
    "Select Function", 
    ["Podcast Generator", "Before Sleep Podcast Mode", "Vocalab Mode (Target 1900)", "Word Audio Mode (Target Series)", "Exam Problem Creator", "University Entrance Exam Listening", "YouTube Posting Management"]
)

if mode == "YouTube Posting Management":
    st.title("📺 YouTube Posting Management")
    st.markdown("""
    **Manage and Upload Videos to YouTube.**
    Reserve posts, set metadata, and upload directly.
    """)

    # Initialize session state for reservations
    if "reservations" not in st.session_state:
        st.session_state.reservations = []

    # Add Reservation Button
    if st.button("＋ 投稿予約を追加 (Add Posting Card)"):
        st.session_state.reservations.append({
            "id": len(st.session_state.reservations),
            "video_path": None,
            "mode": "Public",
            "date": datetime.date.today(),
            "time": datetime.time(19, 0),
            "thumb_path": None,
            "title": "",
            "description": "",
            "hashtags": []
        })

    # Display Cards
    for i, card in enumerate(st.session_state.reservations):
        with st.expander(f"Reservation #{i+1} - {card['title'] or 'Untitled'}", expanded=True):
            # 1. Video Selection
            # Scan output folder for mp4 files
            video_files = glob.glob("output/**/*.mp4", recursive=True)
            # Sort by modification time (newest first)
            video_files.sort(key=os.path.getmtime, reverse=True)
            
            # Create a selection list with absolute paths but show relative
            video_options = [os.path.abspath(p) for p in video_files]
            display_options = [os.path.relpath(p) for p in video_files]
            
            # Map display to absolute
            path_map = dict(zip(display_options, video_options))
            
            # Current selection
            current_index = 0
            if card["video_path"] in video_options:
                current_index = video_options.index(card["video_path"])
                
            selected_display = st.selectbox(
                f"Select Video file", 
                display_options, 
                index=current_index, 
                key=f"video_sel_{i}"
            )
            
            if selected_display:
                selected_abs_path = path_map[selected_display]
                card["video_path"] = selected_abs_path
                
                # --- University Detection & Auto-Metadata ---
                base_name = os.path.basename(selected_abs_path)
                university = "unknown"
                uni_label = ""
                default_hashtags = ["#English", "#Listening"]
                
                lower_name = base_name.lower()
                if lower_name.startswith("todai"):
                    university = "todai"
                    uni_label = "東大"
                    default_hashtags = ["#東大", "#東大英語", "#東大リスニング", "#英語リスニング", "#大学受験"]
                elif lower_name.startswith("kyoto"):
                    university = "kyoto"
                    uni_label = "京大"
                    default_hashtags = ["#京大", "#京大英語", "#京大リスニング", "#英語リスニング", "#大学受験"]
                elif lower_name.startswith("osaka"):
                    university = "osaka"
                    uni_label = "阪大"
                    default_hashtags = ["#阪大", "#阪大英語", "#阪大リスニング", "#英語リスニング", "#大学受験"]
                
                if not card.get("hashtags"):
                    card["hashtags"] = default_hashtags

                # Auto-load description from timestamp file if empty
                if not card["description"]:
                    # Try to find [filename]_概要欄.txt
                    base_name_no_ext = os.path.splitext(base_name)[0]
                    dir_name = os.path.dirname(selected_abs_path)
                    
                    # Candidate 1: Same directory, [filename]_概要欄.txt
                    cand1 = os.path.join(dir_name, f"{base_name_no_ext}_概要欄.txt")
                    # Candidate 2: Same directory, [filename]_description.txt (legacy)
                    cand2 = os.path.join(dir_name, f"{base_name_no_ext}_description.txt")
                    
                    target_txt = None
                    if os.path.exists(cand1):
                        target_txt = cand1
                    elif os.path.exists(cand2):
                        target_txt = cand2
                        
                    if target_txt:
                        try:
                            with open(target_txt, "r", encoding="utf-8") as f:
                                loaded_desc = f.read()
                            
                            # Auto-extract title from first line if it looks like a title
                            lines = loaded_desc.strip().split('\n')
                            if lines and not card["title"]:
                                first_line = lines[0].strip()
                                if first_line.startswith("【") and "リスニング" in first_line:
                                    card["title"] = first_line
                            
                            card["description"] = loaded_desc
                            st.success(f"Auto-loaded description from {os.path.basename(target_txt)}")
                            st.info(f"Detected University: {university.title()} ({uni_label})")
                        except Exception as e:
                            st.warning(f"Found description file but failed to read: {e}")


            # 2. Mode & Date
            col1, col2, col3 = st.columns(3)
            with col1:
                # Default to Unlisted (index 1) as requested
                card["mode"] = st.selectbox("Privacy Mode", ["private", "unlisted", "public"], index=1, key=f"mode_{i}")
            with col2:
                card["date"] = st.date_input("Posting Date", value=card["date"], key=f"date_{i}")
            with col3:
                card["time"] = st.time_input("Posting Time", value=card["time"], key=f"time_{i}")

            # 3. Thumbnail
            # Try to find png/jpg in the same folder as video
            thumb_options = ["None"]
            if card["video_path"]:
                v_dir = os.path.dirname(card["video_path"])
                thumbs = glob.glob(os.path.join(v_dir, "*.png")) + glob.glob(os.path.join(v_dir, "*.jpg"))
                thumb_options.extend([os.path.abspath(t) for t in thumbs])
            
            card["thumb_path"] = st.selectbox("Thumbnail", thumb_options, key=f"thumb_{i}")
            if card["thumb_path"] != "None":
                 st.image(card["thumb_path"], width=200)

            # 4. Title & Description & Hashtags
            card["title"] = st.text_input("Video Title", value=card["title"], key=f"title_{i}")
            
            # Hashtags Input (as comma separated string for editing)
            current_tags_str = ", ".join(card.get("hashtags", []))
            new_tags_str = st.text_input("Hashtags (comma separated)", value=current_tags_str, key=f"tags_{i}")
            card["hashtags"] = [t.strip() for t in new_tags_str.split(",") if t.strip()]
            
            card["description"] = st.text_area("Description", value=card["description"], height=200, key=f"desc_{i}")

            # 5. Upload Button
            st.markdown("---")
            st.caption("Final Verification:")
            st.code(f"Title: {card['title']}\nTags: {card['hashtags']}")
            
            if st.button(f"Upload to YouTube #{i+1}", key=f"upload_{i}"):
                if not card["video_path"] or not os.path.exists(card["video_path"]):
                    st.error("Invalid Video Path")
                elif not card["title"]:
                    st.error("Title is required")
                else:
                    with st.spinner(f"Uploading '{card['title']}'..."):
                        # Prepare publish_at string if needed
                        # Format: YYYY-MM-DDThh:mm:ss.sZ
                        publish_at_str = None
                        # If user wants to schedule, they usually set date/time. 
                        # Assuming if mode is 'private' and they set a future date, they might want to schedule?
                        # Or maybe we should add a checkbox "Schedule Post"?
                        # For now, let's just pass the date if it's explicitly set? 
                        # Actually, let's look at the UI requirement: "Posting Date/Time".
                        # If I pass publish_at, privacy must be private.
                        # Let's combine date and time.
                        dt = datetime.datetime.combine(card["date"], card["time"])
                        # Check if it's in the future? 
                        # Let's assume user intends to schedule if they picked a date. 
                        # But wait, default is today/now. 
                        # Let's check if mode is 'private' + user wants to schedule.
                        # I will add a checkbox "Schedule (Reservation)" to be explicit.
                        pass
                    
                    # Re-implementing button logic to include checkbox inside the loop is tricky with Streamlit reruns.
                    # I'll just use the values. If mode is private, I won't auto-schedule unless implicit?
                    # Let's assume if the user set a date, they want to schedule?
                    # To be safe, I will just format the date and pass it if mode is private. 
                    # Actually, let's format it to ISO string.
                    # Note: YouTube requires UTC or timezone offset. 
                    # Assuming local time JST (UTC+9)? Or system time?
                    # I will add 'Z' (UTC) if I convert to UTC, or +09:00.
                    # Let's assume system local time and format with offset if possible.
                    # Or just simple ISO format `YYYY-MM-DDThh:mm:ss` (YouTube might reject without timezone).
                    # `datetime.isoformat()`
                    
                    publish_at_iso = None
                    # Simple heuristic: If date is in the future, treat as schedule?
                    # Or just always pass it if provided?
                    # The prompt asked for "Reservation List", so scheduling is key.
                    # Let's assume the user ALWAYS wants to schedule if they are using this "Reservation" tool, 
                    # UNLESS they select "public" or "unlisted" immediately.
                    # If mode is "private", we can attach publish_at.
                    
                    if card["mode"] == "private":
                         # Create ISO string
                         # Assumption: User inputs JST. Convert to UTC? 
                         # Actually, let's just use +09:00 for simplicity as context is Japanese user.
                         publish_at_iso = dt.isoformat() + "+09:00"
                    
                    thumb_arg = card["thumb_path"] if card["thumb_path"] != "None" else None
                    
                    try:
                        vid_id = uploader.upload_to_youtube(
                            video_file=card["video_path"],
                            title=card["title"],
                            description=card["description"],
                            privacy_status=card["mode"],
                            tags=card["hashtags"],
                            thumbnail_path=thumb_arg,
                            publish_at=publish_at_iso
                        )
                        if vid_id:
                            st.success(f"Upload Successful! Video ID: {vid_id}")
                            
                            # Update History Status
                            if university != "unknown":
                                updated = history_manager.update_history_status(university, card["title"], "Uploaded", video_id=vid_id)
                                if updated:
                                    st.info(f"History updated for {university.title()}: Status -> Uploaded (ID: {vid_id})")
                                else:
                                    # If not found (maybe manual title change?), try to append?
                                    # For now just warn
                                    st.warning(f"Could not find history entry for '{card['title']}' to update status.")
                            
                            # Remove card? Or keep it? User might want record.
                            # st.session_state.reservations.pop(i) # Modifying list while iterating is bad.
                        else:
                            st.error("Upload failed.")
                    except Exception as e:
                        st.error(f"Error: {e}")


if mode == "Before Sleep Podcast Mode":
    st.title("🌙 Before Sleep Podcast Mode")
    st.markdown("""
    **Create a relaxing podcast for bedtime listening.**
    Includes a soothing jingle and a custom theme.
    """)
    
    with st.container():
        col1, col2 = st.columns([2, 1])
        with col1:
            theme = st.text_area("Podcast Theme", placeholder="e.g. A walk in a quiet forest, Healing phrases for stress relief, Basic grammar for sleep", height=100)
        with col2:
            level_options = [
                "英検3級", "英検準2級", "英検2級", "英検準1級", "英検1級",
                "TOEIC600", "TOEIC800", "TOEIC990",
                "ターゲット1900"
            ]
            level = st.radio("Level", level_options, index=2)
            
        if st.button("Start Sleep Podcast Generation", type="primary"):
            if not theme:
                st.error("Please enter a theme.")
            else:
                with st.spinner("Generating Sleep Podcast... Shhh..."):
                    st.info("Check the terminal for detailed progress logs.")
                    try:
                        # Call main function (we will implement this next)
                        video_path, desc_path = main.run_podcast_generation(theme, level, mode="sleep")
                        st.success("Sleep Podcast Generated! Sweet dreams.")
                        
                        if desc_path and os.path.exists(desc_path):
                            with open(desc_path, "r", encoding="utf-8") as f:
                                desc_content = f.read()
                            st.subheader("Generated YouTube Description")
                            st.text_area("Copy this to YouTube:", value=desc_content, height=600)
                            
                    except Exception as e:
                        st.error(f"An error occurred: {e}")
                        import traceback
                        st.text(traceback.format_exc())

elif mode == "Exam Problem Creator":
    st.title("📝 Exam Problem Creator")
    st.markdown("""
    **Create English Exam Problems (Entrance Exam Style)**
    Generate reading comprehension, grammar questions, or vocabulary tests.
    """)
    
    exam_type = st.selectbox("Problem Type", ["Reading Comprehension", "Grammar/Usage", "Vocabulary Test", "Translation"])
    target_school = st.text_input("Target School / Level", placeholder="e.g. University of Tokyo, Common Test")
    
    if st.button("Generate Problem Draft"):
        st.info("This feature is under development. It will use the LLM to generate exam-style questions.")

elif mode == "University Entrance Exam Listening":
    st.title("🎓 University Entrance Exam Listening")
    st.markdown("""
    **Generate Listening Practice Videos for specific University Exams.**
    Customized structure and tone for high-level entrance exams.
    """)
    
    # University Selection via Tabs
    tab_todai, tab_kyoto, tab_osaka = st.tabs(["東京大学 (UTokyo)", "京都大学 (KyotoU)", "大阪大学 (OsakaU)"])
    
    # --- TODAI TAB ---
    with tab_todai:
        next_no_todai = history_manager.get_next_episode_number("todai")
        st.subheader(f"東京大学 (UTokyo) Mode - Next Episode: #{next_no_todai}")
        
        # Todai Settings
        st.info("Vocabulary Source: 英単語帳鉄壁")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            teppeki_start_todai = st.number_input("Start Word No.", min_value=1, value=1, key="teppeki_start_todai")
        with col_t2:
            teppeki_end_todai = st.number_input("End Word No.", min_value=1, value=50, key="teppeki_end_todai")
        topic_todai = st.text_input("Discussion Topic (Optional)", "", key="topic_todai")

        st.markdown("""
        - **Format**: 3 Speakers (Student A, Student B, Professor)
        - **Style**: Academic Discussion / Debate
        - **Structure**: Listening (No Sub) -> Questions -> Review (Red Sub) -> Questions
        """)
        
        if st.button("Generate UTokyo Video", type="primary", key="btn_todai"):
            st.session_state.exam_university = "todai"
            with st.spinner("Generating UTokyo Listening Video..."):
                try:
                    # Calculate day_number
                    day_num = int((teppeki_start_todai - 1) / 10) + 1
                    
                    result = main.run_podcast_generation(
                        topic=topic_todai,
                        level="英単語帳鉄壁",
                        day_number=day_num,
                        mode="university_listening",
                        university="todai",
                        generate_thumb=False
                    )
                    
                    # Handle Result
                    if isinstance(result, tuple) and len(result) == 3:
                        video_path, desc_path, script_path = result
                    else:
                        video_path, desc_path = result
                        script_path = None

                    st.success("UTokyo Video Generated!")
                    
                    # Display Video
                    if video_path and os.path.exists(video_path):
                        st.video(open(video_path, 'rb').read())
                    
                    # Display Script/Desc
                    if desc_path and os.path.exists(desc_path):
                        with open(desc_path, 'r', encoding='utf-8') as f:
                            st.markdown("### 📋 YouTube Description")
                            st.code(f.read(), language="markdown")
                            
                    if script_path and os.path.exists(script_path):
                        with open(script_path, 'r', encoding='utf-8') as f:
                            script_content = f.read()
                            # Highlight Logic
                            try:
                                vocab_list = script_gen.load_teppeki_words(teppeki_start_todai, teppeki_end_todai)
                                highlight_words = [v.get("word", "") for v in vocab_list if v.get("word")]
                                if highlight_words:
                                    patterns = []
                                    for hw in highlight_words:
                                        if not hw: continue
                                        esc = re.escape(hw)
                                        if len(hw) > 3:
                                            if hw.endswith('e'):
                                                base = hw[:-1]
                                                pat = re.escape(base) + r"(?:e|es|d|ed|ing|al|als|ation|ations|ely)?"
                                            elif hw.endswith('y'):
                                                base = hw[:-1]
                                                pat = re.escape(base) + r"(?:y|ies|ied|ying|ily)"
                                            else:
                                                pat = esc + r"(?:s|es|d|ed|ing|ly|al|als|tion|tions)?"
                                        else:
                                            pat = esc
                                        patterns.append(pat)
                                    full_pattern = r"(?i)\b(" + "|".join(patterns) + r")\b"
                                    script_content = re.sub(full_pattern, r"<span style='color:red; font-weight:bold; background-color:#FFFF00;'>\1</span>", script_content)
                            except: pass

                            st.markdown("### 📖 English Script")
                            st.markdown(f"<div style='height:400px; overflow-y:auto; border:1px solid #ccc; padding:10px; background-color:white; color:black;'>{script_content.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Error: {e}")
                    import traceback
                    st.text(traceback.format_exc())

    # --- KYOTO TAB ---
    with tab_kyoto:
        next_no_kyoto = history_manager.get_next_episode_number("kyoto")
        st.subheader(f"京都大学 (KyotoU) Mode - Next Episode: #{next_no_kyoto}")
        
        # Kyoto Settings
        st.info("Vocabulary Source: 英単語帳鉄壁")
        col_k1, col_k2 = st.columns(2)
        with col_k1:
            teppeki_start_kyoto = st.number_input("Start Word No.", min_value=1, value=1, key="teppeki_start_kyoto")
        with col_k2:
            teppeki_end_kyoto = st.number_input("End Word No.", min_value=1, value=50, key="teppeki_end_kyoto")
        topic_kyoto = st.text_input("Discussion Topic (Optional)", "", key="topic_kyoto")
        
        st.markdown("""
        - **Format**: 1 Speaker (Dr. Smith / Andrew)
        - **Style**: Abstract Academic Lecture (Philosophy, Science, etc.)
        - **Length**: 550-600 words (Dense)
        - **Structure**: Listening (No Sub) -> Questions -> Review (Red Sub) -> Questions
        """)
        
        if st.button("Generate KyotoU Video", type="primary", key="btn_kyoto"):
            st.session_state.exam_university = "kyoto"
            with st.spinner("Generating KyotoU Listening Video..."):
                try:
                    # Calculate day_number
                    day_num = int((teppeki_start_kyoto - 1) / 10) + 1
                    
                    result = main.run_podcast_generation(
                        topic=topic_kyoto,
                        level="英単語帳鉄壁",
                        day_number=day_num,
                        mode="university_listening",
                        university="kyoto",
                        generate_thumb=False
                    )
                    
                    # Handle Result (Duplicate logic for now, can refactor later)
                    if isinstance(result, tuple) and len(result) == 3:
                        video_path, desc_path, script_path = result
                    else:
                        video_path, desc_path = result
                        script_path = None

                    st.success("KyotoU Video Generated!")
                    
                    if video_path and os.path.exists(video_path):
                        st.video(open(video_path, 'rb').read())
                    
                    if desc_path and os.path.exists(desc_path):
                        with open(desc_path, 'r', encoding='utf-8') as f:
                            st.markdown("### 📋 YouTube Description")
                            st.code(f.read(), language="markdown")
                            
                    if script_path and os.path.exists(script_path):
                        with open(script_path, 'r', encoding='utf-8') as f:
                            script_content = f.read()
                            # Highlight Logic
                            try:
                                vocab_list = script_gen.load_teppeki_words(teppeki_start_kyoto, teppeki_end_kyoto)
                                highlight_words = [v.get("word", "") for v in vocab_list if v.get("word")]
                                if highlight_words:
                                    patterns = []
                                    for hw in highlight_words:
                                        if not hw: continue
                                        esc = re.escape(hw)
                                        if len(hw) > 3:
                                            if hw.endswith('e'):
                                                base = hw[:-1]
                                                pat = re.escape(base) + r"(?:e|es|d|ed|ing|al|als|ation|ations|ely)?"
                                            elif hw.endswith('y'):
                                                base = hw[:-1]
                                                pat = re.escape(base) + r"(?:y|ies|ied|ying|ily)"
                                            else:
                                                pat = esc + r"(?:s|es|d|ed|ing|ly|al|als|tion|tions)?"
                                        else:
                                            pat = esc
                                        patterns.append(pat)
                                    full_pattern = r"(?i)\b(" + "|".join(patterns) + r")\b"
                                    script_content = re.sub(full_pattern, r"<span style='color:red; font-weight:bold; background-color:#FFFF00;'>\1</span>", script_content)
                            except: pass

                            st.markdown("### 📖 English Script")
                            st.markdown(f"<div style='height:400px; overflow-y:auto; border:1px solid #ccc; padding:10px; background-color:white; color:black;'>{script_content.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Error: {e}")
                    import traceback
                    st.text(traceback.format_exc())

    # --- OSAKA TAB ---
    with tab_osaka:
        next_no_osaka = history_manager.get_next_episode_number("osaka")
        st.subheader(f"大阪大学 (OsakaU) Mode - Next Episode: #{next_no_osaka}")
        
        # Osaka Settings - UI Update (No Range Inputs, Hybrid Source Info)
        st.info("Vocabulary Source: ランダム抽出（鉄壁 + ターゲット1900）")
        st.caption("※ 阪大モードは、全範囲からランダムに15単語（鉄壁＋ターゲット1900）を抽出します。範囲指定は不要です。")
        
        # Callback to update title when topic changes
        def update_osaka_title():
            t = st.session_state.topic_osaka
            # Recalculate or use current next_no (it shouldn't change during session mostly)
            # We can use the variable from outer scope if we are careful, but better to be explicit or use session state
            # Simple format:
            st.session_state.title_osaka = f"【阪大リスニング】第{next_no_osaka}回：{t}"

        topic_osaka = st.text_input("Discussion Topic (Optional)", "", key="topic_osaka", on_change=update_osaka_title)
        
        # Initialize title if not in session state
        if "title_osaka" not in st.session_state:
             st.session_state.title_osaka = f"【阪大リスニング】第{next_no_osaka}回："
        
        title_osaka = st.text_input("Video Title (YouTube)", key="title_osaka")
        
        st.markdown("""
        - **Format**: 1 Speaker (Student B / Sarah)
        - **Style**: Practical Academic Presentation (AI, Medical, Environment)
        - **Length**: Approx 500 words (Practical & Structured)
        - **Vocab**: Hybrid (Teppeki + Target 1900)
        """)
        
        if st.button("Generate OsakaU Video", type="primary", key="btn_osaka"):
            st.session_state.exam_university = "osaka"
            with st.spinner("Generating OsakaU Listening Video (Hybrid Vocab)..."):
                try:
                    # For Osaka, we ignore teppeki_start/end and use Hybrid Loader
                    # We pass a special level or handle it in main
                    
                    result = main.run_podcast_generation(
                        topic=topic_osaka,
                        level="OsakaHybrid", # Signal to main/script_gen to use hybrid
                        day_number=1, # Ignored for hybrid
                        mode="university_listening",
                        university="osaka",
                        generate_thumb=False,
                        custom_title=title_osaka
                    )
                    
                    # Handle Result (Duplicate logic for now)
                    if isinstance(result, tuple) and len(result) == 3:
                        video_path, desc_path, script_path = result
                    else:
                        video_path, desc_path = result
                        script_path = None

                    st.success("OsakaU Video Generated!")
                    
                    if video_path and os.path.exists(video_path):
                        st.video(open(video_path, 'rb').read())
                    
                    if desc_path and os.path.exists(desc_path):
                        with open(desc_path, 'r', encoding='utf-8') as f:
                            st.markdown("### 📋 YouTube Description")
                            st.code(f.read(), language="markdown")
                            
                    if script_path and os.path.exists(script_path):
                        with open(script_path, 'r', encoding='utf-8') as f:
                            script_content = f.read()
                            # Highlight Logic skipped for random hybrid mode
                            st.caption("※ Random vocabulary highlighted in video.")
                            
                            st.markdown("### 📖 English Script")
                            st.markdown(f"<div style='height:400px; overflow-y:auto; border:1px solid #ccc; padding:10px; background-color:white; color:black;'>{script_content.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Error: {e}")
                    import traceback
                    st.text(traceback.format_exc())

elif mode == "Podcast Generator":
    st.title("🎙️ AI English Podcast Generator")
    st.markdown("""
    **Create a professional English podcast with AI!**
    Select a topic and level below, then click Start.
    """)
    
    # Input form
    with st.container():
        col1, col2 = st.columns([2, 1])
        with col1:
            topic = st.text_input("Topic", placeholder="e.g. Future of AI, History of Pizza")
        with col2:
            level_options = [
                "英検3級", "英検準2級", "英検2級", "英検準1級", "英検1級",
                "TOEIC600", "TOEIC800", "TOEIC990",
                "ターゲット1900"
            ]
            level = st.radio("Level", level_options, index=2)
            
            # Day番号とサムネイル生成オプション
            col_day, col_thumb = st.columns(2)
            with col_day:
                day_number = st.number_input("Day Number", min_value=1, value=1)
            with col_thumb:
                generate_thumb = st.checkbox("サムネイルを生成する", value=False)
                
            # テストサムネイル生成ボタン
            if st.button("テストサムネイルを生成"):
                with st.spinner("Generating Test Thumbnail..."):
                    # トピックが空の場合はダミーを使用
                    test_topic = topic if topic else "Test Topic"
                    try:
                        thumb_path = video_gen.generate_thumbnail(test_topic, level, day_number=day_number, output_path="test_thumbnail.png")
                        if thumb_path and os.path.exists(thumb_path):
                            st.image(thumb_path, caption=f"Generated Thumbnail (Level: {level}, Day: {day_number})")
                            st.success("Thumbnail generated successfully!")
                        else:
                            st.error("Thumbnail generation failed. (No path returned or file not found)")
                    except Exception as e:
                        st.error(f"Error detail: {e}")
                        import traceback
                        st.text(traceback.format_exc())

        if st.button("Start Podcast Generation", type="primary"):
            if not topic:
                st.error("Please enter a topic.")
            else:
                with st.spinner("Generating Podcast... This may take a few minutes."):
                    st.info("Check the terminal for detailed progress logs.")
                    try:
                        # main.py の関数を直接呼ぶ
                        video_path, desc_path = main.run_podcast_generation(topic, level, day_number=day_number, generate_thumb=generate_thumb)
                        st.success("Podcast Generation Completed! Check the 'output' folder.")
                        
                        if desc_path and os.path.exists(desc_path):
                            with open(desc_path, "r", encoding="utf-8") as f:
                                desc_content = f.read()
                            st.subheader("Generated YouTube Description")
                            st.text_area("Copy this to YouTube:", value=desc_content, height=600)
                            
                    except Exception as e:
                        st.error(f"An error occurred: {e}")
                        import traceback
                        st.text(traceback.format_exc())

elif mode == "Vocalab Mode (Target 1900)":
    st.title("🔬 Vocalab Mode")
    st.markdown("""
    **Generate a strict 5-step learning video.**
    
    1. English Word (x2)
    2. Meaning (x1)
    3. Example EN (x2, Screen Off)
    4. Example EN (x1, Full Display)
    5. Example JP (x1)
    """)
    
    tab1, tab2 = st.tabs(["Target 1900 Range", "Manual Word List"])
    
    target_range_str = None
    word_list_input = None
    
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            v_start = st.number_input("Start No.", min_value=1, value=1)
        with col2:
            v_end = st.number_input("End No.", min_value=1, value=5)
        
        target_range_str = f"{v_start}-{v_end}"
        st.caption(f"Selected Range: {target_range_str}")
        
    with tab2:
        manual_words = st.text_area("Enter words (comma separated)", placeholder="apple, banana, cherry")
        if manual_words:
            word_list_input = [w.strip() for w in manual_words.split(",") if w.strip()]
            
    # Priority: Manual > Range
    final_range = target_range_str
    final_words = []
    
    # If tab2 was interacted with and has content, use it? 
    # Streamlit re-runs script on interaction. We need to decide logic.
    # Let's use a radio or just logic: if manual_words is not empty, use it.
    
    use_manual = False
    if manual_words:
        use_manual = True
        st.info(f"Using Manual Word List ({len(word_list_input)} words)")
    else:
        st.info(f"Using Target 1900 Range: {target_range_str}")
        
    v_topic = st.text_input("Topic (Optional)", value="Vocalab Mode")
    
    if st.button("Start Vocalab Generation", type="primary"):
        with st.spinner("Generating Vocalab Video..."):
            st.info("Check terminal for progress.")
            try:
                # Call main.run_vocalab_generation
                # signature: run_vocalab_generation(words: list, topic: str = "Vocalab Mode", target_range: str = None)
                
                if use_manual:
                    output_path = main.run_vocalab_generation(word_list_input, topic=v_topic, target_range=None)
                else:
                    output_path = main.run_vocalab_generation([], topic=v_topic, target_range=final_range)
                
                if output_path is not None and output_path != "" and os.path.exists(output_path):
                    st.success(f"Video Generated! Saved to: {output_path}")
                    # Fix for local video playback: read as bytes
                    st.video(open(output_path, 'rb').read())
                else:
                    st.error("Video generation failed (No output path returned or file missing).")
                    
            except Exception as e:
                st.error(f"Error: {e}")
                import traceback
                st.text(traceback.format_exc())

elif mode == "Word Audio Mode (Target Series)":
    st.title("🎧 Word Audio Mode (Target Series)")
    st.markdown("""
    **Simple audio learning video for Target 1200/1400/1900.**
    
    - Fixed Male Voices (EN: Christopher, JP: Keita)
    - Simple Black/Dark Background
    - No Effects, Just Audio & Text
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        book_map = {
            "Target 1900": "t1900", 
            "Target 1400": "t1400", 
            "Target 1200": "t1200", 
            "鉄壁（てっぺき）": "teppeki", 
            "システム英単語": "systan", 
            "でる順準1級": "derujun",
            "LEAP": "leap"
        }
        book_label = st.selectbox("Select Book", list(book_map.keys()))
        selected_book = book_map[book_label]
        
    with col2:
        submode_map = {
            "EN -> JP": "en_jp", 
            "JP -> EN": "jp_en", 
            "EN Only": "en_only"
        }
        submode_label = st.selectbox("Playback Mode", list(submode_map.keys()))
        selected_submode = submode_map[submode_label]
        
    col3, col4 = st.columns(2)
    with col3:
        wa_start = st.number_input("Start No.", min_value=1, value=1, key="wa_start")
    with col4:
        wa_end = st.number_input("End No.", min_value=1, value=100, key="wa_end")
        use_shuffle = st.checkbox("Shuffle Order", value=False)
        
    range_str = f"{wa_start}-{wa_end}"

    # --- Gap Settings with Persistence ---
    st.markdown("### 読み上げ間隔調整")
    
    # Load settings
    import json
    SETTINGS_FILE = "word_audio_settings.json"
    defaults = {
        "gap_eng_to_jap": 0.5,
        "gap_between_jap": 1.2,
        "gap_next_word": 1.3
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                saved = json.load(f)
                defaults.update(saved)
        except:
            pass
            
    gap_col1, gap_col2, gap_col3 = st.columns(3)
    with gap_col1:
        gap_eng_to_jap = st.slider("Eng → Jap 待機", 0.1, 2.0, float(defaults["gap_eng_to_jap"]), 0.1, key="gap_ej", format="%.1fs")
    with gap_col2:
        gap_between_jap = st.slider("意味同士の間隔（2つ以上ある時）", 0.1, 2.0, float(defaults["gap_between_jap"]), 0.1, key="gap_jj", format="%.1fs")
    with gap_col3:
        gap_next_word = st.slider("次の単語への間隔", 0.1, 2.0, float(defaults["gap_next_word"]), 0.1, key="gap_nw", format="%.1fs")

    st.info(f"Settings: {selected_book} | {range_str} | {selected_submode}")

    # --- Video Extras (Countdown & End Screen) ---
    st.markdown("### Video Extras")
    use_countdown = st.checkbox("Add Countdown (5s)", value=True)
    
    st.markdown("#### End Screen Text")
    end_left_text = st.text_input("Left Text (Next Video)", value="No. 〇〇〜の動画")
    end_right_text = st.text_input("Right Text (Random/Other)", value="only english ランダム")
    end_duration = st.slider("End Screen Duration (sec)", 5, 20, 10)
    
    if st.button("Start Word Audio Generation", type="primary"):
        # Save settings
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump({
                    "gap_eng_to_jap": gap_eng_to_jap,
                    "gap_between_jap": gap_between_jap,
                    "gap_next_word": gap_next_word
                }, f)
        except:
            pass

        with st.spinner("Generating Word Audio Video..."):
            st.info("Check terminal for progress.")
            try:
                output_path = main.run_word_audio_generation(
                    selected_book, range_str, selected_submode,
                    gap_eng_to_jap=gap_eng_to_jap,
                    gap_between_jap=gap_between_jap,
                    gap_next_word=gap_next_word,
                    use_countdown=use_countdown,
                    end_left_text=end_left_text,
                    end_right_text=end_right_text,
                    end_duration=end_duration,
                    use_shuffle=use_shuffle
                )
                
                if output_path is not None and output_path != "" and os.path.exists(output_path):
                    st.success(f"Video Generated! Saved to: {output_path}")
                    # Fix for local video playback: read as bytes
                    st.video(open(output_path, 'rb').read())
                else:
                    st.error("動画パスが取得できませんでした。生成ログを確認してください。")
            except Exception as e:
                st.error(f"Error: {e}")
                import traceback
                st.text(traceback.format_exc())

else:
    # Listening Video Mode (Legacy)
    st.title("🎧 Listening Video Generator")
    st.markdown("""
    **Generate a listening practice video from Target 1900 CSV.**
    
    1. Example Sentence (Normal Speed)
    2. Japanese Translation
    3. Example Sentence (0.8x Speed)
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        start_id = st.number_input("Start ID (No.)", min_value=1, value=1, step=1)
    with col2:
        end_id = st.number_input("End ID (No.)", min_value=1, value=50, step=1)

    # Options
    col3, col4 = st.columns(2)
    with col3:
        difficulty = st.selectbox("Example Difficulty", ["easy", "middle", "hard"], index=1)
    with col4:
        font_map = {
            "Meiryo (メイリオ)": "C:\\Windows\\Fonts\\meiryo.ttc",
            "MS Gothic (MS ゴシック)": "C:\\Windows\\Fonts\\msgothic.ttc",
            "Yu Gothic (遊ゴシック)": "C:\\Windows\\Fonts\\YuGothM.ttc",
            "BIZ UDPGothic": "C:\\Windows\\Fonts\\BIZ-UDPGothicR.ttc",
            "Arial": "C:\\Windows\\Fonts\\arial.ttf"
        }
        
        # English Font
        font_name_en = st.selectbox("Font (English)", list(font_map.keys()), index=4) # Default to Arial for EN
        selected_font_path_en = font_map[font_name_en]
        
        # Japanese Font
        font_name_jp = st.selectbox("Font (Japanese)", list(font_map.keys()), index=0) # Default to Meiryo for JP
        selected_font_path_jp = font_map[font_name_jp]
        
    # Advanced Audio Settings
    with st.expander("Detailed Audio Settings (Speed & Repetition)", expanded=False):
        st.markdown("Configure the reading steps for each word.")
        step_cols = st.columns(3)
        
        speed_options = [0.5, 0.75, 0.8, 1.0, 1.25, 1.5]
        
        # Step 1: En 1
        with step_cols[0]:
            st.markdown("### Step 1 (En)")
            s1_speed = st.selectbox("Speed", speed_options, index=3, key="s1_speed") # Default 1.0
            s1_repeat = st.number_input("Repeat", min_value=0, max_value=10, value=1, key="s1_repeat")
            
        # Step 2: Jp
        with step_cols[1]:
            st.markdown("### Step 2 (Jp)")
            s2_speed = st.selectbox("Speed", speed_options, index=3, key="s2_speed") # Default 1.0
            s2_repeat = st.number_input("Repeat", min_value=0, max_value=10, value=1, key="s2_repeat")
            
        # Step 3: En 2
        with step_cols[2]:
            st.markdown("### Step 3 (En)")
            s3_speed = st.selectbox("Speed", speed_options, index=2, key="s3_speed") # Default 0.8
            s3_repeat = st.number_input("Repeat", min_value=0, max_value=10, value=1, key="s3_repeat")

    # Intro Settings
    with st.expander("Intro Settings", expanded=False):
        intro_text = st.text_area("Intro Text", value="Target 1900 Listening Practice\nUniversity Entrance Exam Level", height=100)
        st.caption("This text will be displayed at the start of the video. Place 'intro_music.mp3' in 'assets' folder for background music.")

    # Construct config
    step_config = [
        {"type": "en", "label": f"Example (x{s1_speed})", "speed": s1_speed, "repeat": s1_repeat},
        {"type": "jp", "label": "Japanese", "speed": s2_speed, "repeat": s2_repeat},
        {"type": "en", "label": f"Example (x{s3_speed})", "speed": s3_speed, "repeat": s3_repeat}
    ]
    # Filter out steps with repeat=0 (user might want to skip a step)
    step_config = [s for s in step_config if s["repeat"] > 0]
        
    st.info(f"Generating video for {end_id - start_id + 1} words. (Diff: {difficulty}, Steps: {len(step_config)})")
    
    if st.button("Generate Listening Video", type="primary"):
        with st.spinner("Generating Listening Video... This may take a while."):
            st.info("Check the terminal for detailed progress logs.")
            try:
                output_path = main.run_listening_generation(
                    start_id, 
                    end_id, 
                    difficulty=difficulty, 
                    font_path_en=selected_font_path_en,
                    font_path_jp=selected_font_path_jp,
                    step_config=step_config,
                    intro_text=intro_text
                )
                if output_path is not None and output_path != "" and os.path.exists(output_path):
                    st.success(f"Video Generation Completed! Saved to: {output_path}")
                    st.video(open(output_path, 'rb').read())
                else:
                    st.error(f"Video generation failed. Path invalid or file missing: {output_path}")
            except Exception as e:
                st.error(f"An error occurred: {e}")
                import traceback
                st.text(traceback.format_exc())