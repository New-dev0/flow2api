"""
Quick Image Generation Test - Simple version

Usage:
    python quick_test.py "your prompt here"
    
Example:
    python quick_test.py "A cute cat playing in the garden"
"""

import os
import sys
import json
import re
import aiohttp
import asyncio
import io

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Configuration
BASE_URL = os.getenv('FLOW2API_URL', 'http://localhost:18282')
API_ENDPOINT = f"{BASE_URL}/v1/chat/completions"
API_KEY = os.getenv('FLOW2API_API_KEY', 'PApiKey1800KOOOO')

async def quick_generate(prompt: str, model: str = 'gemini-2.5-flash-image-landscape'):
    """Quick image generation test"""
    print(f"Generating image with prompt: '{prompt}'")
    print(f"Model: {model}")
    print(f"Endpoint: {API_ENDPOINT}\n")
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    image_url = None
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_ENDPOINT, json=payload, headers=headers, timeout=300) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"Error {response.status}: {error_text}")
                    return None
                
                print("Streaming response...\n")
                
                async for line in response.content:
                    line_str = line.decode('utf-8').strip()
                    if not line_str or not line_str.startswith('data: '):
                        continue
                    
                    data_str = line_str[6:]
                    if data_str == '[DONE]':
                        break
                    
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        
                        if "reasoning_content" in delta:
                            content = delta['reasoning_content']
                            try:
                                print(content, end="", flush=True)
                            except UnicodeEncodeError:
                                # Fallback for encoding issues
                                print(content.encode('ascii', 'replace').decode('ascii'), end="", flush=True)
                        
                        if "content" in delta:
                            content_text = delta["content"]
                            img_match = re.search(r'!\[.*?\]\((.*?)\)', content_text)
                            if img_match:
                                image_url = img_match.group(1)
                                print(f"\n\nImage URL: {image_url}")
                    except json.JSONDecodeError:
                        continue
                
                if image_url:
                    print("\nDownloading image...")
                    async with session.get(image_url) as img_response:
                        if img_response.status == 200:
                            image_bytes = await img_response.read()
                            filename = "output.jpg"
                            with open(filename, 'wb') as f:
                                f.write(image_bytes)
                            print(f"Image saved to: {filename} ({len(image_bytes)} bytes)")
                            return image_bytes
                        else:
                            print(f"Download failed: {img_response.status}")
                            return None
                else:
                    print("\nNo image URL found")
                    return None
                    
    except Exception as e:
        print(f"\nError: {e}")
        return None

if __name__ == '__main__':
    if len(sys.argv) > 1:
        prompt = sys.argv[1]
    else:
        prompt = "一只可爱的猫咪在花园里玩耍"
    
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(quick_generate(prompt))
