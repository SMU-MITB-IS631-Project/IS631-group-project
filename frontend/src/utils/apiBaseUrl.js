const rawBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const API_BASE_URL = rawBaseUrl.replace(/\/+$/, '');

export default API_BASE_URL;
