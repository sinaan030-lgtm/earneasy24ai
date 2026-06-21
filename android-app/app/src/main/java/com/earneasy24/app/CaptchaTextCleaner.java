package com.earneasy24.app;

import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

final class CaptchaTextCleaner {
    private static final Pattern STRUCTURED_CAPTCHA =
            Pattern.compile("(?i)CAPTCHA\\s*:\\s*([^\\r\\n]+)");
    private static final Pattern PREFIX =
            Pattern.compile("(?i)^(?:the\\s+)?(?:captcha|answer|text|value|solution|challenge|result)(?:\\s+is)?\\s*[:=-]\\s*");
    private static final Pattern CODE_BLOCK_START =
            Pattern.compile("(?i)^```(?:text)?");

    private CaptchaTextCleaner() {
    }

    static String clean(String raw) {
        if (raw == null) {
            return "";
        }

        String text = raw.trim();
        Matcher match = STRUCTURED_CAPTCHA.matcher(text);
        if (match.find()) {
            text = stripQuotes(match.group(1).trim());
        } else {
            text = CODE_BLOCK_START.matcher(text).replaceFirst("").trim();
            if (text.endsWith("```")) {
                text = text.substring(0, text.length() - 3).trim();
            }
            boolean hadPrefix = PREFIX.matcher(text).find();
            text = PREFIX.matcher(text).replaceFirst("").trim();
            if (hadPrefix) {
                text = stripOuterMarkdownEmphasis(text);
            }
            text = stripQuotes(text);
        }

        String lower = text.toLowerCase(Locale.US);
        if (containsAny(lower, "sorry", "cannot read", "unable to", "don't see",
                "no text", "clear text", "i see", "loading spinner", "blinking cursor")) {
            return "";
        }

        String strippedLower = stripTrailingPunctuation(lower);
        if (strippedLower.equals("none") || strippedLower.equals("no text")
                || strippedLower.equals("no visible text") || strippedLower.equals("n/a")) {
            return "";
        }

        if (isPlaceholder(text)) {
            return "";
        }

        text = stripTrailingPunctuation(text);
        StringBuilder cleaned = new StringBuilder(text.length());
        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            if (!Character.isWhitespace(ch) && ch >= 32 && ch <= 126) {
                cleaned.append(ch);
            }
        }
        return cleaned.toString();
    }

    static boolean isLengthValid(String value, AppSettings settings) {
        return value.length() >= settings.minLength() && value.length() <= settings.maxLength();
    }

    private static boolean containsAny(String text, String... phrases) {
        for (String phrase : phrases) {
            if (text.contains(phrase)) {
                return true;
            }
        }
        return false;
    }

    private static String stripOuterMarkdownEmphasis(String value) {
        String text = value;
        String[] delimiters = {"**", "__"};
        for (String delimiter : delimiters) {
            if (text.startsWith(delimiter)
                    && text.endsWith(delimiter)
                    && text.length() > delimiter.length() * 2) {
                return text.substring(
                        delimiter.length(),
                        text.length() - delimiter.length()).trim();
            }
        }
        return text;
    }

    private static boolean isPlaceholder(String text) {
        return text.equals("<answer>")
                || text.equals("<exact_characters>")
                || text.equals("<exact_text>")
                || text.equals("<value>")
                || text.equals("<text>")
                || text.equals("VALUE")
                || text.equals("value")
                || text.equals("[answer]")
                || text.equals("[value]");
    }

    private static String stripQuotes(String value) {
        String text = value;
        while (!text.isEmpty() && "\"'` ".indexOf(text.charAt(0)) >= 0) {
            text = text.substring(1);
        }
        while (!text.isEmpty() && "\"'` ".indexOf(text.charAt(text.length() - 1)) >= 0) {
            text = text.substring(0, text.length() - 1);
        }
        return text;
    }

    private static String stripTrailingPunctuation(String value) {
        String text = value;
        while (!text.isEmpty()) {
            char ch = text.charAt(text.length() - 1);
            if (ch == '.' || ch == ',' || ch == '!' || ch == '?' || ch == ';' || ch == ':') {
                text = text.substring(0, text.length() - 1);
            } else {
                return text;
            }
        }
        return text;
    }
}
