# reCAPTCHA Interceptor Analysis

## What This Script Does

This is a **browser extension content script** that runs in the page context of `labs.google` to intercept and inject fresh reCAPTCHA tokens into API requests.

## Key Features

### 1. **Uses reCAPTCHA Enterprise (Not v3!)**

```javascript
const RECAPTCHA_SITE_KEY = "6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV";

// Uses grecaptcha.enterprise, not grecaptcha.execute!
const token = await grecaptcha.enterprise.execute(RECAPTCHA_SITE_KEY, {
  action: "FLOW_GENERATION"
});
```

**This is important:** Google Flow uses **reCAPTCHA Enterprise**, not regular reCAPTCHA v3!

### 2. **Message-based Token Generation**

The script listens for messages from the extension:

```javascript
window.addEventListener("message", async (event) => {
  if (event.data?.type === "veo_requestRecaptchaToken") {
    const token = await getReCaptchaToken(action);
    window.postMessage({
      type: "veo_recaptchaToken",
      token: token,
      success: !!token
    }, "*");
  }
});
```

This allows a browser extension to request tokens on-demand.

### 3. **Proxy API Calls with Fresh Tokens**

Most importantly, it can make API calls with fresh reCAPTCHA tokens:

```javascript
if (event.data?.type === "veo_proxyApiCall") {
  // Get fresh reCAPTCHA token
  const freshToken = await getReCaptchaToken("FLOW_GENERATION");
  
  // Update payload with NEW FORMAT
  payload.clientContext.recaptchaContext = {
    token: freshToken,
    applicationType: "RECAPTCHA_APPLICATION_TYPE_WEB"
  };
  
  // Generate fresh sessionId
  payload.clientContext.sessionId = `;${Date.now()}`;
  
  // Make API call
  const response = await originalFetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "text/plain;charset=UTF-8",
      Authorization: bearerToken
    },
    body: JSON.stringify(payload)
  });
}
```

### 4. **NEW Token Format Discovery!**

This script reveals that Google changed the token format:

**OLD FORMAT (what we're using):**
```json
{
  "clientContext": {
    "recaptchaToken": "token-here"
  }
}
```

**NEW FORMAT (what Google Flow actually uses):**
```json
{
  "clientContext": {
    "recaptchaContext": {
      "token": "token-here",
      "applicationType": "RECAPTCHA_APPLICATION_TYPE_WEB"
    }
  }
}
```

### 5. **Uses text/plain Content-Type**

Notice this comment:
```javascript
// Use text/plain as per labs.google cURL (NOT application/json!)
headers: {
  "Content-Type": "text/plain;charset=UTF-8"
}
```

## How It Works

```
Browser Extension
      ↓
[1] Injects interceptor.js into labs.google page
      ↓
[2] Extension sends message: "veo_proxyApiCall"
      ↓
[3] Interceptor runs: grecaptcha.enterprise.execute()
      ↓
[4] Google analyzes page behavior and returns token
      ↓
[5] Interceptor injects token into payload
      ↓
[6] Interceptor makes API call with originalFetch
      ↓
[7] Returns result to extension
```

## Why This Approach Works Better

1. **Runs in actual Google page context** - Has access to grecaptcha.enterprise
2. **Uses Enterprise API** - More reliable than v3
3. **Fresh tokens every time** - Generated on-demand
4. **Correct format** - Uses new recaptchaContext format
5. **No subprocess issues** - Runs in existing browser tab

## Implications for Our Code

### Problem 1: We're using reCAPTCHA v3, not Enterprise!

Our code uses:
```javascript
window.grecaptcha.execute(websiteKey, { action: 'FLOW_GENERATION' })
```

Should be:
```javascript
window.grecaptcha.enterprise.execute(websiteKey, { action: 'FLOW_GENERATION' })
```

### Problem 2: Wrong token format!

We're sending:
```json
{
  "clientContext": {
    "recaptchaToken": "token"
  }
}
```

Google expects:
```json
{
  "clientContext": {
    "recaptchaContext": {
      "token": "token",
      "applicationType": "RECAPTCHA_APPLICATION_TYPE_WEB"
    }
  }
}
```

### Problem 3: Wrong Content-Type

We're using: `application/json`
Should be: `text/plain;charset=UTF-8`

## How to Apply This to Our Code

We need to update:

1. **browser_captcha.py** - Use grecaptcha.enterprise
2. **flow_client.py** - Update token format and Content-Type

This explains why we're getting 403 - we're using the wrong API and wrong format!
