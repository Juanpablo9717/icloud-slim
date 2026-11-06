"""User-facing text in every supported language. t("key", name=...) returns it in the current LANG.

Each module registers its own strings: STRINGS.update({"key": {"en": "...", "es": "..."}}).
Placeholders use str.format: "{n} videos". A missing translation falls back to English, then to the key.
"""
LANGS = {"en": "English", "es": "Español"}
LANG = "en"
STRINGS = {}


def t(key, **kw):
    entry = STRINGS.get(key)
    text = (entry.get(LANG) or entry.get("en")) if entry else key
    return text.format(**kw) if kw else text
