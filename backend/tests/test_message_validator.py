from backend.app.runtime.message_validator import MessageValidator


def test_message_validator_accepts_observable_roleplay() -> None:
    result = MessageValidator().validate("她抬起火把，眯眼看向石门缝隙。")
    assert result.approved is True


def test_message_validator_rejects_mechanics_and_results() -> None:
    validator = MessageValidator()
    assert validator.validate("赛蕾妮进行调查检定，结果是 18。 ").approved is False
    assert validator.validate("赛蕾妮成功命中了守卫。").approved is False


def test_message_validator_allows_natural_personal_pronouns() -> None:
    result = MessageValidator().validate("我提醒你留意石门。")
    assert result.approved is True


def test_message_validator_allows_ordinary_counting() -> None:
    """Bare digits are not rule leakage; only digits next to rules terms are."""
    validator = MessageValidator()
    assert validator.validate("我数到三，你们就冲。").approved is True
    assert validator.validate("第2次了，别再让我提醒你。").approved is True
    assert validator.validate("三个人堵在门口，我数了数。").approved is True


def test_message_validator_still_rejects_latin_rules_tokens_after_cjk() -> None:
    """CJK counts as a word character, so \\b never fired on 个d20 or 难度DC15."""
    validator = MessageValidator()
    assert validator.validate("我掷了个d20。").approved is False
    assert validator.validate("难度DC15，我过不了。").approved is False


def test_message_validator_rejects_dashes() -> None:
    validator = MessageValidator()
    assert validator.validate("别误会——我只是不想浪费补给。").approved is False
    assert validator.validate("那条路两边是崖—出事跑都没地方跑。").approved is False
    assert validator.validate("等等--这个结构不对。").approved is False
    assert validator.validate("停了一下，“……别死在半路上。”").approved is True
