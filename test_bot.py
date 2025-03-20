import pytest
import asyncio
from bot import ApiClient  # Убедитесь, что имя файла соответствует

@pytest.mark.asyncio
async def test_get_weather():
    result = await ApiClient.get_weather("Minsk,BY")
    assert isinstance(result, str)
    assert "°C" in result or "Нет данных" in result

@pytest.mark.asyncio
async def test_get_currency_rates():
    usd_byn, usd_rub = await ApiClient.get_currency_rates()
    assert isinstance(usd_byn, (float, int))
    assert isinstance(usd_rub, (float, int))
