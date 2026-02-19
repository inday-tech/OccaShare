from sqlalchemy.orm import Session
from ..db import models
from decimal import Decimal
from datetime import datetime, timedelta

class QuotationService:
    def create_quotation(self, db: Session, booking: models.Booking, downpayment_percent: int = 30) -> models.Quotation:
        """
        Calculates total cost and creates a Quotation record for a booking.
        """
        package = booking.package
        if not package:
            raise ValueError("Booking must have a package to generate a quotation.")

        # Basic calculation: price * guest_count
        # Note: price is Float in models, we'll convert to Decimal for accuracy if needed, 
        # but here we'll follow the model types.
        total_amount = Decimal(str(package.price)) * Decimal(str(booking.guest_count))
        
        # In a real app, you'd add add-ons here.
        addons = [] 
        
        # Ensure downpayment is within 30-50%
        if not (30 <= downpayment_percent <= 50):
            downpayment_percent = 30

        quotation = models.Quotation(
            booking_id=booking.id,
            package_details={
                "name": package.name,
                "description": package.description,
                "unit_price": package.price,
                "guest_count": booking.guest_count
            },
            addons=addons,
            total_amount=total_amount,
            downpayment_percent=downpayment_percent,
            status="draft"
        )
        
        db.add(quotation)
        db.flush() # Get ID
        
        # Update booking expiration (24h)
        booking.expires_at = datetime.now() + timedelta(hours=24)
        booking.reservation_fee = total_amount * Decimal(str(downpayment_percent / 100))
        
        db.commit()
        db.refresh(quotation)
        return quotation

    def get_quotation_by_booking(self, db: Session, booking_id: int) -> models.Quotation:
        return db.query(models.Quotation).filter(models.Quotation.booking_id == booking_id).first()

quotation_service = QuotationService()
