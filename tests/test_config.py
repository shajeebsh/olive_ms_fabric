import json
import os
import pytest

CONFIG_DIR = "config"

def test_config_files_valid_json():
    """
    Ensure all config files are valid JSON.
    """
    config_files = [f for f in os.listdir(CONFIG_DIR) if f.endswith(".json")]
    for file_name in config_files:
        with open(os.path.join(CONFIG_DIR, file_name), 'r') as f:
            try:
                json.load(f)
            except json.JSONDecodeError:
                pytest.fail(f"{file_name} is not a valid JSON file")

def test_config_keys_consistency():
    """
    Ensure all environment configs have the same required keys.
    """
    required_keys = {"environment", "workspace", "bronze_lakehouse", "silver_lakehouse", "gold_lakehouse", "lakehouses"}
    
    config_files = ["config_dev.json", "config_prod.json", "config_test.json"]
    
    for file_name in config_files:
        path = os.path.join(CONFIG_DIR, file_name)
        if not os.path.exists(path):
            continue
            
        with open(path, 'r') as f:
            config = json.load(f)
            missing_keys = required_keys - set(config.keys())
            assert not missing_keys, f"{file_name} is missing keys: {missing_keys}"
