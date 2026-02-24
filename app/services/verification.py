import random
import time
import re
from typing import List, Dict, Any

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
        "School ID": r"^[A-Z0-9-]{5,20}$"
    }

    def validate_id_pattern(self, id_type: str, id_number: str) -> bool:
        """Checks if the ID number matches the expected pattern for the ID type."""
        pattern = self.ID_PATTERNS.get(id_type)
        if not pattern:
            return True # If no pattern defined, assume valid for demo
        return bool(re.match(pattern, id_number))

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
        Pro Background Verification Logic.
        """
        # 1. ID Pattern Validation
        pattern_valid = self.validate_id_pattern(id_type, id_number)
        
        # 2. Simulate OCR & Name Match
        # In real app, use Tesseract/Google Vision
        ocr_text = f"NAME: {full_name.upper()} ID: {id_number} TYPE: {id_type}"
        ocr_match = full_name.lower() in ocr_text.lower()
        
        # 3. Simulate Liveness (Movement between frames)
        # Using a mock movement score
        liveness_score = 0.05 if len(selfie_paths) >= 3 else 0.01
        
        # 4. Simulate Face Matching (ID vs Selfie 1)
        face_match_confidence = 0.85 # Mock high confidence
        if "nomatch" in id_path.lower(): face_match_confidence = 0.3
        
        # 5. Calculate Fraud Score
        fraud_score = self.calculate_fraud_score(
            face_match_confidence,
            liveness_score,
            ocr_match,
            pattern_valid
        )
        
        # 6. Decision logic (Real-time Priority)
        status = "approved"
        if fraud_score < 60:
            status = "rejected"
            
        # Removed "manual_review" for demo as requested (Real-time)
            
        return {
            "status": status,
            "fraud_score": fraud_score,
            "face_match_confidence": face_match_confidence,
            "liveness_score": liveness_score,
            "ocr_match": ocr_match,
            "pattern_valid": pattern_valid,
            "failure_reason": "Low fraud score" if status == "rejected" else None
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
