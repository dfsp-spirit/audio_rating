class I18n {
  constructor() {
    this.currentLanguage = 'en';
    this.translations = {};
    this.isLoaded = false;
    this.loadPromise = null;
  }

  detectLanguage() {
    const params = new URLSearchParams(window.location.search);
    const urlLang = params.get('lang');
    if (urlLang && ['en', 'de'].includes(urlLang)) {
      return urlLang;
    }

    const storedLang = localStorage.getItem('ar_lang');
    if (storedLang && ['en', 'de'].includes(storedLang)) {
      return storedLang;
    }

    const browserLang = (navigator.language || 'en').toLowerCase();
    if (browserLang.startsWith('de')) {
      return 'de';
    }

    return 'en';
  }

  async init(language = null) {
    const lang = language || this.detectLanguage();
    return this.setLanguage(lang);
  }

  async setLanguage(language) {
    if (language === this.currentLanguage && this.isLoaded) {
      return;
    }

    this.currentLanguage = language;

    try {
      this.loadPromise = this.loadTranslations(language);
      await this.loadPromise;
      this.updateHtmlLang(language);
      this.isLoaded = true;
      localStorage.setItem('ar_lang', language);
      this.applyTranslations();

      window.dispatchEvent(new CustomEvent('i18n:languageChanged', {
        detail: { language, translations: this.translations }
      }));
    } catch (error) {
      console.error(`Failed to set language to ${language}:`, error);
      if (language !== 'en') {
        return this.setLanguage('en');
      }
      throw error;
    } finally {
      this.loadPromise = null;
    }
  }

  async loadTranslations(language) {
    const response = await fetch(`./locales/${language}.json`);
    if (!response.ok) {
      throw new Error(`Failed to load ${language} translations: ${response.status}`);
    }
    this.translations = await response.json();
  }

  updateHtmlLang(language) {
    document.documentElement.lang = language;
  }

  t(keyPath, params = {}) {
    if (!this.isLoaded) {
      return keyPath;
    }

    const keys = keyPath.split('.');
    let value = this.translations;

    for (const key of keys) {
      if (value && typeof value === 'object' && key in value) {
        value = value[key];
      } else {
        return keyPath;
      }
    }

    if (typeof value === 'string' && Object.keys(params).length > 0) {
      return value.replace(/\{\{(\w+)\}\}/g, (match, paramKey) => {
        return params[paramKey] !== undefined ? params[paramKey] : match;
      });
    }

    return value;
  }

  applyTranslations(container = document) {
    if (!this.isLoaded) {
      return;
    }

    container.querySelectorAll('[data-i18n]').forEach(element => {
      const key = element.getAttribute('data-i18n');
      const value = this.t(key);
      if (value !== key) {
        element.textContent = value;
      }
    });

    container.querySelectorAll('[data-i18n-html]').forEach(element => {
      const key = element.getAttribute('data-i18n-html');
      const value = this.t(key);
      if (value !== key) {
        element.innerHTML = value;
      }
    });

    container.querySelectorAll('[data-i18n-title]').forEach(element => {
      const key = element.getAttribute('data-i18n-title');
      const value = this.t(key);
      if (value !== key) {
        element.title = value;
      }
    });

    container.querySelectorAll('[data-i18n-aria-label]').forEach(element => {
      const key = element.getAttribute('data-i18n-aria-label');
      const value = this.t(key);
      if (value !== key) {
        element.setAttribute('aria-label', value);
      }
    });
  }
}

window.i18n = new I18n();
export default window.i18n;
