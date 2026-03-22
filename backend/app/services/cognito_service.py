import os
from jose import jwt
import boto3
import hmac
import hashlib
import base64
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import requests
from app.services.errors import ServiceError

# load_dotenv()


CognitoUserRole = os.getenv("COGNITO_USER_ROLE", "Users")
CognitoAdminRole = os.getenv("COGNITO_ADMIN_ROLE", "Admins")
bearer_scheme = HTTPBearer(auto_error=False)

class CognitoService:
    def __init__(self):
        # Allow local tests/coverage runs without AWS config.
        # Prefer explicit Cognito region, then standard AWS env vars, then a safe default.
        self.region = (
            os.getenv("COGNITO_REGION")
            or os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
            or "us-east-1"
        )
        self.user_pool_id = os.getenv("COGNITO_USER_POOL_ID")
        self.client_id = os.getenv("COGNITO_CLIENT_ID")
        self.client_secret = os.getenv("COGNITO_CLIENT_SECRET")

        # JSON Web Key Set (JWKS) is a collection of public cryptographic keys used to verify JSON Web Tokens
        self.jwks_url = f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}/.well-known/jwks.json"
        self._jwks_keys = None  # Lazy-loaded on first use
        self.bearer = bearer_scheme

        # Initialize Boto3 Cognito client
        self.client = boto3.client("cognito-idp", region_name=self.region)

    def _get_cognito_jwks(self):
        """
        Retrieve JWKS (JSON Web Key Set) for token validation from AWS Cognito.
        """
        response = requests.get(self.jwks_url)
        if response.status_code != 200:
            raise ServiceError(
                status_code=500,
                code="INTERNAL_SERVER_ERROR",
                message="Unable to fetch JWKS for token validation.",
                details={},
            )
        return response.json()["keys"]

    @property
    def jwks_keys(self):
        """Lazily fetch JWKS keys on first use."""
        if self._jwks_keys is None:
            self._jwks_keys = self._get_cognito_jwks()
        return self._jwks_keys

    def validate_token(self, auth: HTTPAuthorizationCredentials):
        """
        Validate and decode a JWT token issued by AWS Cognito.

        :param credentials: HTTPAuthorizationCredentials (token from the Authorization header).
        :return: The decoded token payload.
        """
        try:
            # Decode token using Cognito's JWKS
            token = auth.credentials
            headers = jwt.get_unverified_header(token)
            
            # Finding a specific JSON Web Key (JWK) from a JWKS using the "kid" (Key ID) parameter
            kid = headers.get("kid")
            key = next((k for k in self.jwks_keys if k["kid"] == kid), None)
            if not key:
                raise ServiceError(
                    status_code=401,
                    code="UNAUTHORIZED",
                    message="Invalid token signature.",
                    details={},
                )
            
            payload = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}",
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise ServiceError(
                status_code=401,
                code="UNAUTHORIZED",
                message="Token has expired.",
                details={},
            )
        except jwt.JWTError as e:
            raise ServiceError(
                status_code=401,
                code="UNAUTHORIZED",
                message="Token validation error.",
                details={"cause": str(e)},
            )
        

    def calculate_secret_hash(self, username):
        """
        Calculate the Cognito SECRET_HASH for the given username.
        """
        message = username + self.client_id
        dig = hmac.new(
            self.client_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).digest()
        return base64.b64encode(dig).decode()

    def authenticate_user(self, username: str, password: str):
        """
        Authenticate a user with Cognito using their username and password.

        :param username: Username of the user.
        :param password: Password of the user.
        :return: Dictionary containing tokens if authentication is successful.
        """
        try:
            # Calculate the SECRET_HASH
            secret_hash = self.calculate_secret_hash(username)

            # Initiate the authentication
            response = self.client.initiate_auth(
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME": username,
                    "PASSWORD": password,
                    "SECRET_HASH": secret_hash
                },
                ClientId=self.client_id
            )

            return {
                "id_token": response["AuthenticationResult"]["IdToken"],
                "access_token": response["AuthenticationResult"]["AccessToken"],
                "refresh_token": response["AuthenticationResult"]["RefreshToken"]
            }

        except self.client.exceptions.NotAuthorizedException:
            raise ServiceError(
                status_code=401,
                code="UNAUTHORIZED",
                message="Invalid username or password.",
                details={},
            )
        except self.client.exceptions.UserNotConfirmedException:
            raise ServiceError(
                status_code=403,
                code="FORBIDDEN",
                message="User account not confirmed.",
                details={},
            )
        except Exception as e:
            raise ServiceError(
                status_code=500,
                code="INTERNAL_SERVER_ERROR",
                message="Authentication failed.",
                details={"cause": str(e)},
            )
        
    def check_user_role(self, claims, required_role: str):
        """
        Check if the token contains the required role.
        """
        groups = claims.get("cognito:groups", [])
        if required_role in groups:
            return True
        raise ServiceError(
            status_code=403,
            code="FORBIDDEN",
            message="Insufficient permissions.",
            details={},
        )

    def register_user(self, username: str, email: str, password: str):
        """
        Register a new user with a distinct username, and store the user's email in Cognito.
        """
        try:
            # Calculate the SECRET_HASH if your app client has a client secret
            secret_hash = self.calculate_secret_hash(username)

            response = self.client.sign_up(
                ClientId=self.client_id,
                SecretHash=secret_hash,
                Username=username,      # <--- Distinct username
                Password=password,
                UserAttributes=[
                    {
                        'Name': 'email',
                        'Value': email       # <--- Storing user's email as an attribute
                    }
                ]
            )

            return response

        except self.client.exceptions.UsernameExistsException:
            raise ServiceError(
                status_code=409,
                code="CONFLICT",
                message="Username already exists.",
                details={},
            )
        except self.client.exceptions.AliasExistsException:
            raise ServiceError(
                status_code=409,
                code="CONFLICT",
                message="Email already exists.",
                details={},
            )
        except self.client.exceptions.InvalidParameterException as e:
            message = str(e)
            if "email" in message.lower() and "exist" in message.lower():
                raise ServiceError(
                    status_code=409,
                    code="CONFLICT",
                    message="Email already exists.",
                    details={},
                )
            raise ServiceError(
                status_code=400,
                code="VALIDATION_ERROR",
                message=message,
                details={},
            )
        except Exception as e:
            raise ServiceError(
                status_code=500,
                code="INTERNAL_SERVER_ERROR",
                message="Registration failed.",
                details={"cause": str(e)},
            )
    
    
    def confirm_user(self, username: str, confirmation_code: str):
        """
        Confirm the user's signup with the code they received by email
        """
        try:
            # First confirm the sign-up
            self.client.confirm_sign_up(
                ClientId=self.client_id,
                Username=username,
                ConfirmationCode=confirmation_code,
                SecretHash=self.calculate_secret_hash(username)
            )

            return "User confirmed successfully."
        
        except self.client.exceptions.CodeMismatchException:
            raise ServiceError(
                status_code=400,
                code="VALIDATION_ERROR",
                message="Invalid confirmation code.",
                details={},
            )
        except self.client.exceptions.ExpiredCodeException:
            raise ServiceError(
                status_code=400,
                code="VALIDATION_ERROR",
                message="Confirmation code has expired.",
                details={},
            )
        except self.client.exceptions.UserNotFoundException:
            raise ServiceError(
                status_code=404,
                code="NOT_FOUND",
                message="User not found.",
                details={},
            )
        except Exception as e:
            raise ServiceError(
                status_code=500,
                code="INTERNAL_SERVER_ERROR",
                message="Confirmation failed.",
                details={"cause": str(e)},
            )

    def delete_user(self, username: str) -> None:
        """Delete a Cognito user from the user pool (admin operation)."""
        try:
            self.client.admin_delete_user(
                UserPoolId=self.user_pool_id,
                Username=username,
            )
        except self.client.exceptions.UserNotFoundException:
            return
        except Exception as e:
            raise ServiceError(
                status_code=500,
                code="INTERNAL_SERVER_ERROR",
                message="Cognito cleanup failed.",
                details={"cause": str(e)},
            )

class RoleChecker:
    def __init__(self, allowed_role: str):
        self.allowed_role = allowed_role

    def __call__(self, auth: HTTPAuthorizationCredentials = Depends(bearer_scheme), 
                 cognito_service: CognitoService = Depends(CognitoService)):
        # Validate the token and check the user's role
        if not auth:
            raise ServiceError(
                status_code=401,
                code="UNAUTHORIZED",
                message="Not authenticated.",
                details={},
            )
        claims = cognito_service.validate_token(auth)
        cognito_service.check_user_role(claims, self.allowed_role)
        return claims

