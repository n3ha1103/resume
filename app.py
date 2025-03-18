import os
import re
import PyPDF2
import pytesseract
import cv2
import numpy as np
import pdf2image
import tempfile
import json
import base64
from flask import Flask, request, render_template, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image
import threading
import webbrowser

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Global variables to store resume data
resume_data = {
    "full_text": "",
    "sections": {
        "Education": "",
        "Experience": "",
        "Projects": "",
        "Skills": "",
        "Other": ""
    },
    "current_file": None
}

def extract_text(file_path):
    """Extract text from PDF or image file using OCR if needed"""
    _, ext = os.path.splitext(file_path)
    
    if ext.lower() == '.pdf':
        # First try normal PDF text extraction
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                page_text = page.extract_text()
                
                # If page has no text content, it might be a scanned PDF
                if not page_text or len(page_text.strip()) < 100:
                    # Convert PDF to images and perform OCR
                    return extract_text_with_ocr(file_path)
                
                text += page_text + "\n"
            
            return text
    else:
        # For image files, use OCR directly
        return extract_text_with_ocr(file_path)

def extract_text_with_ocr(file_path):
    """Extract text using OCR with pytesseract and OpenCV for preprocessing"""
    _, ext = os.path.splitext(file_path)
    
    if ext.lower() == '.pdf':
        # Convert PDF to images
        with tempfile.TemporaryDirectory() as path:
            images = pdf2image.convert_from_path(file_path)
            text = ""
            
            for i, image in enumerate(images):
                image_path = os.path.join(path, f'page_{i}.png')
                image.save(image_path, 'PNG')
                
                # Use OpenCV for image preprocessing
                img = cv2.imread(image_path)
                img = preprocess_image(img)
                
                # Save preprocessed image
                preprocessed_path = os.path.join(path, f'preprocessed_{i}.png')
                cv2.imwrite(preprocessed_path, img)
                
                # Extract text with OCR
                text += pytesseract.image_to_string(Image.open(preprocessed_path)) + "\n"
            
            return text
    else:
        # Process single image with OCR
        img = cv2.imread(file_path)
        img = preprocess_image(img)
        
        # Save preprocessed image
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp:
            preprocessed_path = temp.name
            cv2.imwrite(preprocessed_path, img)
        
        text = pytesseract.image_to_string(Image.open(preprocessed_path))
        os.unlink(preprocessed_path)  # Delete temporary file
        return text

def preprocess_image(img):
    """Preprocess image using OpenCV to improve OCR accuracy"""
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply thresholding
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Apply noise removal
    kernel = np.ones((1, 1), np.uint8)
    opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    
    # Apply dilation
    kernel = np.ones((1, 1), np.uint8)
    dilated = cv2.dilate(opening, kernel, iterations=1)
    
    return dilated

def parse_sections(text):
    """Parse resume into sections"""
    sections = {
        "Education": "",
        "Experience": "",
        "Projects": "",
        "Skills": "",
        "Other": ""
    }
    
    # Define section patterns
    section_patterns = {
        "Education": r"(?i)(education|academic|qualification)",
        "Experience": r"(?i)(experience|work|employment|professional)",
        "Projects": r"(?i)(projects|portfolio)",
        "Skills": r"(?i)(skills|technical skills|competencies|expertise)"
    }
    
    # Find potential section headers
    lines = text.split('\n')
    current_section = "Other"
    
    for i, line in enumerate(lines):
        if not line.strip():
            continue
            
        # Check if line looks like a section header
        for section, pattern in section_patterns.items():
            if re.search(pattern, line, re.IGNORECASE) and (len(line) < 50):
                current_section = section
                break
        
        # Add content to current section
        if i > 0:  # Skip adding the header itself
            sections[current_section] += line + "\n"
    
    return sections

def search_resume(query):
    """Search for keywords in the resume"""
    query = query.strip().lower()
    
    if not query:
        return {"status": "error", "message": "Please enter a search term."}
    
    if not resume_data["full_text"]:
        return {"status": "error", "message": "Please upload a resume first."}
    
    results = []
    
    # Search in each section
    for section, text in resume_data["sections"].items():
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if query in line.lower():
                context = get_context(lines, i)
                results.append(f"Found in {section}:\n{context}\n")
    
    if results:
        return {"status": "success", "results": results}
    else:
        return {"status": "success", "results": [f"No results found for '{query}'"]}

def get_context(lines, index, context_lines=2):
    """Get context around a matched line"""
    start = max(0, index - context_lines)
    end = min(len(lines), index + context_lines + 1)
    
    context = []
    for i in range(start, end):
        prefix = ">>> " if i == index else "    "
        if lines[i].strip():
            context.append(f"{prefix}{lines[i]}")
    
    return "\n".join(context)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"})
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"})
    
    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        try:
            # Extract text from the file
            text = extract_text(file_path)
            sections = parse_sections(text)
            
            # Update global resume data
            resume_data["full_text"] = text
            resume_data["sections"] = sections
            resume_data["current_file"] = filename
            
            return jsonify({
                "status": "success", 
                "message": f"File processed successfully: {filename}",
                "sections": sections,
                "full_text": text
            })
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error processing file: {str(e)}"})

@app.route('/get_section/<section>')
def get_section(section):
    if section == "all":
        return jsonify({
            "status": "success",
            "title": "FULL RESUME",
            "content": resume_data["full_text"]
        })
    
    if section in resume_data["sections"]:
        return jsonify({
            "status": "success",
            "title": section.upper(),
            "content": resume_data["sections"][section]
        })
    else:
        return jsonify({
            "status": "error", 
            "message": f"Section '{section}' not found"
        })

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json()
    query = data.get('query', '')
    return jsonify(search_resume(query))

@app.route('/update_section', methods=['POST'])
def update_section():
    data = request.get_json()
    section = data.get('section')
    content = data.get('content')
    
    if section and content is not None:
        if section == "full_resume":
            # Update full resume text and re-parse sections
            resume_data["full_text"] = content
            resume_data["sections"] = parse_sections(content)
            return jsonify({
                "status": "success", 
                "message": "Full resume updated successfully",
                "sections": resume_data["sections"]
            })
        elif section in resume_data["sections"]:
            # Update specific section
            resume_data["sections"][section] = content
            
            # Reconstruct full text
            full_text = ""
            for section_name, section_content in resume_data["sections"].items():
                if section_content.strip():
                    full_text += f"\n{section_name.upper()}\n{section_content}\n"
            
            resume_data["full_text"] = full_text
            
            return jsonify({
                "status": "success", 
                "message": f"Section '{section}' updated successfully"
            })
        else:
            return jsonify({
                "status": "error", 
                "message": f"Section '{section}' not found"
            })
    else:
        return jsonify({
            "status": "error", 
            "message": "Missing section or content"
        })

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

def generate_html_templates():
    """Generate HTML templates for the application"""
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)

def open_browser():
    """Open web browser to the application URL"""
    webbrowser.open(f'http://127.0.0.1:5000')

if __name__ == '__main__':
    # Generate HTML templates
    generate_html_templates()
    
    # Open browser in a separate thread
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    # Start Flask server
    app.run(debug=True)