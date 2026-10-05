from apps.core.exceptions import BusinessRuleError, exception_handler


def test_business_rule_error_becomes_400_with_code():
    response = exception_handler(BusinessRuleError("insufficient_stock", "Only 3 left."), {})

    assert response.status_code == 400
    assert response.data == {"code": "insufficient_stock", "detail": "Only 3 left."}
