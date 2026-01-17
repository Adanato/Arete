import re

def test_regex():
    p1 = re.compile(r"^\s*[\"\']?anki_template_version[\"\']?:\s*1\s*$", re.MULTILINE)
    p2 = re.compile(r"^\s*[\"\']?anki_template_version[\"\']?:\s*['\"]1['\"]\s*$", re.MULTILINE)

    cases = [
        "anki_template_version: 1",
        "anki_template_version: 1 ",
        "anki_template_version: '1'",
        "'anki_template_version': 1",
        " anki_template_version: 1",  # Leading space (should fail with current regex)
        "anki_template_version:  1",
        "anki_template_version:1",
    ]

    print("Testing Regex Matches:")
    for case in cases:
        match1 = p1.search(case)
        match2 = p2.search(case)
        print(f"'{case}': Match1={bool(match1)}, Match2={bool(match2)}")

if __name__ == "__main__":
    test_regex()
