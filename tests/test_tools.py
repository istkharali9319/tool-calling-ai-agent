import re

import pytest

from app.tools import ToolError, calculator, date_tools, employee_tools, summary_tools, user_tools


class TestCalculator:
    def test_basic_operations(self):
        assert calculator.add(2, 3)["result"] == 5
        assert calculator.subtract(10, 4.5)["result"] == 5.5
        assert calculator.multiply(1250, 12)["result"] == 15000
        assert calculator.divide(10, 4)["result"] == 2.5

    def test_divide_by_zero(self):
        with pytest.raises(ToolError, match="Division by zero"):
            calculator.divide(1, 0)

    def test_overflow(self):
        with pytest.raises(ToolError, match="too large"):
            calculator.multiply(1e308, 1e308)


class TestUserTools:
    def test_get_user(self, db):
        assert user_tools.get_user(db, 1)["name"] == "Aarav Sharma"

    def test_get_user_missing(self, db):
        with pytest.raises(ToolError, match="No user found"):
            user_tools.get_user(db, 999)

    def test_get_all_users(self, db):
        result = user_tools.get_all_users(db)
        assert result["total"] == 6 and result["returned"] == 6 and not result["truncated"]

    def test_search_is_case_insensitive_and_partial(self, db):
        result = user_tools.search_user(db, "PRIYA")
        assert [u["name"] for u in result["users"]] == ["Priya Patel"]

    def test_search_escapes_wildcards(self, db):
        assert user_tools.search_user(db, "%")["count"] == 0


class TestEmployeeTools:
    def test_get_employee(self, db):
        employee = employee_tools.get_employee(db, 2)
        assert employee["name"] == "Vikram Singh"
        assert employee["hire_date"] == "2019-07-01"

    def test_get_employee_missing(self, db):
        with pytest.raises(ToolError):
            employee_tools.get_employee(db, 999)

    def test_search_and_list(self, db):
        assert employee_tools.search_employee(db, "neha")["count"] == 1
        assert employee_tools.get_all_employees(db)["total"] == 8


class TestDateTools:
    def test_current_date(self):
        result = date_tools.get_current_date()
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", result["date"])
        assert result["timezone"] == "UTC"

    def test_current_time_in_other_zone(self):
        result = date_tools.get_current_time("Asia/Kolkata")
        assert re.fullmatch(r"\d{2}:\d{2}:\d{2}", result["time"])
        assert result["iso_datetime"].endswith("+05:30")


class TestTextTools:
    def test_count_words(self):
        result = summary_tools.count_words("Hello world. It's a well-known test!")
        assert result["word_count"] == 6
        assert result["sentence_count"] == 2

    def test_short_text_is_returned_whole(self):
        assert summary_tools.summarize_text("One sentence.")["summary"] == "One sentence."

    def test_summary_keeps_key_sentences_in_order(self):
        text = (
            "Revenue grew strongly this quarter. Revenue growth came from new enterprise customers. "
            "The office plants were watered. Enterprise customers renewed at record rates. "
            "Lunch was pizza. Revenue from enterprise customers now leads the business."
        )
        result = summary_tools.summarize_text(text, max_sentences=3)
        assert result["summary_sentence_count"] == 3
        assert "plants" not in result["summary"] and "pizza" not in result["summary"]
        assert result["original_sentence_count"] == 6
