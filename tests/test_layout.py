from datetime import date

from profilecard.layout import W, age, info_lines, kv, kv2, rule


def text_of(segments):
    return "".join(t for t, _ in segments)


# The three cases that used to live in update_profile.selfcheck().
def test_age_month_precision():
    assert age(date(2012, 8, 1), date(2026, 9, 3)) == (14, 1)


def test_age_borrows_a_year_when_months_go_negative():
    assert age(date(2000, 3, 1), date(2026, 1, 1)) == (25, 10)


def test_age_exact_year_boundary():
    assert age(date(2000, 1, 1), date(2026, 1, 1)) == (26, 0)


def test_age_ignores_day_of_month():
    assert age(date(2012, 8, 31), date(2026, 9, 1)) == age(date(2012, 8, 1), date(2026, 9, 28))


def test_kv_row_is_exactly_the_column_width():
    assert len(text_of(kv("OS", "macOS"))) == W


def test_kv_keeps_one_dot_when_content_overflows():
    row = kv("k" * 40, "v" * 40)
    assert text_of(row) == "k" * 40 + ": " + ". " + "v" * 40
    assert len(text_of(row)) > W  # overflow widens the row rather than truncating


def test_kv_segments_carry_key_dots_value_colours():
    assert [c for _, c in kv("OS", "macOS")] == ["k", "d", "v"]


def test_kv2_uses_30_and_23_char_columns():
    row = kv2("Repos", "45", "Stars", "789")
    left, sep, right = row[:3], row[3], row[4:]
    assert len(text_of(left)) == 30
    assert text_of([sep]) == " | "
    assert len(text_of(right)) == 23


def test_rule_with_title_is_full_width():
    row = rule("Contact")
    assert text_of(row) == "─ Contact " + "─" * (W - len("─ Contact "))
    assert [c for _, c in row] == ["h", "d"]


def test_rule_without_title_is_all_dashes():
    assert text_of(rule()) == "─" * W


def test_info_lines_header_and_blank_separators(stats, profile):
    lines = info_lines(stats, profile, today=date(2026, 9, 3))
    assert text_of(lines[0]).startswith("glrodasz@github ")
    assert lines[1] == []  # blank rows are dropped by render()


def test_info_lines_reads_every_field_from_the_profile(stats, profile):
    rendered = "\n".join(text_of(line) for line in info_lines(stats, profile, today=date(2026, 9, 3)))
    for value in (profile.os, profile.host, profile.kernel, profile.ide, profile.hobbies,
                  profile.languages_programming, profile.languages_spoken,
                  profile.email, profile.linkedin):
        assert value in rendered
    assert "14 years, 1 months" in rendered


def test_info_lines_formats_numbers_with_thousands_separators(stats, profile):
    rendered = "\n".join(text_of(line) for line in info_lines(stats, profile, today=date(2026, 9, 3)))
    assert "654,321" in rendered and "900,000++" in rendered and "245,679--" in rendered
    assert "45 {Contributed: 6}" in rendered
