
def create_jingle_clip(jingle_path, title="🌙 おやすみEnglishラジオ", logo_path="assets/logo_kiai.png", w=1280, h=720):
    """
    Create a jingle video clip with title and logo.
    """
    print(f"  - Generating Jingle Clip: {jingle_path}")
    
    if not os.path.exists(jingle_path):
        print(f"    ! Jingle file not found: {jingle_path}")
        return None
        
    try:
        audio_clip = AudioFileClip(jingle_path)
        duration = audio_clip.duration
        
        # Create Image
        img = Image.new('RGBA', (w, h), (10, 10, 30, 255)) # Dark blue background
        draw = ImageDraw.Draw(img)
        
        # Font
        font_path = get_font_path()
        try:
            font_title = ImageFont.truetype(font_path, 80) if font_path else ImageFont.load_default()
        except:
            font_title = ImageFont.load_default()
            
        # Draw Title (Center)
        try:
            bbox = draw.textbbox((0, 0), title, font=font_title)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except:
            tw, th = draw.textsize(title, font=font_title)
            
        draw.text(((w - tw) // 2, (h - th) // 2), title, font=font_title, fill="white")
        
        # Draw Logo (Above Title)
        if logo_path and os.path.exists(logo_path):
            try:
                logo = Image.open(logo_path).convert("RGBA")
                # Resize
                aspect = logo.height / logo.width
                new_w = 200
                new_h = int(new_w * aspect)
                logo = logo.resize((new_w, new_h))
                
                logo_x = (w - new_w) // 2
                logo_y = (h - th) // 2 - new_h - 40
                
                img.paste(logo, (logo_x, logo_y), logo)
            except Exception as e:
                print(f"    ! Failed to load logo for jingle: {e}")

        img_np = np.array(img)
        video_clip = ImageClip(img_np)
        video_clip = with_duration_compat(video_clip, duration)
        video_clip = with_audio_compat(video_clip, audio_clip)
        
        return video_clip
        
    except Exception as e:
        print(f"    ! Error creating jingle clip: {e}")
        return None
