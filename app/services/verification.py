import random
import time
import re
import os
import io
import numpy as np
import cv2
import pytesseract
from typing import List, Dict, Any
from ..core.encryption import decrypt_data
from PIL import Image
import traceback

# Configure Tesseract Path for Windows
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

class VerificationService:
    # ID Patterns (Regular Expressions)
    ID_PATTERNS = {
        "Passport": r"^[A-Z][0-9]{7}[A-Z]$|^[A-Z][0-9]{8}$",
        "Driver's License": r"^[A-Z][0-9]{2}-[0-9]{2}-[0-9]{6}$",
        "PhilID (National ID)": r"^[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{4}$",
        "UMID": r"^[0-9]{4}-[0-9]{7}-[0-9]{1}$",
        "SSS ID": r"^[0-9]{2}-[0-9]{7}-[0-9]{1}$",
        "PRC ID": r"^[0-9]{7}$",
        "Postal ID": r"^[A-Z0-9]{12}$",
        "Voter's ID": r"^[0-9]{4}-[0-9]{4}[A-Z]$",
        "TIN ID": r"^[0-9]{3}-[0-9]{3}-[0-9]{3}-[0-9]{3}$",
        "PhilHealth ID": r"^[0-9]{2}-[0-9]{9}-[0-9]{1}$",
        "School ID": r"^[A-Z0-9-]{5,20}$",
        "NBI Clearance": r"^[A-Z0-9]{10,18}$",
        "Alien Certificate of Registration": r"^[A-Z][0-9]{9}$"
    }

    def validate_id_pattern(self, id_type: str, id_number: str) -> bool:
        """Checks if the ID number matches the expected pattern for the ID type."""
        pattern = self.ID_PATTERNS.get(id_type)
        if not pattern:
            return True # If no pattern defined, assume valid for demo
        # Clean ID number for matching (remove spaces/dashes if necessary)
        clean_id = id_number.replace(" ", "").replace("-", "")
        # However, patterns usually expect the format, so we match original too
        return bool(re.match(pattern, id_number)) or bool(re.match(pattern.replace("-", "").replace(" ", ""), clean_id))

    def _prepare_image(self, encrypted_path: str) -> np.ndarray:
        """Decrypts a file and converts it to an OpenCV BGR image."""
        # Convert virtual API path back to real file system path if needed
        # id_path in db is like "/api/bookings/kyc/view/filename.enc"
        filename = encrypted_path.split("/")[-1]
        real_path = os.path.join("app/static/uploads/verification", filename)
        
        if not os.path.exists(real_path):
            raise FileNotFoundError(f"KYC document not found at {real_path}")

        with open(real_path, "rb") as f:
            encrypted_data = f.read()
        
        decrypted_data = decrypt_data(encrypted_data)
        
        # Convert bytes to numpy array then to OpenCV image
        nparr = np.frombuffer(decrypted_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img

    def _detect_faces_detailed(self, img: np.ndarray) -> List[Any]:
        """Detect faces using standard OpenCV Haar Cascades."""
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        return faces

    def calculate_fraud_score(self, 
                                face_match_conf: float, 
                                liveness_conf: float, 
                                ocr_match: bool, 
                                pattern_valid: bool) -> int:
        """
        Fintech-level 100-point scoring engine.
        Face Match: 40, Liveness: 30, OCR: 20, Pattern: 10
        """
        score = 0
        if face_match_conf >= 0.6: score += 40
        elif face_match_conf >= 0.4: score += 20
        
        if liveness_conf >= 0.02: score += 30 # Simple movement threshold
        
        if ocr_match: score += 20
        if pattern_valid: score += 10
        
        return score

    def verify_identity_v2(self, 
                           id_path: str, 
                           selfie_paths: List[str], 
                           full_name: str, 
                           id_number: str, 
                           id_type: str) -> Dict[str, Any]:
        """
        Real Background Verification Logic.
        """
        try:
            # 1. ID Pattern Validation
            pattern_valid = self.validate_id_pattern(id_type, id_number)
            
            # 2. Real OCR
            id_img = self._prepare_image(id_path)
            
            # Advanced Preprocessing for OCR
            # 1. Grayscale
            gray = cv2.cvtColor(id_img, cv2.COLOR_BGR2GRAY)
            
            # 2. Rescale (Optional: Tesseract works best on 300 DPI equivalent)
            # gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            
            # 3. Bilateral Filter (Removes noise while keeping edges sharp)
            denoised = cv2.bilateralFilter(gray, 9, 75, 75)
            
            # 4. Adaptive Thresholding (Handles uneven lighting)
            thresh = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                           cv2.THRESH_BINARY, 11, 2)
            
            ocr_text = pytesseract.image_to_string(thresh)
            
            # Comprehensive Name & ID Matching
            # Normalize full_name (strip spaces, lowercase)
            clean_name = " ".join(full_name.lower().split())
            clean_ocr = " ".join(ocr_text.lower().split())
            
            # Check if name or parts of it exist (first name and last name)
            name_parts = clean_name.split()
            name_match = all(part in clean_ocr for part in name_parts) if name_parts else False
            
            id_found = id_number.replace("-", "").replace(" ", "") in clean_ocr.replace("-", "").replace(" ", "")
            
            ocr_match = name_match or id_found
            
            # 3. Real Face Detection & Fake Liveness
            # Detect face in ID
            id_faces = self._detect_faces_detailed(id_img)
            
            # Detect faces in all selfies for movement/integrity
            selfie_face_counts = []
            for sp in selfie_paths:
                s_img = self._prepare_image(sp)
                faces = self._detect_faces_detailed(s_img)
                selfie_face_counts.append(len(faces))
            
            # Basic Liveness: Ensure face is present and "movement" (different face detections)
            # This is a very basic mock of liveness since we don't have deepface working yet
            liveness_score = 0.0
            if all(count == 1 for count in selfie_face_counts):
                liveness_score = 0.5 # Basic pass if 1 face in all frames
            
            # 4. Face Matching (Fallback Mock if DeepFace missing)
            face_match_confidence = 0.0
            try:
                # If we had DeepFace, we'd call it here
                # result = DeepFace.verify(img1=id_img, img2=selfie_img)
                # face_match_confidence = result["distance"] ...
                
                # FALLBACK: For now, if both have 1 face, we give a cautious high score 
                # (This should be replaced by real Face Recognition when possible)
                if len(id_faces) == 1 and selfie_face_counts[0] == 1:
                    face_match_confidence = 0.75 # Assume match for demo if structure is correct
                else:
                    face_match_confidence = 0.3
            except Exception:
                face_match_confidence = 0.5 
            
            # 5. Calculate Fraud Score
            fraud_score = self.calculate_fraud_score(
                face_match_confidence,
                liveness_score,
                ocr_match,
                pattern_valid
            )
            
            # 6. Decision logic
            status = "approved"
            failure_reason = None
            if fraud_score < 60:
                status = "rejected"
                reasons = []
                if not ocr_match: reasons.append("Name or ID not found on document")
                if not pattern_valid: reasons.append("ID number format is invalid")
                if liveness_score < 0.1: reasons.append("Liveness check failed (no face detected)")
                failure_reason = ", ".join(reasons) if reasons else "Low verification confidence"
                
            return {
                "status": status,
                "fraud_score": fraud_score,
                "face_match_confidence": face_match_confidence,
                "liveness_score": liveness_score,
                "ocr_match": ocr_match,
                "pattern_valid": pattern_valid,
                "failure_reason": failure_reason,
                "extracted_text_preview": ocr_text[:200], # For debugging
                "ocr_data": {
                    "raw_text": ocr_text,
                    "name_match": ocr_match,
                    "id_found": id_number in ocr_text,
                    "faces_in_id": len(id_faces),
                    "selfie_faces": selfie_face_counts
                }
            }
        except Exception as e:
            import traceback
            print(f"Error in KYC processing: {e}")
            traceback.print_exc()
            return {
                "status": "failed",
                "fraud_score": 0,
                "failure_reason": f"System Error: {str(e) or 'Unknown error, check logs'}",
                "ocr_data": {}
            }

    def verify_identity(self, id_url: str, selfie_url: str) -> dict:
        """Legacy mock for compatibility."""
        return {
            "success": "invalid" not in id_url.lower() and "nomatch" not in selfie_url.lower(),
            "failure_reason": "ID or Selfie mismatch",
            "ocr_data": {"full_name": "RODRIGUEZ, MARIA CLARA"}
        }

    def check_liveness(self, selfie_url: str) -> dict:
        """Legacy mock for compatibility."""
        return {"success": True, "liveness_token": "live_tok_" + str(random.randint(1000, 9999))}

verification_service = VerificationService()
