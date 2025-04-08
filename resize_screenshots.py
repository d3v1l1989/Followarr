from PIL import Image
import os

def resize_image(input_path, output_path, max_width=800):
    # Open the image
    with Image.open(input_path) as img:
        # Calculate new height maintaining aspect ratio
        width_percent = (max_width/float(img.size[0]))
        new_height = int((float(img.size[1])*float(width_percent)))
        
        # Resize image
        resized_img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        # Save with high quality
        resized_img.save(output_path, 'PNG', quality=95)

def main():
    # Create output directory if it doesn't exist
    output_dir = 'docs/screenshots/resized'
    os.makedirs(output_dir, exist_ok=True)
    
    # Process each screenshot
    screenshots = [
        'calendar.png',
        'follow.png',
        'unfollow.png',
        'list.png',
        'notification.png'
    ]
    
    for screenshot in screenshots:
        input_path = os.path.join('docs/screenshots', screenshot)
        output_path = os.path.join(output_dir, screenshot)
        
        if os.path.exists(input_path):
            print(f"Resizing {screenshot}...")
            resize_image(input_path, output_path)
            print(f"Saved resized image to {output_path}")
        else:
            print(f"Warning: {input_path} not found")

if __name__ == '__main__':
    main() 