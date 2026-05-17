import json
import os
import pytest

from src.config_loader import lakehouse_table, lakehouse_name


SAMPLE_CONFIG = {
    "environment": "TEST",
    "workspace": "UNIV-TEST",
    "bronze_lakehouse": "Bronze_Lakehouse",
    "silver_lakehouse": "Silver_Lakehouse",
    "gold_lakehouse": "Gold_Lakehouse",
    "lakehouses": {
        "bronze": "Bronze_Lakehouse",
        "silver": "Silver_Lakehouse",
        "gold": "Gold_Lakehouse",
    },
}


class TestConfigHelpers:

    def test_lakehouse_table(self):
        result = lakehouse_table(SAMPLE_CONFIG, "bronze", "my_table")
        assert result == "Bronze_Lakehouse.my_table"

    def test_lakehouse_table_silver(self):
        result = lakehouse_table(SAMPLE_CONFIG, "silver", "silver_entity")
        assert result == "Silver_Lakehouse.silver_entity"

    def test_lakehouse_name(self):
        assert lakehouse_name(SAMPLE_CONFIG, "bronze") == "Bronze_Lakehouse"
        assert lakehouse_name(SAMPLE_CONFIG, "silver") == "Silver_Lakehouse"
        assert lakehouse_name(SAMPLE_CONFIG, "gold") == "Gold_Lakehouse"

    def test_lakehouse_table_missing_layer(self):
        with pytest.raises(KeyError):
            lakehouse_table(SAMPLE_CONFIG, "nonexistent", "t")

    def test_lakehouse_name_missing_layer(self):
        with pytest.raises(KeyError):
            lakehouse_name(SAMPLE_CONFIG, "nonexistent")
