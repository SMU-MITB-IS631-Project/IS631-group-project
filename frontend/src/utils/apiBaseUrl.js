const rawEnvBaseUrl = import.meta.env.VITE_API_BASE_URL;
const envBaseUrl = typeof rawEnvBaseUrl === 'string' ? rawEnvBaseUrl.trim() : '';

// Keep same-origin by default so deployed frontends can rely on /api reverse-proxy rules.
const rawBaseUrl = envBaseUrl || '';
const API_BASE_URL = rawBaseUrl.replace(/\/+$/, '');

export default API_BASE_URL;
