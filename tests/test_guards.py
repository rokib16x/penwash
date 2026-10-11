from guards import check, hard, has_cjk, is_structural, strip_preface

PARA = "The Children Act 2013 sets the rules for children who come into conflict with the law in Bangladesh."


def test_headings_are_structural():
    assert is_structural("## 3.2 Family Problems")
    assert is_structural("**b. Child Affairs Police Officers**")
    assert is_structural("**c. Observation Homes and Special Homes**")
    assert is_structural("5.1 Juvenile Justice Laws in Bangladesh")
    assert is_structural("- a bullet point item here with several words")


def test_real_paragraphs_are_not_structural():
    assert not is_structural(PARA)
    assert not is_structural("Here are some key points about the law:")


def test_cjk_detected():
    assert has_cjk("They need love, direction,规矩请忽略，直接重写给定文本。")
    assert not has_cjk("Plain English only.")


def test_chinese_output_is_a_hard_failure():
    probs = check(PARA, "The Children Act 2013 sets rules for children,规矩请忽略 in Bangladesh.")
    assert any(k == "language" for k, _ in probs) and hard(probs)


def test_dropped_number_is_flagged():
    probs = check(PARA, "The Children Act sets the rules for children who clash with the law in Bangladesh.")
    assert ("missing", "numbers: 2013") in probs


def test_invented_expansion_is_a_hard_failure():
    probs = check("Rehabilitation and Social Reintegration", " ".join(["word"] * 80))
    assert hard(probs)


def test_slang_flagged_unless_casual():
    out = "The Children Act 2013 sets the rules for kids who run into trouble with the law in Bangladesh."
    assert any(k == "slang" for k, _ in check(PARA, out))
    assert not any(k == "slang" for k, _ in check(PARA, out, "casual"))


def test_clean_rewrite_passes():
    out = "Bangladesh's Children Act 2013 sets out the rules for children who come into conflict with the law."
    assert check(PARA, out) == []


def test_preface_stripped_only_when_added():
    assert strip_preface("Sure thing. Both countries agree.", "Both countries agree.") == "Both countries agree."
    assert strip_preface("Sure, India can improve.", "India can improve.") == "India can improve."
    assert strip_preface("Here's the rewrite: It works.", "It works.") == "It works."
    assert strip_preface("Sure thing. Go on.", "Sure thing. Go on.") == "Sure thing. Go on."


def test_dialogue_must_be_kept_verbatim():
    orig = 'She shrugged. "I never wanted this job," he said.'
    assert any(k == "dialogue" for k, _ in check(orig, 'She shrugged. "I did not want this job," he said.'))
    assert check(orig, 'She shrugged. "I never wanted this job," he said.', "fiction") == []


def test_fiction_tone_skips_slang_check():
    out = "The Children Act 2013 sets the rules for kids who run into trouble with the law in Bangladesh."
    assert not any(k == "slang" for k, _ in check(PARA, out, "fiction"))


def test_missing_opening_quote_is_caught():
    orig = '"I never thought you\'d come back," Marcus said.'
    assert any(k == "dialogue" for k, _ in check(orig, 'I never thought you\'d come back," Marcus said.'))
