from __future__ import annotations

import json
from datetime import date as real_date
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
from app.services import data_service




@pytest.fixture
def mockdb(tmp_path, monkeypatch):
	users_file = tmp_path / "users.json"
	tx_file = tmp_path / "transactions.json"
	monkeypatch.setattr(data_service, "USERS_FILE", str(users_file))
	monkeypatch.setattr(data_service, "TRANSACTIONS_FILE", str(tx_file))
	return users_file, tx_file


def _write_json(path, payload):
	path.write_text(json.dumps(payload), encoding="utf-8")


def _read_json(path):
	return json.loads(path.read_text(encoding="utf-8"))


def test_load_json_returns_empty_dict_when_file_missing(tmp_path):
	missing = tmp_path / "missing.json"
	assert data_service._load_json(str(missing)) == {}


def test_load_json_reads_existing_file(tmp_path):
	existing = tmp_path / "data.json"
	_write_json(existing, {"k": [1, 2]})
	assert data_service._load_json(str(existing)) == {"k": [1, 2]}


def test_save_json_writes_with_valid_content(tmp_path):
	output = tmp_path / "out.json"
	payload = {"user": {"wallet": []}}

	data_service._save_json(str(output), payload)

	assert _read_json(output) == payload


def test_get_user_wallet_returns_wallet_for_existing_user(mockdb):
	users_file, _ = mockdb
	_write_json(users_file, {"u_001": {"wallet": [{"card_id": "c1"}]}})

	wallet = data_service.get_user_wallet("u_001")

	assert wallet == [{"card_id": "c1"}]


def test_get_user_wallet_returns_empty_for_missing_user(mockdb):
	users_file, _ = mockdb
	_write_json(users_file, {"u_999": {"wallet": [{"card_id": "c1"}]}})

	wallet = data_service.get_user_wallet("u_001")

	assert wallet == []


def test_card_exists_in_wallet_true_and_false(mockdb):
	users_file, _ = mockdb
	_write_json(users_file, {"u_001": {"wallet": [{"card_id": "ww"}, {"card_id": "tuvalu"}]}})

	assert data_service.card_exists_in_wallet("ww", "u_001") is True
	assert data_service.card_exists_in_wallet("missing", "u_001") is False


def test_create_transaction_initializes_user_list_and_defaults(monkeypatch, mockdb):
	_, tx_file = mockdb

	monkeypatch.setattr(data_service.uuid, "uuid4", lambda: "abcd1234efgh")

	class FakeDate:
		@classmethod
		def today(cls):
			return real_date(2026, 3, 23)

	monkeypatch.setattr(data_service, "date", FakeDate)

	payload = {
		"item": "Grab",
		"amount_sgd": 12.5,
		"card_id": "ww",
		"channel": "online",
	}

	created = data_service.create_transaction(payload, user_id="u_001")

	assert created["id"] == "abcd1234"
	assert created["date"] == "2026-03-23"
	assert created["is_overseas"] is False
	assert created["user_id"] == "u_001"

	stored = _read_json(tx_file)
	assert stored["u_001"][0]["id"] == "abcd1234"


def test_create_transaction_appends_and_honors_provided_fields(monkeypatch, mockdb):
	_, tx_file = mockdb
	_write_json(tx_file, {"u_001": [{"id": "old"}]})
	monkeypatch.setattr(data_service.uuid, "uuid4", lambda: "zyxw9876tttt")

	payload = {
		"item": "Hotel",
		"amount_sgd": 400,
		"card_id": "tuvalu",
		"channel": "offline",
		"is_overseas": True,
		"date": "2026-01-15",
	}

	created = data_service.create_transaction(payload, user_id="u_001")

	assert created["id"] == "zyxw9876"
	assert created["date"] == "2026-01-15"
	assert created["is_overseas"] is True

	stored = _read_json(tx_file)
	assert len(stored["u_001"]) == 2
	assert stored["u_001"][1]["id"] == "zyxw9876"


def test_get_user_transactions_sorts_desc_when_enabled(mockdb):
	_, tx_file = mockdb
	_write_json(
		tx_file,
		{
			"u_001": [
				{"id": "a", "date": "2025-01-01"},
				{"id": "b", "date": "2026-01-01"},
				{"id": "c"},
			]
		},
	)

	transactions = data_service.get_user_transactions("u_001", sort_by_date_desc=True)

	assert [t["id"] for t in transactions] == ["b", "a", "c"]


def test_get_user_transactions_returns_unsorted_when_disabled(mockdb):
	_, tx_file = mockdb
	_write_json(
		tx_file,
		{
			"u_001": [
				{"id": "a", "date": "2025-01-01"},
				{"id": "b", "date": "2026-01-01"},
			]
		},
	)

	transactions = data_service.get_user_transactions("u_001", sort_by_date_desc=False)

	assert [t["id"] for t in transactions] == ["a", "b"]


def test_get_user_transactions_empty_user_list(mockdb):
	_, tx_file = mockdb
	_write_json(tx_file, {})

	transactions = data_service.get_user_transactions("u_001", sort_by_date_desc=True)

	assert transactions == []


def test_get_transaction_by_id_found_and_not_found(mockdb):
	_, tx_file = mockdb
	_write_json(
		tx_file,
		{
			"u_001": [
				{"id": "t1", "item": "Coffee"},
				{"id": "t2", "item": "Taxi"},
			]
		},
	)

	found = data_service.get_transaction_by_id("t2", "u_001")
	not_found = data_service.get_transaction_by_id("missing", "u_001")

	assert found == {"id": "t2", "item": "Taxi"}
	assert not_found is None


def test_init_sample_data_creates_default_user_when_missing(mockdb):
	users_file, _ = mockdb
	_write_json(users_file, {"u_999": {"wallet": []}})

	data_service.init_sample_data()

	users = _read_json(users_file)
	assert "u_001" in users
	assert users["u_001"]["username"] == "demo"
	assert len(users["u_001"]["wallet"]) == 2


def test_init_sample_data_is_idempotent_when_user_exists(mockdb):
	users_file, _ = mockdb
	original = {
		"u_001": {
			"user_id": "u_001",
			"username": "already-there",
			"preference": "cashback",
			"wallet": [{"card_id": "custom"}],
		}
	}
	_write_json(users_file, original)

	data_service.init_sample_data()

	assert _read_json(users_file) == original
