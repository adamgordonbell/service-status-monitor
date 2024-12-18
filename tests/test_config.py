import pytest
import toml
from scripts.app_server import load_urls_from_toml  # Updated import path

def test_load_urls_from_toml(tmp_path):
    # Create a temporary TOML file
    toml_content = """
    [services]
    test1 = "https://example.com/status1"
    test2 = "https://example.com/status2"
    """
    toml_file = tmp_path / "test_urls_config.toml"
    toml_file.write_text(toml_content)

    # Load URLs from the temporary TOML file
    urls = load_urls_from_toml(toml_file)

    # Assertions
    assert "test1" in urls
    assert "test2" in urls
    assert urls["test1"] == "https://example.com/status1"
    assert urls["test2"] == "https://example.com/status2"
