"""
PRACTICE 03: Structured Output (Pydantic)
==========================================

Topic: Section 7 from THEORY.md
Level: Intermediate → Advanced

What you'll learn:
- Pydantic BaseModel for schemas
- with_structured_output() method
- Type-safe responses (no parsing!)
- Real-world extraction patterns
"""

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field

load_dotenv()

# Initialize model
model = init_chat_model("groq:llama-3.3-70b-versatile")


# ===== BASIC: Simple Schema =====

class PersonInfo(BaseModel):
    """Information about a person."""
    name: str = Field(description="Full name")
    age: int = Field(description="Age in years")
    profession: str = Field(description="Their job/profession")


def basic_extraction():
    """Extract structured person info."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Basic Structured Output")
    print("=" * 70)

    structured_model = model.with_structured_output(PersonInfo)
    result = structured_model.invoke("Tell me about APJ Abdul Kalam")

    print(f"\nType: {type(result).__name__}")
    print(f"Name: {result.name}")
    print(f"Age: {result.age}")
    print(f"Profession: {result.profession}")


# ===== INTERMEDIATE: Complex Schema =====

class JobApplication(BaseModel):
    """Job application data."""
    candidate_name: str = Field(description="Candidate's full name")
    email: str = Field(description="Email address")
    skills: list[str] = Field(description="List of top skills")
    experience_years: int = Field(description="Years of experience")
    expected_salary_lpa: float = Field(description="Expected salary in LPA")
    notice_period_days: int = Field(description="Notice period in days")
    is_remote: bool = Field(description="Available for remote work?")


def extract_job_application():
    """Extract job application from text."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Job Application Extraction")
    print("=" * 70)

    structured_model = model.with_structured_output(JobApplication)

    text = """
    Hi, I'm Ashish Kumar. My email is ashish@example.com.
    I'm a backend developer with 4.3 years of experience.
    My top skills are Python, FastAPI, PostgreSQL, and Docker.
    I expect 25 LPA salary and have 60 days notice period.
    I'm available for remote work.
    """

    result = structured_model.invoke(f"Extract job application details: {text}")

    print(f"\nName: {result.candidate_name}")
    print(f"Email: {result.email}")
    print(f"Skills: {result.skills}")
    print(f"Experience: {result.experience_years} years")
    print(f"Expected Salary: ₹{result.expected_salary_lpa} LPA")
    print(f"Notice Period: {result.notice_period_days} days")
    print(f"Remote: {result.is_remote}")


# ===== ADVANCED: Nested Schema =====

class Address(BaseModel):
    street: str = Field(description="Street address")
    city: str = Field(description="City name")
    state: str = Field(description="State name")
    pincode: str = Field(description="Pincode")


class Order(BaseModel):
    """E-commerce order schema."""
    order_id: str = Field(description="Order ID")
    customer_name: str = Field(description="Customer name")
    items: list[str] = Field(description="Items ordered")
    total_amount: float = Field(description="Total amount in rupees")
    shipping_address: Address = Field(description="Shipping address")
    is_paid: bool = Field(description="Is payment done?")


def extract_order():
    """Extract complex nested order data."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Nested Schema (Order Extraction)")
    print("=" * 70)

    structured_model = model.with_structured_output(Order)

    text = """
    Order #ORD-12345 was placed by Priya Sharma.
    She ordered: Wireless Headphones, USB Cable, Phone Case.
    Total amount: ₹5499.
    Shipping to: 123 MG Road, Bangalore, Karnataka, 560001.
    Payment status: Completed (paid).
    """

    result = structured_model.invoke(f"Extract order details: {text}")

    print(f"\nOrder ID: {result.order_id}")
    print(f"Customer: {result.customer_name}")
    print(f"Items: {result.items}")
    print(f"Total: ₹{result.total_amount}")
    print(f"Address: {result.shipping_address.street}, "
          f"{result.shipping_address.city}, "
          f"{result.shipping_address.state} - "
          f"{result.shipping_address.pincode}")
    print(f"Paid: {result.is_paid}")


# ===== EXPERT: Database-Ready Extraction =====

class UserProfile(BaseModel):
    """User profile for database insertion."""
    full_name: str = Field(description="User's full name")
    email: str = Field(description="Email address")
    phone: str = Field(description="Phone number")
    age: int = Field(description="Age in years")
    interests: list[str] = Field(description="User's interests")


def database_ready_extraction():
    """Extract data ready for database insertion."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Database-Ready Data Extraction")
    print("=" * 70)

    structured_model = model.with_structured_output(UserProfile)

    user_text = """
    Hi! I'm Rahul Verma, 28 years old.
    You can reach me at rahul@gmail.com or +91-9876543210.
    I love coding, reading books, and playing chess.
    """

    profile = structured_model.invoke(f"Extract user profile: {user_text}")

    print(f"\nProfile extracted (ready for DB):")
    print(profile.model_dump())  # Direct dict for DB insert!

    # Simulate database insert
    print(f"\n💾 INSERT INTO users (name, email, phone, age, interests)")
    print(f"   VALUES ('{profile.full_name}', '{profile.email}', "
          f"'{profile.phone}', {profile.age}, '{profile.interests}')")


def main():
    """Run all examples."""
    basic_extraction()
    extract_job_application()
    extract_order()
    database_ready_extraction()


if __name__ == "__main__":
    main()
