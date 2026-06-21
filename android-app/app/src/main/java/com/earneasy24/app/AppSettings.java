package com.earneasy24.app;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Rect;

final class AppSettings {
    static final String DEFAULT_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions";
    static final String DEFAULT_MODEL = "nvidia/llama-3.1-nemotron-nano-vl-8b-v1";

    private static final String PREFS = "earn_easy24_settings";
    private static final String KEY_API_URL = "api_url";
    private static final String KEY_MODEL = "model";
    private static final String KEY_API_KEY = "api_key";
    private static final String KEY_MIN_LENGTH = "min_length";
    private static final String KEY_MAX_LENGTH = "max_length";
    private static final String KEY_LOOP_DELAY = "loop_delay";
    private static final String KEY_COOLDOWN = "cooldown";
    private static final String KEY_REGION_LEFT = "region_left";
    private static final String KEY_REGION_TOP = "region_top";
    private static final String KEY_REGION_RIGHT = "region_right";
    private static final String KEY_REGION_BOTTOM = "region_bottom";

    private final SharedPreferences prefs;

    AppSettings(Context context) {
        this.prefs = context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    String apiUrl() {
        return prefs.getString(KEY_API_URL, DEFAULT_API_URL);
    }

    String model() {
        return prefs.getString(KEY_MODEL, DEFAULT_MODEL);
    }

    String apiKey() {
        return prefs.getString(KEY_API_KEY, "");
    }

    int minLength() {
        return prefs.getInt(KEY_MIN_LENGTH, 6);
    }

    int maxLength() {
        return prefs.getInt(KEY_MAX_LENGTH, 20);
    }

    float loopDelaySeconds() {
        return prefs.getFloat(KEY_LOOP_DELAY, 0.15f);
    }

    float cooldownSeconds() {
        return prefs.getFloat(KEY_COOLDOWN, 3.0f);
    }

    Rect region() {
        int left = prefs.getInt(KEY_REGION_LEFT, -1);
        int top = prefs.getInt(KEY_REGION_TOP, -1);
        int right = prefs.getInt(KEY_REGION_RIGHT, -1);
        int bottom = prefs.getInt(KEY_REGION_BOTTOM, -1);
        if (left < 0 || top < 0 || right <= left || bottom <= top) {
            return new Rect();
        }
        return new Rect(left, top, right, bottom);
    }

    String regionLabel() {
        Rect rect = region();
        if (rect.isEmpty()) {
            return "Not set";
        }
        return rect.left + "," + rect.top + "," + rect.width() + "," + rect.height();
    }

    void saveNetwork(String apiUrl, String model, String apiKey) {
        prefs.edit()
                .putString(KEY_API_URL, emptyToDefault(apiUrl, DEFAULT_API_URL))
                .putString(KEY_MODEL, emptyToDefault(model, DEFAULT_MODEL))
                .putString(KEY_API_KEY, apiKey == null ? "" : apiKey.trim())
                .apply();
    }

    void saveTuning(int minLength, int maxLength, float loopDelay, float cooldown) {
        prefs.edit()
                .putInt(KEY_MIN_LENGTH, Math.max(1, minLength))
                .putInt(KEY_MAX_LENGTH, Math.max(Math.max(1, minLength), maxLength))
                .putFloat(KEY_LOOP_DELAY, Math.max(0.05f, loopDelay))
                .putFloat(KEY_COOLDOWN, Math.max(0f, cooldown))
                .apply();
    }

    void saveRegion(Rect region) {
        prefs.edit()
                .putInt(KEY_REGION_LEFT, region.left)
                .putInt(KEY_REGION_TOP, region.top)
                .putInt(KEY_REGION_RIGHT, region.right)
                .putInt(KEY_REGION_BOTTOM, region.bottom)
                .apply();
    }

    private static String emptyToDefault(String value, String fallback) {
        if (value == null || value.trim().isEmpty()) {
            return fallback;
        }
        return value.trim();
    }
}
