package com.earneasy24.app;

import android.graphics.Bitmap;
import android.util.Base64;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

final class AiVisionClient {
    private static final String PROMPT =
            "You are a CAPTCHA transcription engine. Your ONLY job is to read the exact characters shown in this CAPTCHA image.\n\n"
                    + "OUTPUT FORMAT (mandatory): CAPTCHA: <exact_characters>\n"
                    + "If the image is unreadable: CAPTCHA: NONE\n\n"
                    + "RULES:\n"
                    + "1. Copy every visible character exactly as shown, left to right. This includes letters, digits, and symbols such as %, =, @, #, $, !, +, *, and -.\n"
                    + "2. Ignore decorations only: strike-through lines, grid lines, and background noise are not part of the CAPTCHA answer.\n"
                    + "3. Case-sensitive: uppercase and lowercase are different.\n"
                    + "4. Do not add explanations, steps, or any text beyond the CAPTCHA value itself.\n"
                    + "5. Output ONLY the single line: CAPTCHA: <value>";

    String readCaptcha(Bitmap bitmap, AppSettings settings) throws Exception {
        String apiKey = settings.apiKey();
        if (apiKey.isEmpty()) {
            throw new IllegalStateException("NVIDIA API key is not set");
        }

        String imageDataUrl = "data:image/png;base64," + bitmapToBase64Png(bitmap);
        JSONObject payload = new JSONObject();
        payload.put("model", settings.model());
        payload.put("temperature", 0);
        payload.put("max_tokens", 64);
        payload.put("stream", false);

        JSONArray messages = new JSONArray();
        JSONObject message = new JSONObject();
        message.put("role", "user");

        JSONArray content = new JSONArray();
        JSONObject promptPart = new JSONObject();
        promptPart.put("type", "text");
        promptPart.put("text", PROMPT);
        content.put(promptPart);

        JSONObject imagePart = new JSONObject();
        imagePart.put("type", "image_url");
        JSONObject imageUrl = new JSONObject();
        imageUrl.put("url", imageDataUrl);
        imagePart.put("image_url", imageUrl);
        content.put(imagePart);

        message.put("content", content);
        messages.put(message);
        payload.put("messages", messages);

        HttpURLConnection connection = (HttpURLConnection) new URL(settings.apiUrl()).openConnection();
        connection.setRequestMethod("POST");
        connection.setConnectTimeout(5000);
        connection.setReadTimeout(30000);
        connection.setDoOutput(true);
        connection.setRequestProperty("Accept", "application/json");
        connection.setRequestProperty("Content-Type", "application/json");
        connection.setRequestProperty("Authorization", authHeader(apiKey));

        byte[] body = payload.toString().getBytes(StandardCharsets.UTF_8);
        connection.setFixedLengthStreamingMode(body.length);
        try (OutputStream output = connection.getOutputStream()) {
            output.write(body);
        }

        int status = connection.getResponseCode();
        InputStream responseStream = status >= 200 && status < 300
                ? connection.getInputStream()
                : connection.getErrorStream();
        String response = readAll(responseStream);
        if (status < 200 || status >= 300) {
            throw new IllegalStateException("AI request failed: HTTP " + status + " " + response);
        }
        return CaptchaTextCleaner.clean(extractMessage(response));
    }

    private static String authHeader(String apiKey) {
        String trimmed = apiKey.trim();
        if (trimmed.regionMatches(true, 0, "Bearer ", 0, 7)) {
            return trimmed;
        }
        return "Bearer " + trimmed;
    }

    private static String bitmapToBase64Png(Bitmap bitmap) {
        ByteArrayOutputStream stream = new ByteArrayOutputStream();
        bitmap.compress(Bitmap.CompressFormat.PNG, 100, stream);
        return Base64.encodeToString(stream.toByteArray(), Base64.NO_WRAP);
    }

    private static String extractMessage(String response) throws Exception {
        JSONObject root = new JSONObject(response);
        JSONArray choices = root.optJSONArray("choices");
        if (choices == null || choices.length() == 0) {
            return "";
        }

        JSONObject message = choices.getJSONObject(0).optJSONObject("message");
        if (message == null) {
            return "";
        }

        Object content = message.opt("content");
        if (content instanceof String) {
            return (String) content;
        }
        if (content instanceof JSONArray) {
            StringBuilder combined = new StringBuilder();
            JSONArray parts = (JSONArray) content;
            for (int i = 0; i < parts.length(); i++) {
                JSONObject part = parts.optJSONObject(i);
                if (part != null) {
                    combined.append(part.optString("text"));
                }
            }
            return combined.toString();
        }
        return "";
    }

    private static String readAll(InputStream stream) throws Exception {
        if (stream == null) {
            return "";
        }
        StringBuilder builder = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                builder.append(line);
            }
        }
        return builder.toString();
    }
}
