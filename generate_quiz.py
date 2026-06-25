import pandas as pd
import re
import base64
import io
import html
from PIL import Image
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTImage, LTFigure, LTTextBox, LTTextLine

# File Names (Make sure these match your files in the folder)
PDF_FILE = 'STALL_QB_ENGLISH_NEW.pdf'
CSV_FILE = 'STALL_QB_ENGLISH_NEW.xlsx - Table 1.csv'
OUTPUT_FILE = 'index.html'

def extract_images_from_pdf(pdf_path):
    print("Scanning PDF and extracting images... (This might take a minute)")
    q_to_b64 = {}
    
    # Process the PDF page by page
    for page_layout in extract_pages(pdf_path):
        images = []
        q_nums = []
        
        for element in page_layout:
            # Look for Images
            if isinstance(element, LTFigure):
                for child in element:
                    if isinstance(child, LTImage):
                        # Calculate vertical center of the image
                        y_center = (child.bbox[1] + child.bbox[3]) / 2
                        images.append({'y': y_center, 'data': child.stream.get_data()})
            
            # Look for Question Numbers (Text on the far left)
            elif isinstance(element, LTTextBox):
                for text_line in element:
                    if isinstance(text_line, LTTextLine):
                        text = text_line.get_text().strip()
                        # If it's a number and on the left margin
                        if re.match(r'^\d+$', text) and text_line.bbox[0] < 100:
                            y_center = (text_line.bbox[1] + text_line.bbox[3]) / 2
                            q_nums.append({'y': y_center, 'q_num': text})
        
        # Sort both lists from top to bottom of the page
        images = sorted(images, key=lambda x: x['y'], reverse=True)
        q_nums = sorted(q_nums, key=lambda x: x['y'], reverse=True)
        
        # Match images to the closest question number on the same row
        for img in images:
            if not q_nums: 
                continue
            closest_q = min(q_nums, key=lambda q: abs(q['y'] - img['y']))
            
            # If they are vertically aligned (within 100 points)
            if abs(closest_q['y'] - img['y']) < 100:
                try:
                    # Read image, resize it, compress it, and convert to base64
                    img_stream = io.BytesIO(img['data'])
                    pil_img = Image.open(img_stream)
                    if pil_img.mode != 'RGB':
                        pil_img = pil_img.convert('RGB')
                    
                    # Resize to a web-friendly size to keep HTML fast
                    pil_img.thumbnail((250, 250))
                    out_stream = io.BytesIO()
                    pil_img.save(out_stream, format='JPEG', quality=80)
                    b64_data = base64.b64encode(out_stream.getvalue()).decode('utf-8')
                    
                    q_to_b64[closest_q['q_num']] = b64_data
                except Exception as e:
                    print(f"Failed to process image for Question {closest_q['q_num']}: {e}")
                    
    print(f"Successfully extracted {len(q_to_b64)} images from the PDF.")
    return q_to_b64

def generate_html(csv_path, q_to_b64, output_path):
    print("Reading CSV and generating HTML layout...")
    df = pd.read_csv(csv_path)
    
    # Clean data
    for col in df.columns:
        df[col] = df[col].astype(str).replace('nan', '')
        
    html_cards = ""
    
    for index, row in df.iterrows():
        question = row.get('QUESTION', '').strip()
        if not question: 
            continue
            
        q_num = row.get('Q_NUMBER', '').strip()
        if not q_num: q_num = str(index + 1)
        if q_num.endswith('.0'): q_num = q_num[:-2]
        
        ans = row.get('ANSWER', '').strip()
        if ans.endswith('.0'): ans = ans[:-2]
        
        options = [
            row.get('OPTION1', '').strip(),
            row.get('OPTION2', '').strip(),
            row.get('OPTION3', '').strip()
        ]
        
        # 1. Build the Left Side (Question & Image)
        img_html = ""
        if q_num in q_to_b64:
            img_html = f'''
            <div class="mt-6 p-4 bg-white rounded-lg border-2 border-gray-200 inline-block">
                <img src="data:image/jpeg;base64,{q_to_b64[q_num]}" class="max-h-[180px] object-contain" alt="Question {q_num} Image">
            </div>'''
            
        left_side = f'''
        <div class="md:w-[45%] p-8 bg-slate-50 border-b md:border-b-0 md:border-r border-gray-200 flex flex-col justify-center">
            <span class="text-sm font-bold text-blue-600 mb-3 uppercase tracking-wider">Question {q_num}</span>
            <h2 class="text-2xl font-semibold text-gray-800 leading-snug">{html.escape(question)}</h2>
            {img_html}
        </div>
        '''
        
        # 2. Build the Right Side (Options with Green Highlight for Answer)
        options_html = ""
        for i, opt in enumerate(options):
            if opt:
                is_correct = (str(i+1) == ans)
                if is_correct:
                    options_html += f'''
                    <div class="p-5 rounded-xl border-2 border-green-400 bg-green-50 text-green-900 font-bold relative shadow-sm">
                        {html.escape(opt)}
                       <!-- <span class="absolute right-4 top-1/2 -translate-y-1/2 text-green-700 bg-green-200 px-3 py-1 rounded-md text-xs uppercase tracking-wide font-black">✓ Correct Answer</span> -->
                    </div>
                    '''
                else:
                    options_html += f'''
                    <div class="p-5 rounded-xl border-2 border-gray-200 bg-white text-gray-600 font-medium shadow-sm hover:border-gray-300 transition-colors">
                        {html.escape(opt)}
                    </div>
                    '''
        
        if not options_html:
            options_html = "<div class='text-gray-400 italic'>No options provided for this question.</div>"
            
        right_side = f'''
        <div class="md:w-[55%] p-8 flex flex-col justify-center space-y-4 bg-white">
            {options_html}
        </div>
        '''
        
        # 3. Combine into a Card
        html_cards += f'''
        <div class="flex flex-col md:flex-row bg-white rounded-2xl shadow-md border border-gray-200 overflow-hidden mb-8 transition-transform hover:-translate-y-1 duration-300">
            {left_side}
            {right_side}
        </div>
        '''

    # Final HTML Template using Tailwind CSS for beautiful styling
    final_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Driving Rules & Signs Quiz Directory</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
    </style>
</head>
<body class="bg-gray-100 min-h-screen p-6 md:p-12 text-gray-800">
    
    <div class="max-w-6xl mx-auto mb-10 text-center">
        <h1 class="text-4xl md:text-5xl font-black text-slate-800 mb-4 tracking-tight">Driving Rules Quiz Directory</h1>
        <p class="text-lg text-slate-500 font-medium">Complete overview of all questions, signs, and correct answers.</p>
    </div>

    <div class="max-w-6xl mx-auto">
        {html_cards}
    </div>

</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_html)
    print(f"Done! Open '{output_path}' in your web browser to view your quiz.")

if __name__ == "__main__":
    extracted_images = extract_images_from_pdf(PDF_FILE)
    generate_html(CSV_FILE, extracted_images, OUTPUT_FILE)
