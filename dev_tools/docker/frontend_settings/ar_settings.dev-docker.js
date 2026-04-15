// Application settings for Audiorating (AR) frontend in Docker-based development.

const AR_SETTINGS = {
    API_BASE_URL: 'http://localhost:3000/ar_backend/api',
};

window.AR_SETTINGS = AR_SETTINGS;

console.log('ar_settings.dev-docker.js loaded, AR_SETTINGS:', AR_SETTINGS);
