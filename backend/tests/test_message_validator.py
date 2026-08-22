from backend.app.runtime.message_validator import MessageValidator


def test_message_validator_accepts_observable_roleplay() -> None:
    result = MessageValidator().validate("她抬起火把，眯眼看向石门缝隙。")
    assert result.approved is True


def test_message_validator_rejects_mechanics_and_results() -> None:
    validator = MessageValidator()
    assert validator.validate("我进行调查检定，结果是 18。 ").approved is False
    assert validator.validate("我成功命中了守卫。").approved is False
