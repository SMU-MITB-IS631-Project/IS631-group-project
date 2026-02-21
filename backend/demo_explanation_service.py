"""
Demo Script: AI Explanation Engine (TDD Architecture)

This script demonstrates the DB-grounded explanation service.
Works WITHOUT OpenAI API key (uses intelligent template fallback).

Usage:
    1. Ensure backend database is seeded with cards
    2. Run: python backend/demo_explanation_service.py
    
What this demonstrates:
- Database ground truth extraction
- Bonus rate calculation from CardBonusCategory
- Template fallback when OpenAI unavailable
- Type-safe Pydantic schemas
- Production-ready error handling
"""

import os
import sys
from decimal import Decimal

# Add backend to Python path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.db import Base
from app.models.card_catalogue import CardCatalogue, BankEnum, BenefitTypeEnum, StatusEnum
from app.models.card_bonus_category import CardBonusCategory, BonusCategory
from app.models.user_profile import UserProfile  # Import to ensure table creation
from app.models.transaction import UserTransaction  # Import to ensure table creation
from app.models.user_owned_cards import UserOwnedCard  # Import to ensure table creation
from app.services.explanation_service import ExplanationService
from app.schemas.ai_schemas import ExplanationRequest


def create_test_database():
    """Create an in-memory database with sample card data"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Create DBS Live Fresh card
    dbs_card = CardCatalogue(
        card_id=101,
        bank=BankEnum.DBS,
        card_name="DBS Live Fresh",
        benefit_type=BenefitTypeEnum.CASHBACK,
        base_benefit_rate=Decimal("0.01"),  # 1% base
        status=StatusEnum.VALID
    )
    session.add(dbs_card)
    
    # Add Fashion bonus category
    fashion_bonus = CardBonusCategory(
        card_id=101,
        bonus_category=BonusCategory.Fashion,
        bonus_benefit_rate=Decimal("0.035"),  # 3.5% on Fashion
        bonus_cap_in_dollar=100,
        bonus_minimum_spend_in_dollar=0
    )
    session.add(fashion_bonus)
    
    # Add Food bonus category
    food_bonus = CardBonusCategory(
        card_id=101,
        bonus_category=BonusCategory.Food,
        bonus_benefit_rate=Decimal("0.05"),  # 5% on Food
        bonus_cap_in_dollar=50,
        bonus_minimum_spend_in_dollar=0
    )
    session.add(food_bonus)
    
    session.commit()
    return session


def demo_fashion_purchase():
    """Demo: Fashion purchase with bonus category"""
    print("\n" + "="*80)
    print("DEMO 1: Fashion Purchase (Bonus Category)")
    print("="*80)
    
    session = create_test_database()
    try:
        service = ExplanationService(session)
        
        # Build context from database
        print("\n📊 Building context from database...")
        context = service.build_context_from_db(
            card_id=101,
            category="Fashion",
            transaction_amount=Decimal("120.00"),
            merchant_name="ZARA"
        )
        
        print(f"   Card: {context.bank} {context.card_name}")
        print(f"   Category: {context.category}")
        print(f"   Base Rate: {float(context.base_rate * 100):.2f}%")
        print(f"   Bonus Rate: {f'{float(context.bonus_rate * 100):.2f}%' if context.bonus_rate else 'N/A'}")
        print(f"   Bonus Eligible: {context.is_bonus_eligible}")
        print(f"   Total Reward: SGD {float(context.total_reward_value) if context.total_reward_value else 0:.2f}")
        
        # Generate explanation
        print("\n💬 Generating explanation...")
        request = ExplanationRequest(recommendation=context)
        response = service.generate_explanation(request)
        
        print(f"\n✅ Explanation Generated:")
        print(f"   {response.explanation}")
        print(f"\n📋 Metadata:")
        print(f"   Model Used: {response.model_used}")
        print(f"   Is Fallback: {response.is_fallback}")
        print(f"   Generation Time: {response.generation_time_ms}ms")
    finally:
        session.close()


def demo_food_purchase():
    """Demo: Food purchase with 5% bonus and cap"""
    print("\n" + "="*80)
    print("DEMO 2: Food Purchase (High Bonus Rate + Cap)")
    print("="*80)
    
    session = create_test_database()
    service = ExplanationService(session)
    
    # Large purchase that will hit the cap
    print("\n📊 Building context from database...")
    context = service.build_context_from_db(
        card_id=101,
        category="Food",
        transaction_amount=Decimal("2000.00"),  # Would give $100 at 5%, but cap is $50
        merchant_name="FairPrice"
    )
    
    print(f"   Transaction: SGD {float(context.transaction_amount):.2f}")
    print(f"   Bonus Rate: {float(context.bonus_rate * 100) if context.bonus_rate else 0:.2f}%")
    print(f"   Uncapped Reward: SGD {float(context.transaction_amount * context.bonus_rate) if context.bonus_rate else 0:.2f}")
    print(f"   Cap: SGD {context.bonus_cap_sgd}")
    print(f"   Actual Reward (capped): SGD {float(context.total_reward_value) if context.total_reward_value else 0:.2f}")
    
    request = ExplanationRequest(recommendation=context)
    response = service.generate_explanation(request)
    
    print(f"\n💬 Explanation:\n   {response.explanation}")


def demo_no_bonus_category():
    """Demo: Transaction with no bonus (falls back to base rate)"""
    print("\n" + "="*80)
    print("DEMO 3: Bills Payment (No Bonus Category)")
    print("="*80)
    
    session = create_test_database()
    service = ExplanationService(session)
    
    context = service.build_context_from_db(
        card_id=101,
        category="Bills",  # No bonus for Bills
        transaction_amount=Decimal("150.00")
    )
    
    print(f"\n📊 Context:")
    print(f"   Category: {context.category}")
    print(f"   Bonus Eligible: {context.is_bonus_eligible}")
    print(f"   Applied Rate: {float(context.base_rate * 100):.2f}% (base rate)")
    print(f"   Reward: SGD {float(context.total_reward_value) if context.total_reward_value else 0:.2f}")
    
    request = ExplanationRequest(recommendation=context)
    response = service.generate_explanation(request)
    
    print(f"\n💬 Explanation:\n   {response.explanation}")


def demo_invalid_card():
    """Demo: Error handling for non-existent card"""
    print("\n" + "="*80)
    print("DEMO 4: Error Handling (Non-existent Card)")
    print("="*80)
    
    session = create_test_database()
    service = ExplanationService(session)
    
    try:
        context = service.build_context_from_db(
            card_id=999,  # Doesn't exist
            category="Fashion",
            transaction_amount=Decimal("100.00")
        )
    except ValueError as e:
        print(f"\n❌ Expected Error Caught:")
        print(f"   {str(e)}")
        print(f"\n✅ Error handling works correctly!")


def main():
    print("\n" + "🎯" * 40)
    print("AI EXPLANATION ENGINE - TDD ARCHITECTURE DEMO")
    print("🎯" * 40)
    
    print("\n💡 Note: This demo works WITHOUT OpenAI API key!")
    print("   The service uses intelligent template fallbacks.")
    
    # Run all demos
    demo_fashion_purchase()
    demo_food_purchase()
    demo_no_bonus_category()
    demo_invalid_card()
    
    print("\n" + "="*80)
    print("✨ DEMO COMPLETE - All systems operational!")
    print("="*80)
    print("\n📚 Next Steps:")
    print("   1. Set OPENAI_API_KEY in .env to enable AI-powered explanations")
    print("   2. Run tests: pytest backend/tests -v")
    print("   3. Start API: python backend/run.py")
    print("   4. Test endpoint: POST /api/v1/card-reasoner/explain-db")
    print("\n")


if __name__ == "__main__":
    main()
