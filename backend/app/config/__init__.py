import os

DEV_CORS_ORIGINS = [
	"http://localhost:5173",
	"http://localhost:5174",
	"http://localhost:5175",
	"http://localhost:5176",
	"http://127.0.0.1:5173",
	"http://127.0.0.1:5174",
	"http://127.0.0.1:5175",
	"http://127.0.0.1:5176",
	"http://localhost:3000",
	"http://127.0.0.1:3000",
	"http://localhost:5177",
]


def get_cors_allowed_origins() -> list[str]:
	"""Resolve CORS origins from CORS_ALLOWED_ORIGINS with safe defaults."""
	cors_origins_str = os.getenv("CORS_ALLOWED_ORIGINS")

	if cors_origins_str is None or not cors_origins_str.strip():
		return DEV_CORS_ORIGINS

	origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]
	if "*" in origins and len(origins) > 1:
		raise ValueError(
			"Invalid CORS_ALLOWED_ORIGINS: '*' cannot be combined with explicit origins."
		)
	return origins


def get_cors_allow_credentials(origins: list[str]) -> bool:
	"""Disable credentialed CORS when wildcard origin is enabled."""
	return "*" not in origins
