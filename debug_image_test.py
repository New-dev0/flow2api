"""
Debug Image Generation Test
Tests the image generation flow with detailed debugging output

This script tests:
1. Token validation and AT refresh
2. Project creation/validation
3. Image generation API call
4. Response parsing

Usage:
    python debug_image_test.py

Environment:
    Set FLOW2API_URL and FLOW2API_API_KEY if needed
"""

import os
import sys
import json
import aiohttp
import asyncio
import io
import traceback
from datetime import datetime

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Configuration
BASE_URL = os.getenv('FLOW2API_URL', 'http://localhost:18282')
API_ENDPOINT = f"{BASE_URL}/v1/chat/completions"
API_KEY = os.getenv('FLOW2API_API_KEY', 'PApiKey1800KOOOO')

# Test configurations
TEST_CASES = [
    {
        "name": "Simple Text Prompt - Landscape",
        "model": "gemini-2.5-flash-image-landscape",
        "prompt": "A beautiful sunset over mountains",
        "stream": True
    },
    {
        "name": "Simple Text Prompt - Portrait",
        "model": "gemini-2.5-flash-image-portrait",
        "prompt": "A cute cat sitting on a windowsill",
        "stream": True
    },
    {
        "name": "Chinese Prompt - Landscape",
        "model": "gemini-2.5-flash-image-landscape",
        "prompt": "一只可爱的猫咪在花园里玩耍",
        "stream": True
    }
]

class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log_info(message: str):
    """Log info message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{Colors.OKCYAN}[{timestamp}] ℹ {message}{Colors.ENDC}")

def log_success(message: str):
    """Log success message"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{Colors.OKGREEN}[{timestamp}] ✓ {message}{Colors.ENDC}")

def log_error(message: str):
    """Log error message"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{Colors.FAIL}[{timestamp}] ✗ {message}{Colors.ENDC}")

def log_warning(message: str):
    """Log warning message"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{Colors.WARNING}[{timestamp}] ⚠ {message}{Colors.ENDC}")

def log_section(message: str):
    """Log section header"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{message}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*80}{Colors.ENDC}\n")

async def test_image_generation(test_config: dict) -> dict:
    """
    Test image generation with detailed debugging
    
    Returns:
        dict with test results including success/failure status and details
    """
    test_name = test_config["name"]
    model = test_config["model"]
    prompt = test_config["prompt"]
    stream = test_config["stream"]
    
    log_section(f"Test: {test_name}")
    log_info(f"Model: {model}")
    log_info(f"Prompt: {prompt}")
    log_info(f"Stream: {stream}")
    log_info(f"Endpoint: {API_ENDPOINT}")
    
    result = {
        "test_name": test_name,
        "success": False,
        "error": None,
        "image_url": None,
        "reasoning_messages": [],
        "response_status": None,
        "response_time_ms": None
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": stream
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    start_time = asyncio.get_event_loop().time()
    
    try:
        async with aiohttp.ClientSession() as session:
            log_info("Sending request to API...")
            
            async with session.post(
                API_ENDPOINT, 
                json=payload, 
                headers=headers, 
                timeout=aiohttp.ClientTimeout(total=300)
            ) as response:
                result["response_status"] = response.status
                
                if response.status != 200:
                    error_text = await response.text()
                    log_error(f"HTTP Error {response.status}")
                    log_error(f"Response: {error_text}")
                    result["error"] = f"HTTP {response.status}: {error_text}"
                    return result
                
                log_success(f"Response status: {response.status}")
                
                if stream:
                    log_info("Processing streaming response...")
                    chunk_count = 0
                    
                    async for line in response.content:
                        line_str = line.decode('utf-8').strip()
                        if not line_str or not line_str.startswith('data: '):
                            continue
                        
                        data_str = line_str[6:]
                        if data_str == '[DONE]':
                            log_info("Stream complete (received [DONE])")
                            break
                        
                        try:
                            chunk = json.loads(data_str)
                            chunk_count += 1
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            
                            # Process reasoning_content (progress messages)
                            if "reasoning_content" in delta:
                                content = delta['reasoning_content']
                                result["reasoning_messages"].append(content)
                                log_info(f"Progress: {content.strip()}")
                            
                            # Process content (final result)
                            if "content" in delta:
                                content_text = delta["content"]
                                log_info(f"Content: {content_text}")
                                
                                # Try to extract image URL from markdown
                                import re
                                img_match = re.search(r'!\[.*?\]\((.*?)\)', content_text)
                                if img_match:
                                    image_url = img_match.group(1)
                                    result["image_url"] = image_url
                                    log_success(f"Found image URL: {image_url}")
                                    result["success"] = True
                                
                        except json.JSONDecodeError as e:
                            log_warning(f"Failed to decode chunk: {e}")
                            continue
                    
                    log_info(f"Total chunks received: {chunk_count}")
                    
                    if not result["image_url"]:
                        log_error("No image URL found in response")
                        result["error"] = "No image URL found in response"
                        # Log all reasoning messages for debugging
                        log_warning("Reasoning messages received:")
                        for msg in result["reasoning_messages"]:
                            print(f"  - {msg}")
                
                else:
                    # Non-streaming response
                    response_json = await response.json()
                    log_info(f"Non-streaming response: {json.dumps(response_json, indent=2, ensure_ascii=False)}")
                    
                    # Extract content from response
                    choices = response_json.get("choices", [])
                    if choices:
                        message = choices[0].get("message", {})
                        content = message.get("content", "")
                        log_info(f"Content: {content}")
                
        end_time = asyncio.get_event_loop().time()
        result["response_time_ms"] = int((end_time - start_time) * 1000)
        log_info(f"Total time: {result['response_time_ms']}ms")
        
    except asyncio.TimeoutError:
        log_error("Request timed out")
        result["error"] = "Request timeout"
    except Exception as e:
        log_error(f"Exception: {type(e).__name__}: {str(e)}")
        log_error(f"Traceback:\n{traceback.format_exc()}")
        result["error"] = f"{type(e).__name__}: {str(e)}"
    
    return result

async def run_all_tests():
    """Run all test cases"""
    log_section("Starting Debug Image Generation Tests")
    log_info(f"Base URL: {BASE_URL}")
    log_info(f"API Key: {API_KEY[:20]}..." if len(API_KEY) > 20 else API_KEY)
    
    results = []
    
    for test_config in TEST_CASES:
        result = await test_image_generation(test_config)
        results.append(result)
        
        # Pause between tests
        if test_config != TEST_CASES[-1]:
            await asyncio.sleep(2)
    
    # Summary
    log_section("Test Results Summary")
    
    passed = sum(1 for r in results if r["success"])
    failed = len(results) - passed
    
    print(f"{Colors.BOLD}Total Tests: {len(results)}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}Passed: {passed}{Colors.ENDC}")
    print(f"{Colors.FAIL}Failed: {failed}{Colors.ENDC}\n")
    
    for result in results:
        status_icon = "✓" if result["success"] else "✗"
        status_color = Colors.OKGREEN if result["success"] else Colors.FAIL
        
        print(f"{status_color}{status_icon} {result['test_name']}{Colors.ENDC}")
        
        if result["success"]:
            print(f"  Image URL: {result['image_url']}")
            print(f"  Response Time: {result['response_time_ms']}ms")
        else:
            print(f"  Error: {result['error']}")
        
        if result["response_status"]:
            print(f"  HTTP Status: {result['response_status']}")
        
        print()
    
    # Error Analysis
    if failed > 0:
        log_section("Error Analysis")
        
        for result in results:
            if not result["success"]:
                print(f"{Colors.FAIL}Test: {result['test_name']}{Colors.ENDC}")
                print(f"Error: {result['error']}")
                
                if result["reasoning_messages"]:
                    print(f"\nProgress messages before failure:")
                    for msg in result["reasoning_messages"]:
                        print(f"  - {msg}")
                
                print("\nPossible causes:")
                if "403" in str(result["error"]):
                    print("  1. Invalid or expired access token (AT)")
                    print("  2. Invalid session token (ST)")
                    print("  3. reCAPTCHA token validation failed")
                    print("  4. Project ID is invalid or not accessible")
                    print("  5. Account permissions issue")
                elif "No image URL" in str(result["error"]):
                    print("  1. API returned empty response")
                    print("  2. Response format changed")
                    print("  3. Generation failed silently")
                elif "timeout" in str(result["error"]).lower():
                    print("  1. Server is not responding")
                    print("  2. Generation taking too long")
                    print("  3. Network connectivity issue")
                
                print()
    
    return results

if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        results = asyncio.run(run_all_tests())
        
        # Exit with appropriate code
        failed = sum(1 for r in results if not r["success"])
        sys.exit(0 if failed == 0 else 1)
        
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Tests interrupted by user{Colors.ENDC}")
        sys.exit(130)
