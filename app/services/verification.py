
import random
import time

class VerificationService:
    def verify_identity(self, id_url: str, selfie_url: str) -> dict:
        """
        Mocks the identity verification process.
        """
        # Simulate network delay
        time.sleep(1)

        # Mock logic: If id_url contains "invalid", returns failure.
        if "invalid" in id_url.lower():
            return {
                "success": False,
                "verification_status": "rejected",
                "failure_reason": "Document is invalid, expired, or not supported."
            }
        
        # Mock logic: If selfie_url contains "nomatch", returns failure.
        if "nomatch" in selfie_url.lower():
            return {
                "success": False,
                "verification_status": "rejected",
                "failure_reason": "Selfie does not match the photo on the identity document."
            }

        # Success case
        return {
            "success": True,
            "verification_status": "verified",
            "ocr_data": {
                "full_name": "RODRIGUEZ, MARIA CLARA",
                "date_of_birth": "1992-05-15",
                "document_number": "N01-92-123456",
                "document_type": "Unified Multi-Purpose ID (UMID)",
                "nationality": "Filipino",
                "address": "123 Balagtas St, Makati City, 1200"
            }
        }

    def check_liveness(self, selfie_url: str) -> dict:
        """
        Mocks a liveness check.
        """
        if "blur" in selfie_url.lower():
            return {"success": False, "reason": "Selfie too blurry for liveness detection."}
        return {"success": True, "liveness_token": "live_tok_" + str(random.randint(1000, 9999))}

verification_service = VerificationService()
