# logic_ocr.py (New File)
import pytesseract
from PIL import Image
import os
import sys # Needed for a better Tesseract path check
from logic_media import determine_directory

# NOTE for macOS/Linux users who used Homebrew/MacPorts: 
# The line below is usually NOT needed. If you get a 'TesseractNotFoundError',
# you can uncomment it and try to find the path (e.g., '/usr/local/bin/tesseract').

# Check if we are running on Windows (where the path is often required)
if sys.platform == "win32" and not os.environ.get('TESSDATA_PREFIX'):
    # FIX APPLIED HERE: Setting the absolute path to the Tesseract executable
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    pass


def process_ocr_scan(filepath):
    """
    Performs OCR on an image file and extracts the text and tags.
    """
    try:
        # 1. Use Pillow to open the image file
        img = Image.open(filepath)
        
        # 2. Use pytesseract to extract text from the image
        extracted_text = pytesseract.image_to_string(img)
        
        # 3. Simple intelligence: Check for common document keywords
        text_lower = extracted_text.lower()
        tags = ["ocr_document"]
        
        # Financial Document Check
        if any(keyword in text_lower for keyword in ["invoice", "bill", "receipt", "payable", "balance"]):
            tags.append("financial_document")
            
        # PII Check (Zero-Trust Feature)
        if any(keyword in text_lower for keyword in ["name", "address", "phone", "email", "ssn"]):
            tags.append("potential_pii")
            
        # Code Snippet Check (Your unique feature)
        if any(keyword in text_lower for keyword in ["class", "import", "def", "public static", "int main", "function", "while", "for"]):
            tags.append("code_snippet") 
            
        # Create a simple, cleaned version of the text to store as a separate searchable file/metadata
        searchable_text = extracted_text.strip().replace('\n', ' ')[:500] # First 500 chars

        return {
            "status": "success",
            "extracted_text_summary": searchable_text,
            "classification_tags": tags,
            "full_text_stored": len(extracted_text) > 0,
            "intelligence_action": f"OCR successful. Identified {len(extracted_text)} characters."
        }
        
    except pytesseract.TesseractNotFoundError:
        return {
            "status": "error",
            "message": "Tesseract OCR engine not found. (Check MacPorts/Homebrew install path).",
            "fix": "Tesseract not found. Please verify 'pytesseract.pytesseract.tesseract_cmd' is set correctly to your installation path."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"OCR processing failed: {str(e)}"
        }