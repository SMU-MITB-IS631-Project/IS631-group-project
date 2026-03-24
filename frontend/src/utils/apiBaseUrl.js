const rawEnvBaseUrl = import.meta.env.VITE_API_BASE_URL;
const envBaseUrl = typeof rawEnvBaseUrl === 'string' ? rawEnvBaseUrl.trim() : '';

function getDefaultApiBaseUrl() {
	if (typeof window === 'undefined') {
		return '';
	}

	const { protocol, hostname } = window.location;
	const isLocalHost = hostname === 'localhost' || hostname === '127.0.0.1';

	// In local dev, keep same-origin so Vite proxy can forward /api requests.
	if (isLocalHost) {
		return '';
	}

	// In CD/prod without explicit env, use current host with backend default port.
	return `${protocol}//${hostname}:8000`;
}

const rawBaseUrl = envBaseUrl || getDefaultApiBaseUrl();
const API_BASE_URL = rawBaseUrl.replace(/\/+$/, '');

export default API_BASE_URL;
