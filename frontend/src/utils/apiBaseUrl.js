const rawBaseUrl = import.meta.env.VITE_API_BASE_URL ?? '';
const API_BASE_URL = rawBaseUrl.replace(/\/+$/, '');

export default API_BASE_URL;
