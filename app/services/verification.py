
import random
import time

class VerificationService:
    def verify_identity(self, document_url: str, selfie_url: str) -> dict:
        """
        Mocks the identity verification process.
        In a real scenario, this would call an external API like Stripe Identity, Onfido, etc.
        """
        # Simulate network delay
        time.sleep(1)

        # Mock logic: If document_url contains "fail", returns failure.
        if "fail" in document_url.lower():
            return {
                "success": False,
                "verification_status": "rejected",
                "failure_reason": "Document not legible or invalid."
            }
        
        # Mock logic: If selfie_url contains "fail", returns failure.
        if "fail" in selfie_url.lower():
            return {
                "success": False,
                "verification_status": "rejected",
                "failure_reason": "Face does not match ID photo."
            }

        # Success case
        return {
            "success": True,
            "verification_status": "verified",
            "ocr_data": {
                "full_name": "Mock User",
                "date_of_birth": "1990-01-01",
                "document_number": "A12345678"
            }
        }

verification_service = VerificationService()
