"""Tests for broker price/volume conversion helpers."""

from broker._convert import (
    price_from_api,
    price_to_api,
    volume_from_lots,
    volume_to_lots,
)


class TestPriceFromApi:
    def test_forex_price(self):
        # 1.20350 sent as 120350
        assert price_from_api(120350) == 1.2035

    def test_index_price_us30(self):
        # US30 at 39500.5 sent as 3950050000
        assert price_from_api(3950050000) == 39500.5

    def test_zero(self):
        assert price_from_api(0) == 0.0

    def test_negative_price(self):
        assert price_from_api(-120350) == -1.2035

    def test_with_digits_rounding(self):
        # Round to 1 digit for US30
        result = price_from_api(3950050000, digits=1)
        assert result == 39500.5

    def test_with_digits_5(self):
        result = price_from_api(120357, digits=5)
        assert result == 1.20357


class TestPriceToApi:
    def test_forex_price(self):
        assert price_to_api(1.2035) == 120350

    def test_index_price(self):
        assert price_to_api(39500.5) == 3950050000

    def test_zero(self):
        assert price_to_api(0.0) == 0

    def test_roundtrip_forex(self):
        original = 1.20357
        assert price_from_api(price_to_api(original), digits=5) == original

    def test_roundtrip_index(self):
        original = 39500.5
        assert price_from_api(price_to_api(original), digits=1) == original


class TestVolumeFromLots:
    def test_one_lot(self):
        # 1 lot = 100000 in API (volume in cents of base)
        assert volume_from_lots(100000) == 1.0

    def test_mini_lot(self):
        # 0.1 lot = 10000 in API
        assert volume_from_lots(10000) == 0.1

    def test_micro_lot(self):
        # 0.01 lot = 1000 in API
        assert volume_from_lots(1000) == 0.01

    def test_zero(self):
        assert volume_from_lots(0) == 0.0


class TestVolumeToLots:
    def test_one_lot(self):
        assert volume_to_lots(1.0) == 100000

    def test_mini_lot(self):
        assert volume_to_lots(0.1) == 10000

    def test_micro_lot(self):
        assert volume_to_lots(0.01) == 1000

    def test_roundtrip(self):
        original = 0.25
        assert volume_from_lots(volume_to_lots(original)) == original
