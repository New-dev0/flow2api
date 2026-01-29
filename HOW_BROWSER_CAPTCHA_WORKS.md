# How Browser Mode Solves reCAPTCHA v3

## Overview

The browser mode uses **real browser automation** to obtain reCAPTCHA tokens by mimicking a real user visiting the Google Labs page.

## Step-by-Step Process

### 1. **Launch Real Browser**
```python
self.browser = await self.playwright.chromium.launch(**launch_options)
```
- Launches an actual Chromium browser instance
- Can be headless (no window) or headed (visible window)
- Browser has all normal features: cookies, localStorage, etc.

### 2. **Create Browser Context**
```python
context = await self.browser.new_context(
    viewport={'width': 1920, 'height': 1080},
    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...',
    locale='en-US',
    timezone_id='America/New_York'
)
```
- Creates an isolated browsing session
- Sets realistic browser fingerprint
- Configures viewport, user agent, locale

### 3. **Navigate to Google Labs Page**
```python
website_url = f"https://labs.google/fx/tools/flow/project/{project_id}"
await page.goto(website_url, wait_until="domcontentloaded", timeout=30000)
```
- Visits the actual Google Labs Flow project page
- Same URL a human would visit
- Loads all Google scripts and tracking

### 4. **Check for reCAPTCHA Script**
```javascript
if (window.grecaptcha && typeof window.grecaptcha.execute === 'function') {
    return true;
}
```
- Checks if Google's reCAPTCHA v3 script is already loaded on the page
- If not loaded, injects it manually

### 5. **Inject reCAPTCHA Script (if needed)**
```javascript
const script = document.createElement('script');
script.src = 'https://www.google.com/recaptcha/api.js?render={website_key}';
document.head.appendChild(script);
```
- Loads Google's official reCAPTCHA v3 library
- Uses the correct website key: `6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV`
- Waits for script to load and initialize

### 6. **Execute reCAPTCHA**
```javascript
window.grecaptcha.ready(() => {
    window.grecaptcha.execute('{website_key}', {
        action: 'FLOW_GENERATION'
    }).then((token) => {
        resolve(token);
    });
});
```
- Calls Google's `grecaptcha.execute()` function
- Specifies action: `'FLOW_GENERATION'`
- Google analyzes browser behavior and generates token

### 7. **Return Token**
```python
token = await page.evaluate(...)  # Returns: "03AL8dmw9Vm7d..."
return token
```
- Extracts the token from JavaScript
- Returns it to Python
- Token is valid for ~2 minutes

### 8. **Use Token in API Request**
```json
{
  "clientContext": {
    "recaptchaToken": "03AL8dmw9Vm7d...",
    "projectId": "...",
    "sessionId": "...",
    "tool": "PINHOLE"
  }
}
```
- Includes token in API request
- Google validates the token server-side
- If valid, request proceeds

## What reCAPTCHA v3 Checks

When `grecaptcha.execute()` runs, Google analyzes:

### Browser Signals
- ✅ Mouse movements and patterns
- ✅ Keyboard typing patterns
- ✅ Scroll behavior
- ✅ Touch events (mobile)
- ✅ Browser fingerprint (canvas, WebGL, fonts, etc.)
- ✅ Screen resolution and device type

### JavaScript Environment
- ✅ JavaScript execution timing
- ✅ DOM manipulation patterns
- ✅ Event listener behaviors
- ✅ Performance API data
- ✅ WebDriver detection (checks for automation)

### Network & Cookies
- ✅ Google cookies from previous visits
- ✅ IP address reputation
- ✅ Browser history signals
- ✅ TLS/SSL fingerprint
- ✅ HTTP header patterns

### Behavioral Analysis
- ✅ Time spent on page
- ✅ Interaction with page elements
- ✅ Navigation patterns
- ✅ Focus/blur events
- ✅ Tab visibility changes

## Why Browser Mode Works Better Than API Calls

### Traditional API Call (Without Browser)
```
❌ No mouse movements
❌ No keyboard events
❌ No scroll behavior
❌ Minimal browser fingerprint
❌ No Google cookies
❌ Obvious automation patterns
→ Low reCAPTCHA score → Rejected
```

### Browser Mode
```
✅ Real Chromium browser
✅ Natural browser fingerprint
✅ Can have Google cookies
✅ Realistic JavaScript environment
✅ Proper timing and events
✅ Harder to detect as automation
→ Higher reCAPTCHA score → Accepted
```

## reCAPTCHA v3 Scoring

Google assigns a **score from 0.0 to 1.0**:
- **0.9 - 1.0**: Very likely human
- **0.7 - 0.9**: Probably human
- **0.5 - 0.7**: Neutral
- **0.1 - 0.5**: Probably bot
- **0.0 - 0.1**: Definitely bot

Google Flow API likely requires score > 0.5 or 0.7

### What Affects Score

**Increases Score (Good):**
- ✅ Real browser with natural fingerprint
- ✅ Google account cookies present
- ✅ Normal mouse/keyboard patterns
- ✅ Good IP reputation
- ✅ Realistic timing

**Decreases Score (Bad):**
- ❌ Automation detected (WebDriver flag)
- ❌ Suspicious browser fingerprint
- ❌ Too-perfect timing (bot-like)
- ❌ VPN/proxy IP
- ❌ No cookies or history

## Headless vs Headed Mode

### Headless (headless=True) - Default
```python
self.headless = True
```
- ✅ No window shown (runs in background)
- ✅ Lower resource usage
- ✅ Works on servers without display
- ⚠️ Easier to detect (headless flag)
- ⚠️ Some fingerprints different

### Headed (headless=False)
```python
self.headless = False
```
- ✅ Shows actual browser window
- ✅ Harder to detect as automation
- ✅ Can debug visually
- ❌ Needs display (X11/Windows GUI)
- ❌ Can't run on headless servers

## Why It's Failing on Your System

### The NotImplementedError Issue

```
NotImplementedError at asyncio.base_events.py:503
```

**What's happening:**
1. Playwright tries to launch browser process
2. Uses `asyncio.create_subprocess_exec()`
3. Your event loop is `WindowsSelectorEventLoopPolicy`
4. SelectorEventLoop **doesn't support subprocesses** on Windows
5. Raises NotImplementedError

**The chain:**
```
browser_captcha.py
  → playwright.chromium.launch()
    → async_playwright.start()
      → asyncio.create_subprocess_exec()
        → WindowsSelectorEventLoopPolicy
          → ❌ NotImplementedError (no subprocess support)
```

## Browser Mode vs API Service

| Aspect | Browser Mode | API Service |
|--------|--------------|-------------|
| **How it works** | Launches real browser, executes grecaptcha | Sends captcha to service, they solve it |
| **Token generation** | Your machine | Their servers |
| **Detection risk** | Medium (automation detectable) | Low (they use residential IPs, real browsers) |
| **Cost** | Free | $1-3 per 1000 |
| **Reliability** | Depends on browser/system | Very reliable |
| **Speed** | 3-10 seconds | 10-30 seconds |
| **Setup** | Complex (Playwright, browsers) | Simple (just API key) |
| **Windows issues** | Yes (event loop problems) | No issues |

## What API Services Do

Services like YesCaptcha actually:
1. Receive your captcha parameters (website_key, URL, action)
2. Open the page in **real browsers on real devices**
3. Execute grecaptcha the same way
4. Often use **residential IPs** (home internet, not datacenter)
5. May use **browser extensions** to appear more human
6. Return the token to you

They essentially do the same thing as browser mode, but:
- On their infrastructure (residential networks)
- With better anti-detection
- At scale (thousands of browsers ready)

## Summary

**Browser Mode Process:**
```
Launch Browser → Visit Google Page → Load reCAPTCHA Script → 
Execute grecaptcha → Google Analyzes Behavior → Generate Token → 
Return Token → Use in API Request
```

**Why you need a real browser:**
- reCAPTCHA v3 runs JavaScript analysis
- Checks 100+ browser signals
- Needs realistic environment to pass
- Can't be done with simple HTTP requests

**Your issue:**
- Browser mode tries to launch browser subprocess
- Windows SelectorEventLoop doesn't support this
- Need to either:
  1. Fix event loop (ProactorEventLoop)
  2. Use API service instead

**Recommendation:**
Use API service - it does the same browser automation, but on their infrastructure without your system limitations!
