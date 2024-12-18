import unittest
from scripts.app_server import app

class TestFlaskApp(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_home_status_code(self):
        """Test that the home page loads successfully"""
        result = self.app.get('/')
        self.assertEqual(result.status_code, 200)

    def test_status_endpoint(self):
        """Test that the status endpoint returns JSON"""
        result = self.app.get('/status')
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)

    def test_packet_stats_endpoint(self):
        """Test that the packet stats endpoint returns JSON"""
        result = self.app.get('/packet-stats')
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)

if __name__ == '__main__':
    unittest.main()
