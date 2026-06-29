/**
 * FMailSender — Frontend build version.
 *
 * Must stay in sync with core/_version.py (APP_VERSION).
 * The release pipeline (.github/workflows/release.yml) updates this file
 * automatically when building a new version tag.
 *
 * Used by StartupOverlay to detect a stale WebView2 cache:
 * if the backend reports a different version, it means the old index.html
 * was loaded from cache → force window.location.reload() to get fresh files.
 */
export const FRONTEND_VERSION = "6.0.5"
