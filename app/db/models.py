from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Boolean, Date, Time, DECIMAL, ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default="customer") # 'admin', 'caterer', 'customer'
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    profile_image_url = Column(String, nullable=True)
    status = Column(String, default="active")
    is_verified = Column(Boolean, default=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Social Login Fields
    facebook_id = Column(String, unique=True, nullable=True)
    instagram_id = Column(String, unique=True, nullable=True)
    auth_provider = Column(String, default='email') # 'email', 'facebook', 'instagram'
    
    # Email Verification
    is_email_verified = Column(Boolean, default=False)
    verification_code = Column(String, nullable=True) # OTP
    otp_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Password Reset Fields
    reset_token = Column(String, unique=True, nullable=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_kyc_complete = Column(Boolean, default=False)

    caterer_profile = relationship("CatererProfile", back_populates="user", uselist=False)
    bookings = relationship("Booking", back_populates="user")
    reviews = relationship("Review", back_populates="user")
    inquiries = relationship("Inquiry", back_populates="user")
    identity_verification = relationship("IdentityVerification", back_populates="user", uselist=False)
    notifications = relationship("Notification", back_populates="user")
    verification_attempts = relationship("VerificationAttempt", back_populates="user")

class CatererProfile(Base):
    __tablename__ = "caterer_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    business_name = Column(String)
    slug = Column(String, unique=True, nullable=True)
    business_type = Column(String, nullable=True)
    years_of_operation = Column(Integer, default=0)
    description = Column(Text)
    logo_url = Column(String)
    cover_image_url = Column(String)
    contact_phone = Column(String)
    contact_address = Column(Text)
    city = Column(String)
    coverage_area = Column(Text, nullable=True)
    cuisine_types = Column(ARRAY(String)) # Requires PostgreSQL
    event_types = Column(ARRAY(String)) # Supported events like Wedding, Birthday, etc.
    rating = Column(Float, default=0.0)
    review_count = Column(Integer, default=0)
    payout_method = Column(String, nullable=True) # Bank, GCash
    payout_account_name = Column(String, nullable=True)
    payout_account_number = Column(String, nullable=True)
    verification_status = Column(String, default='Pending') # Pending, Verified, Rejected
    is_verified = Column(Boolean, default=False)
    
    # NEW: Refined Registration Fields
    min_pax = Column(Integer, default=0)
    starting_price = Column(Float, default=0.0)
    sample_menu_url = Column(String, nullable=True)
    permit_url = Column(String, nullable=True)
    gov_id_url = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="caterer_profile")
    packages = relationship("CateringPackage", back_populates="caterer")
    gallery_items = relationship("CatererGallery", back_populates="caterer")
    bookings = relationship("Booking", back_populates="caterer")
    reviews = relationship("Review", back_populates="caterer")
    promotions = relationship("Promotion", back_populates="caterer")
    availability = relationship("Availability", back_populates="caterer")
    inquiries = relationship("Inquiry", back_populates="caterer")

class CateringPackage(Base):
    __tablename__ = "catering_packages"

    id = Column(Integer, primary_key=True, index=True)
    caterer_id = Column(Integer, ForeignKey("caterer_profiles.id"))
    name = Column(String, index=True)
    description = Column(Text)
    price = Column(Float)
    price_unit = Column(String, default='per_guest')
    min_guests = Column(Integer, default=10)
    max_guests = Column(Integer, nullable=True)
    image_url = Column(String)
    service_type = Column(String, default="General") # Wedding, Birthday, Corporate, etc.
    
    # NEW: Rich Pricing & Details
    price_per_head = Column(Float, nullable=True)
    min_contract_amount = Column(Float, nullable=True)
    additional_guest_price = Column(Float, nullable=True)
    service_duration = Column(Integer, default=4) # In hours
    overtime_fee = Column(Float, default=0.0)
    location_coverage = Column(String, nullable=True) # City / Area
    
    # Structured Data
    inclusions = Column(JSONB, nullable=True) # Checklist fields
    policies = Column(JSONB, nullable=True) # Cancellation, Payment terms, etc.
    
    is_active = Column(Boolean, default=True)
    status = Column(String, default="active") # active, inactive, draft
    is_featured = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    caterer = relationship("CatererProfile", back_populates="packages")
    menu_items = relationship("MenuItem", back_populates="package", cascade="all, delete-orphan")

    bookings = relationship("Booking", back_populates="package")

class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True, index=True)
    package_id = Column(Integer, ForeignKey("catering_packages.id"))
    name = Column(String)
    description = Column(Text, nullable=True)
    category = Column(String) # Starter, Soup, Salad, Main Dish (Beef), etc.
    
    # Dietary & Allergen Info
    dietary_tags = Column(ARRAY(String), nullable=True) # Vegetarian, Vegan, Halal
    allergen_info = Column(ARRAY(String), nullable=True) # Nuts, Dairy, Seafood
    
    serving_size = Column(String, nullable=True) # "Good for 1", "Per tray"
    is_addon = Column(Boolean, default=False)
    addon_price = Column(Float, default=0.0)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    package = relationship("CateringPackage", back_populates="menu_items")


class CatererGallery(Base):
    __tablename__ = "caterer_gallery"

    id = Column(Integer, primary_key=True, index=True)
    caterer_id = Column(Integer, ForeignKey("caterer_profiles.id"))
    media_url = Column(String)
    media_type = Column(String, default="image")
    caption = Column(String, nullable=True)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    caterer = relationship("CatererProfile", back_populates="gallery_items")

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    caterer_id = Column(Integer, ForeignKey("caterer_profiles.id"))
    package_id = Column(Integer, ForeignKey("catering_packages.id"), nullable=True)
    event_name = Column(String, nullable=True) # e.g. "Garcia Family Wedding"
    event_type = Column(String, nullable=True) # Wedding, Birthday, Corporate, Private Party
    event_date = Column(Date)
    event_time = Column(Time, nullable=True)
    venue_address = Column(Text, nullable=True)
    guest_count = Column(Integer)
    total_amount = Column(Float)
    total_price = Column(Float, nullable=True) # Alias to match user request structure
    reservation_fee = Column(DECIMAL, nullable=True)
    status = Column(String, default="pending")
    payment_status = Column(String, default="pending") # pending, paid, deposit_paid
    payment_method = Column(String, nullable=True) # GCash, Credit Card, etc.
    payment_reference = Column(String, nullable=True)
    payment_proof_url = Column(String, nullable=True)
    ocr_verification = relationship("OCRVerification", back_populates="booking", uselist=False)

    ocr_verified = Column(Boolean, default=False)
    liveness_verified = Column(Boolean, default=False)
    special_requests = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    expires_at = Column(DateTime(timezone=True), nullable=True)
    reservation_fee = Column(DECIMAL, nullable=True)
    event_location = Column(Text, nullable=True) # Alias for venue_address

    user = relationship("User", back_populates="bookings")
    caterer = relationship("CatererProfile", back_populates="bookings")
    package = relationship("CateringPackage", back_populates="bookings")
    review = relationship("Review", back_populates="booking", uselist=False)
    history = relationship("BookingHistory", back_populates="booking")
    quotation = relationship("Quotation", back_populates="booking", uselist=False)
    verification_attempts = relationship("VerificationAttempt", back_populates="booking")
    fraud_flags = relationship("FraudFlag", back_populates="booking")
    selected_items = relationship("BookingMenuItem", back_populates="booking", cascade="all, delete-orphan")

class BookingMenuItem(Base):
    __tablename__ = "booking_menu_items"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"))
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"))
    is_add_on = Column(Boolean, default=False)
    price = Column(Float) # Price at the time of booking

    booking = relationship("Booking", back_populates="selected_items")
    menu_item = relationship("MenuItem")

class BookingHistory(Base):
    __tablename__ = "booking_history"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"))
    status = Column(String) # The status being transitioned TO
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    booking = relationship("Booking", back_populates="history")

class OCRVerification(Base):
    __tablename__ = "ocr_verification"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True) # Can be linked to booking or user
    user_id = Column(Integer, ForeignKey("users.id"))
    document_url = Column(String)
    selfie_url = Column(String)
    status = Column(String, default="pending") # pending, verified, failed
    ocr_data = Column(JSONB)
    match_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    booking = relationship("Booking", back_populates="ocr_verification")
    user = relationship("User")

class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), unique=True, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    caterer_id = Column(Integer, ForeignKey("caterer_profiles.id"))
    rating = Column(Integer)
    comment = Column(Text)
    recommend = Column(Boolean, default=False)
    was_punctual = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    booking = relationship("Booking", back_populates="review")
    user = relationship("User", back_populates="reviews")
    caterer = relationship("CatererProfile", back_populates="reviews")

class Promotion(Base):
    __tablename__ = "promotions"

    id = Column(Integer, primary_key=True, index=True)
    caterer_id = Column(Integer, ForeignKey("caterer_profiles.id"))
    title = Column(String)
    description = Column(Text)
    discount_type = Column(String, default="percentage")
    discount_value = Column(Float)
    start_date = Column(Date)
    end_date = Column(Date)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    caterer = relationship("CatererProfile", back_populates="promotions")

class Availability(Base):
    __tablename__ = "availability"

    id = Column(Integer, primary_key=True, index=True)
    caterer_id = Column(Integer, ForeignKey("caterer_profiles.id"))
    date = Column(Date)
    is_available = Column(Boolean, default=False) # False means blocked
    reason = Column(String, nullable=True)

    caterer = relationship("CatererProfile", back_populates="availability")

class Inquiry(Base):
    __tablename__ = "inquiries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    caterer_id = Column(Integer, ForeignKey("caterer_profiles.id"), nullable=True)
    name = Column(String)
    email = Column(String)
    message = Column(Text)
    status = Column(String, default="new")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="inquiries")
    caterer = relationship("CatererProfile", back_populates="inquiries")

class IdentityVerification(Base):
    __tablename__ = "identity_verifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    verification_type = Column(String, default='government_id')
    document_url = Column(String, nullable=False)
    selfie_url = Column(String, nullable=False)
    ocr_data = Column(JSONB)
    verification_status = Column(String, default='pending') # pending, verified, rejected
    failure_reason = Column(Text, nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="identity_verification")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String)
    message = Column(Text)
    type = Column(String, default="info") # info, success, warning, reminder
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

class VerificationAttempt(Base):
    __tablename__ = "verification_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    booking_id = Column(Integer, ForeignKey("bookings.id"))
    step = Column(String(20), nullable=False) # 'upload', 'ocr', 'liveness', 'match'
    status = Column(String(20), nullable=False) # pending/verified/failed
    details = Column(JSONB) # raw OCR data or error codes
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="verification_attempts")
    booking = relationship("Booking", back_populates="verification_attempts")

class Quotation(Base):
    __tablename__ = "quotations"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), unique=True)
    package_details = Column(JSONB)
    addons = Column(JSONB)
    total_amount = Column(DECIMAL)
    downpayment_percent = Column(Integer) # CHECK (downpayment_percent BETWEEN 30 AND 50) - handle in app logic or custom CheckConstraint
    contract_url = Column(String) # signed PDF
    status = Column(String(20), default='draft') # draft, sent, signed
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    booking = relationship("Booking", back_populates="quotation")

class FraudFlag(Base):
    __tablename__ = "fraud_flags"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"))
    flag_type = Column(String(50)) # 'multiple_ids','high_risk_location'…
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    booking = relationship("Booking", back_populates="fraud_flags")
