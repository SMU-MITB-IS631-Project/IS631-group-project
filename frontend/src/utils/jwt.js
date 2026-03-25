// Utility to decode JWT and extract username
export function getUsernameFromJWT() {
  const token = localStorage.getItem('access_token');
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.username || payload.preferred_username || payload.sub || null;
  } catch (e) {
    return null;
  }
}
