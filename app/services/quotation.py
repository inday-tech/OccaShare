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

        # Base calculation: price * guest_count
        base_amount = Decimal(str(package.price)) * Decimal(str(booking.guest_count))
        
        # Calculate add-ons from BookingMenuItem
        addons = []
        addon_total = Decimal("0.0")
        
        from ..db.models import BookingMenuItem, MenuItem
        booking_items = db.query(BookingMenuItem).join(MenuItem).filter(
            BookingMenuItem.booking_id == booking.id,
            BookingMenuItem.is_add_on == True
        ).all()

        for item in booking_items:
            price = Decimal(str(item.price))
            addons.append({
                "id": item.menu_item_id,
                "name": item.menu_item.name,
                "price": float(price)
            })
            addon_total += price

        total_amount = base_amount + addon_total
        
        # Ensure downpayment is within 30-50%
        if not (30 <= downpayment_percent <= 50):
            downpayment_percent = 30

        quotation = models.Quotation(
            booking_id=booking.id,
            package_details={
                "name": package.name,
                "description": package.description,
                "unit_price": float(package.price),
                "guest_count": booking.guest_count,
                "base_amount": float(base_amount)
            },
            addons=addons,
            total_amount=float(total_amount),
            downpayment_percent=downpayment_percent,
            status="draft"
        )
        
        db.add(quotation)
        db.flush() # Get ID
        
        # Update booking expiration (24h)
        booking.expires_at = datetime.now() + timedelta(hours=24)
        # Store high precision Decimal in reservation_fee
        booking.reservation_fee = total_amount * Decimal(str(downpayment_percent / 100))
        booking.total_amount = float(total_amount)
        
        db.commit()
        db.refresh(quotation)
        return quotation

    def get_quotation_by_booking(self, db: Session, booking_id: int) -> models.Quotation:
        return db.query(models.Quotation).filter(models.Quotation.booking_id == booking_id).first()

quotation_service = QuotationService()
