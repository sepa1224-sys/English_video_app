from PIL import Image
import os

def create_dummy_bg():
    if not os.path.exists("assets"):
        os.makedirs("assets")
    
    # Wood-like color (Brown)
    img = Image.new('RGB', (1920, 1080), color=(139, 69, 19))
    img.save("assets/background_wood.png")
    print("Created dummy background_wood.png")

if __name__ == "__main__":
    create_dummy_bg()
