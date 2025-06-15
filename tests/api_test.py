import pytest
from django.test import RequestFactory
from Main.views import api, utils
import json

# テスト開始、レポート生成
# pytest tests/api_test.py --html=tests/report.html


@pytest.mark.django_db
class TestAPIUtils:
    def setup_method(self):
        self.factory = RequestFactory()

    # --- get_search_words ---
    def test_get_search_words_get(self):
        request = self.factory.get('/taskle/get_search_words')
        response = api.get_search_words(request)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'searchWords' in data
        assert isinstance(data['searchWords'], list)

    def test_get_search_words_post(self):
        request = self.factory.post('/taskle/get_search_words')
        response = api.get_search_words(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    # --- get_market_data ---
    def test_get_market_data_get_no_keyword(self):
        request = self.factory.get('/taskle/get_market_data')
        response = api.get_market_data(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    def test_get_market_data_post(self):
        request = self.factory.post('/taskle/get_market_data')
        response = api.get_market_data(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    # --- update_market_data ---
    def test_update_market_data_post_no_keyword(self):
        request = self.factory.post('/taskle/update_market_data')
        response = api.update_market_data(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    def test_update_market_data_get(self):
        request = self.factory.get('/taskle/update_market_data')
        response = api.update_market_data(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    # --- delete_market_data ---
    def test_delete_market_data_delete_no_keyword(self):
        request = self.factory.delete('/taskle/delete_market_data')
        response = api.delete_market_data(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    def test_delete_market_data_get(self):
        request = self.factory.get('/taskle/delete_market_data')
        response = api.delete_market_data(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    # --- complex_market_data ---
    def test_complex_market_data_post(self):
        request = self.factory.post('/taskle/complex_market_data')
        response = api.complex_market_data(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    def test_complex_market_data_get_no_keyword(self):
        request = self.factory.get('/taskle/complex_market_data')
        response = api.complex_market_data(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    # --- prediction_market ---
    def test_prediction_market_post(self):
        request = self.factory.post('/taskle/prediction_market')
        response = api.prediction_market(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    def test_prediction_market_get_no_keyword(self):
        request = self.factory.get('/taskle/prediction_market')
        response = api.prediction_market(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    # --- perform_search ---
    def test_perform_search_get_no_keyword(self):
        request = self.factory.get('/taskle/perform_search')
        response = api.perform_search(request)
        assert response.status_code == 400 or response.status_code == 200
        data = json.loads(response.content)
        assert 'error' in data or 'data' in data

    def test_perform_search_post(self):
        request = self.factory.post('/taskle/perform_search')
        response = api.perform_search(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    # --- RealtimeSearch ---
    def test_realtime_search_get_no_keyword(self):
        request = self.factory.get('/taskle/realtime_search')
        response = api.RealtimeSearch(request)
        assert response.status_code == 400 or response.status_code == 200
        data = json.loads(response.content)
        assert 'error' in data or 'data' in data

    def test_realtime_search_post(self):
        request = self.factory.post('/taskle/realtime_search')
        response = api.RealtimeSearch(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    # --- utils.get_search_words_logic ---
    def test_utils_get_search_words_logic_get(self):
        request = self.factory.get('/taskle/get_search_words')
        response = utils.get_search_words_logic(request)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'searchWords' in data

    def test_utils_get_search_words_logic_post(self):
        request = self.factory.post('/taskle/get_search_words')
        response = utils.get_search_words_logic(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    # --- utils.get_market_data_logic ---
    def test_utils_get_market_data_logic_no_keyword(self):
        request = self.factory.get('/taskle/get_market_data')
        response = utils.get_market_data_logic(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    def test_utils_get_market_data_logic_post(self):
        request = self.factory.post('/taskle/get_market_data')
        response = utils.get_market_data_logic(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    # --- utils.update_market_data_logic ---
    def test_utils_update_market_data_logic_get(self):
        request = self.factory.get('/taskle/update_market_data')
        response = utils.update_market_data_logic(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    # --- utils.delete_market_data_logic ---
    def test_utils_delete_market_data_logic_get(self):
        request = self.factory.get('/taskle/delete_market_data')
        response = utils.delete_market_data_logic(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    # --- utils.complex_market_data_logic ---
    def test_utils_complex_market_data_logic_post(self):
        request = self.factory.post('/taskle/complex_market_data')
        response = utils.complex_market_data_logic(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    # --- utils.prediction_market_logic ---
    def test_utils_prediction_market_logic_post(self):
        request = self.factory.post('/taskle/prediction_market')
        response = utils.prediction_market_logic(request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data
