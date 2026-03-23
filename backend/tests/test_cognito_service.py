from __future__ import annotations

import base64
import hashlib
import hmac
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

import app.services.cognito_service as cognito_module
from app.exceptions import ServiceException
from app.services.cognito_service import CognitoService, RoleChecker




def _build_fake_cognito_client() -> Mock:
	client = Mock()
	client.exceptions = SimpleNamespace(
		NotAuthorizedException=type("NotAuthorizedException", (Exception,), {}),
		UserNotConfirmedException=type("UserNotConfirmedException", (Exception,), {}),
		UsernameExistsException=type("UsernameExistsException", (Exception,), {}),
		AliasExistsException=type("AliasExistsException", (Exception,), {}),
		InvalidParameterException=type("InvalidParameterException", (Exception,), {}),
		CodeMismatchException=type("CodeMismatchException", (Exception,), {}),
		ExpiredCodeException=type("ExpiredCodeException", (Exception,), {}),
		UserNotFoundException=type("UserNotFoundException", (Exception,), {}),
	)
	return client


@pytest.fixture
def mockdb(monkeypatch):
	monkeypatch.setenv("COGNITO_REGION", "ap-southeast-1")
	monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
	monkeypatch.setenv("COGNITO_CLIENT_ID", "client-abc")
	monkeypatch.setenv("COGNITO_CLIENT_SECRET", "secret-xyz")

	fake_client = _build_fake_cognito_client()
	monkeypatch.setattr(cognito_module.boto3, "client", lambda *_args, **_kwargs: fake_client)
	return fake_client


@pytest.fixture
def service_and_client(mockdb):
	service = CognitoService()
	return service, mockdb


def _bearer(token: str = "token") -> HTTPAuthorizationCredentials:
	return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_get_cognito_jwks_success(monkeypatch, service_and_client):
	service, _ = service_and_client
	response = Mock(status_code=200)
	response.json.return_value = {"keys": [{"kid": "k1"}]}
	monkeypatch.setattr(cognito_module.requests, "get", Mock(return_value=response))

	assert service._get_cognito_jwks() == [{"kid": "k1"}]


def test_get_cognito_jwks_raises_when_non_200(monkeypatch, service_and_client):
	service, _ = service_and_client
	response = Mock(status_code=503)
	monkeypatch.setattr(cognito_module.requests, "get", Mock(return_value=response))

	with pytest.raises(ServiceException) as exc:
		service._get_cognito_jwks()

	assert exc.value.status_code == 500
	assert "Unable to fetch JWKS" in exc.value.detail


def test_jwks_keys_is_lazily_cached(service_and_client):
	service, _ = service_and_client
	service._get_cognito_jwks = Mock(return_value=[{"kid": "k1"}])

	first = service.jwks_keys
	second = service.jwks_keys

	assert first == [{"kid": "k1"}]
	assert second == [{"kid": "k1"}]
	service._get_cognito_jwks.assert_called_once()


def test_validate_token_success(monkeypatch, service_and_client):
	service, _ = service_and_client
	service._jwks_keys = [{"kid": "kid-1"}]
	monkeypatch.setattr(cognito_module.jwt, "get_unverified_header", Mock(return_value={"kid": "kid-1"}))
	decode_mock = Mock(return_value={"sub": "user-1"})
	monkeypatch.setattr(cognito_module.jwt, "decode", decode_mock)

	payload = service.validate_token(_bearer("jwt-token"))

	assert payload == {"sub": "user-1"}
	decode_mock.assert_called_once_with(
		"jwt-token",
		key={"kid": "kid-1"},
		algorithms=["RS256"],
		audience="client-abc",
		issuer="https://cognito-idp.ap-southeast-1.amazonaws.com/pool-123",
	)


def test_validate_token_invalid_signature(monkeypatch, service_and_client):
	service, _ = service_and_client
	service._jwks_keys = [{"kid": "known"}]
	monkeypatch.setattr(cognito_module.jwt, "get_unverified_header", Mock(return_value={"kid": "unknown"}))

	with pytest.raises(ServiceException) as exc:
		service.validate_token(_bearer())

	assert exc.value.status_code == 401
	assert exc.value.detail == "Invalid token signature."


def test_validate_token_expired_signature(monkeypatch, service_and_client):
	service, _ = service_and_client
	service._jwks_keys = [{"kid": "kid-1"}]
	monkeypatch.setattr(cognito_module.jwt, "get_unverified_header", Mock(return_value={"kid": "kid-1"}))
	monkeypatch.setattr(cognito_module.jwt, "decode", Mock(side_effect=jwt.ExpiredSignatureError()))

	with pytest.raises(ServiceException) as exc:
		service.validate_token(_bearer())

	assert exc.value.status_code == 401
	assert exc.value.detail == "Token has expired."


def test_validate_token_jwt_error(monkeypatch, service_and_client):
	service, _ = service_and_client
	service._jwks_keys = [{"kid": "kid-1"}]
	monkeypatch.setattr(cognito_module.jwt, "get_unverified_header", Mock(return_value={"kid": "kid-1"}))
	monkeypatch.setattr(cognito_module.jwt, "decode", Mock(side_effect=jwt.JWTError("bad token")))

	with pytest.raises(ServiceException) as exc:
		service.validate_token(_bearer())

	assert exc.value.status_code == 401
	assert "Token validation error" in exc.value.detail


def test_calculate_secret_hash_matches_expected(service_and_client):
	service, _ = service_and_client

	actual = service.calculate_secret_hash("alice")
	expected = base64.b64encode(
		hmac.new(
			b"secret-xyz",
			b"aliceclient-abc",
			hashlib.sha256,
		).digest()
	).decode()

	assert actual == expected


def test_authenticate_user_success(service_and_client):
	service, client = service_and_client
	client.initiate_auth.return_value = {
		"AuthenticationResult": {
			"IdToken": "id-tok",
			"AccessToken": "access-tok",
			"RefreshToken": "refresh-tok",
		}
	}

	tokens = service.authenticate_user("alice", "pass")

	assert tokens == {
		"id_token": "id-tok",
		"access_token": "access-tok",
		"refresh_token": "refresh-tok",
	}


def test_authenticate_user_not_authorized_maps_to_401(service_and_client):
	service, client = service_and_client
	client.initiate_auth.side_effect = client.exceptions.NotAuthorizedException()

	with pytest.raises(ServiceException) as exc:
		service.authenticate_user("alice", "bad-pass")

	assert exc.value.status_code == 401
	assert exc.value.detail == "Invalid username or password."


def test_authenticate_user_not_confirmed_maps_to_403(service_and_client):
	service, client = service_and_client
	client.initiate_auth.side_effect = client.exceptions.UserNotConfirmedException()

	with pytest.raises(ServiceException) as exc:
		service.authenticate_user("alice", "pass")

	assert exc.value.status_code == 403
	assert exc.value.detail == "User account not confirmed."


def test_authenticate_user_unexpected_error_maps_to_500(service_and_client):
	service, client = service_and_client
	client.initiate_auth.side_effect = RuntimeError("boom")

	with pytest.raises(ServiceException) as exc:
		service.authenticate_user("alice", "pass")

	assert exc.value.status_code == 500
	assert "Authentication failed: boom" == exc.value.detail


def test_check_user_role_success(service_and_client):
	service, _ = service_and_client
	assert service.check_user_role({"cognito:groups": ["Admins", "Users"]}, "Admins") is True


def test_check_user_role_forbidden(service_and_client):
	service, _ = service_and_client

	with pytest.raises(ServiceException) as exc:
		service.check_user_role({"cognito:groups": ["Users"]}, "Admins")

	assert exc.value.status_code == 403
	assert exc.value.detail == "Insufficient permissions"


def test_register_user_success(service_and_client):
	service, client = service_and_client
	client.sign_up.return_value = {"UserConfirmed": False}

	response = service.register_user("alice", "alice@example.com", "Pass#123")

	assert response == {"UserConfirmed": False}


def test_register_user_username_exists_maps_to_409(service_and_client):
	service, client = service_and_client
	client.sign_up.side_effect = client.exceptions.UsernameExistsException()

	with pytest.raises(ServiceException) as exc:
		service.register_user("alice", "alice@example.com", "Pass#123")

	assert exc.value.status_code == 409
	assert exc.value.detail == "Username already exists."


def test_register_user_alias_exists_maps_to_409(service_and_client):
	service, client = service_and_client
	client.sign_up.side_effect = client.exceptions.AliasExistsException()

	with pytest.raises(ServiceException) as exc:
		service.register_user("alice", "alice@example.com", "Pass#123")

	assert exc.value.status_code == 409
	assert exc.value.detail == "Email already exists."


def test_register_user_invalid_parameter_email_exists_maps_to_409(service_and_client):
	service, client = service_and_client
	client.sign_up.side_effect = client.exceptions.InvalidParameterException("Email already exists")

	with pytest.raises(ServiceException) as exc:
		service.register_user("alice", "alice@example.com", "Pass#123")

	assert exc.value.status_code == 409
	assert exc.value.detail == "Email already exists."


def test_register_user_invalid_parameter_other_maps_to_400(service_and_client):
	service, client = service_and_client
	client.sign_up.side_effect = client.exceptions.InvalidParameterException("Bad password")

	with pytest.raises(ServiceException) as exc:
		service.register_user("alice", "alice@example.com", "Pass#123")

	assert exc.value.status_code == 400
	assert exc.value.detail == "Bad password"


def test_register_user_unexpected_error_maps_to_500(service_and_client):
	service, client = service_and_client
	client.sign_up.side_effect = RuntimeError("service down")

	with pytest.raises(ServiceException) as exc:
		service.register_user("alice", "alice@example.com", "Pass#123")

	assert exc.value.status_code == 500
	assert exc.value.detail == "Registration failed: service down"


def test_confirm_user_success(service_and_client):
	service, client = service_and_client

	message = service.confirm_user("alice", "123456")

	assert message == "User confirmed successfully."
	client.confirm_sign_up.assert_called_once()


def test_confirm_user_invalid_code_maps_to_400(service_and_client):
	service, client = service_and_client
	client.confirm_sign_up.side_effect = client.exceptions.CodeMismatchException()

	with pytest.raises(ServiceException) as exc:
		service.confirm_user("alice", "wrong")

	assert exc.value.status_code == 400
	assert exc.value.detail == "Invalid confirmation code."


def test_confirm_user_expired_code_maps_to_400(service_and_client):
	service, client = service_and_client
	client.confirm_sign_up.side_effect = client.exceptions.ExpiredCodeException()

	with pytest.raises(ServiceException) as exc:
		service.confirm_user("alice", "old")

	assert exc.value.status_code == 400
	assert exc.value.detail == "Confirmation code has expired."


def test_confirm_user_not_found_maps_to_404(service_and_client):
	service, client = service_and_client
	client.confirm_sign_up.side_effect = client.exceptions.UserNotFoundException()

	with pytest.raises(ServiceException) as exc:
		service.confirm_user("alice", "123456")

	assert exc.value.status_code == 404
	assert exc.value.detail == "User not found."


def test_confirm_user_unexpected_error_maps_to_500(service_and_client):
	service, client = service_and_client
	client.confirm_sign_up.side_effect = RuntimeError("unexpected")

	with pytest.raises(ServiceException) as exc:
		service.confirm_user("alice", "123456")

	assert exc.value.status_code == 500
	assert exc.value.detail == "Confirmation failed: unexpected"


def test_delete_user_success(service_and_client):
	service, client = service_and_client

	service.delete_user("alice")

	client.admin_delete_user.assert_called_once_with(UserPoolId="pool-123", Username="alice")


def test_delete_user_not_found_is_ignored(service_and_client):
	service, client = service_and_client
	client.admin_delete_user.side_effect = client.exceptions.UserNotFoundException()

	service.delete_user("ghost")


def test_delete_user_unexpected_error_maps_to_500(service_and_client):
	service, client = service_and_client
	client.admin_delete_user.side_effect = RuntimeError("api error")

	with pytest.raises(ServiceException) as exc:
		service.delete_user("alice")

	assert exc.value.status_code == 500
	assert exc.value.detail == "Cognito cleanup failed: api error"


def test_role_checker_raises_401_when_missing_auth():
	checker = RoleChecker()

	with pytest.raises(HTTPException) as exc:
		checker(auth=None, cognito_service=Mock())

	assert exc.value.status_code == 401
	assert exc.value.detail == "Not authenticated"


def test_role_checker_validates_and_checks_allowed_role():
	checker = RoleChecker(allowed_role="Admins")
	service = Mock()
	service.validate_token.return_value = {"sub": "user-1", "cognito:groups": ["Admins"]}

	claims = checker(auth=_bearer(), cognito_service=service)

	assert claims["sub"] == "user-1"
	service.check_user_role.assert_called_once_with({"sub": "user-1", "cognito:groups": ["Admins"]}, "Admins")


def test_role_checker_validates_without_allowed_role():
	checker = RoleChecker()
	service = Mock()
	service.validate_token.return_value = {"sub": "user-1", "cognito:groups": ["Users"]}

	claims = checker(auth=_bearer(), cognito_service=service)

	assert claims["sub"] == "user-1"
	service.validate_token.assert_called_once()
	service.check_user_role.assert_not_called()


def test_role_checker_maps_service_exception_to_http_exception():
	checker = RoleChecker(allowed_role="Admins")
	service = Mock()
	service.validate_token.side_effect = ServiceException(status_code=403, detail="Insufficient permissions")

	with pytest.raises(HTTPException) as exc:
		checker(auth=_bearer(), cognito_service=service)

	assert exc.value.status_code == 403
	assert exc.value.detail == "Insufficient permissions"
