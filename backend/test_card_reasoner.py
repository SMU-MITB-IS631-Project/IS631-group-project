"""
Test script for card_reasoner_service.
Run this to validate the service works end-to-end.

Usage:
    python backend/test_card_reasoner.py
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.services.card_reasoner_service import (
    ExplanationRequest,
    TransactionInput,
    CardDetail,
    BenefitTypeEnum,
    generate_explanation
)

# Test data - Singapore shopping scenario
test_request = ExplanationRequest(
    transaction=TransactionInput(
        merchant_name="ZARA",
        amount=120.00,
        category="Fashion"
    ),
    recommended_card=CardDetail(
        Card_ID=3,
        Bank="DBS",
        Card_Name="DBS Live Fresh",
        Benefit_type=BenefitTypeEnum.CASHBACK,
        base_benefit_rate=0.01,
        applied_bonus_rate=0.035,
        total_calculated_value=4.32
    ),
    comparison_cards=[
        CardDetail(
            Card_ID=5,
            Bank="OCBC",
            Card_Name="OCBC 365",
            Benefit_type=BenefitTypeEnum.CASHBACK,
            base_benefit_rate=0.005,
            applied_bonus_rate=0.03,
            total_calculated_value=4.20
        )
    ]
)


def test_generate_explanation_smoke():
    """Smoke test: service returns a shaped response for a valid request."""
    response = generate_explanation(test_request)
    assert response.explanation
    assert response.audit_log_entry.recommended_card_id == test_request.recommended_card.Card_ID

def main():
    print("=" * 80)
    print("CARD REASONER SERVICE TEST")
    print("=" * 80)
    
    print("\n📝 Input Request:")
    print(f"   Merchant: {test_request.transaction.merchant_name}")
    print(f"   Amount: SGD {test_request.transaction.amount:.2f}")
    print(f"   Category: {test_request.transaction.category}")
    print(f"   Recommended: {test_request.recommended_card.Bank} {test_request.recommended_card.Card_Name}")
    print(f"   Comparisons: {len(test_request.comparison_cards)}")
    
    print("\n🔄 Generating explanation...")
    try:
        response = generate_explanation(test_request)
        
        print("\n✅ SUCCESS!")
        print("\n📢 Explanation Generated:")
        print(f"   {response.explanation}")
        
        print("\n📊 Audit Log:")
        print(f"   Event Type: {response.audit_log_entry.event_type}")
        print(f"   Model: {response.audit_log_entry.model_used}")
        print(f"   Timestamp: {response.audit_log_entry.timestamp}")
        print(f"   Merchant: {response.audit_log_entry.merchant_name}")
        print(f"   Card: {response.audit_log_entry.recommended_card_name}")
        print(f"   Comparisons Analyzed: {response.audit_log_entry.num_comparisons}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\n💡 Troubleshooting:")
        print("   1. Check OPENAI_API_KEY env variable is set")
        print("   2. Verify OpenAI account has credits")
        print("   3. Note: If OpenAI unavailable, fallback explanation is used")
        return 1
    
    print("\n" + "=" * 80)
    print("✨ Service is working correctly!")
    print("=" * 80)
    return 0

if __name__ == "__main__":
    sys.exit(main())
