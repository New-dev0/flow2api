"""
Direct API Function Test
Tests the Flow API generate_image function directly with detailed logging

Usage:
    python test_generate_api.py
"""

import asyncio
import sys
import os
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.database import Database
from src.services.flow_client import FlowClient
from src.services.proxy_manager import ProxyManager
from src.services.token_manager import TokenManager
from src.core.config import config

def print_section(title):
    """Print section header"""
    print("\n" + "="*80)
    print(f" {title}")
    print("="*80 + "\n")

def print_json(data, title=""):
    """Print JSON data in formatted way"""
    if title:
        print(f"\n{title}:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

async def test_generate_image_api():
    """Test the generate_image API directly"""
    
    print_section("Direct Flow API Test - generate_image")
    
    # Initialize services
    print("[1/6] Initializing database...")
    db = Database()
    await db.init_db()
    
    print("[2/6] Initializing proxy manager...")
    proxy_manager = ProxyManager(db)
    
    print("[3/6] Initializing Flow client...")
    flow_client = FlowClient(proxy_manager, db)
    
    print("[4/6] Initializing token manager...")
    token_manager = TokenManager(db, flow_client)
    
    print("[5/6] Loading tokens from database...")
    tokens = await db.get_all_tokens()
    
    if not tokens:
        print("\nERROR: No tokens found in database!")
        return
    
    print(f"Found {len(tokens)} token(s)")
    
    # Find an active token with valid AT
    active_token = None
    for token in tokens:
        if token.is_active and token.at:
            print(f"\nUsing Token: {token.email} (ID: {token.id})")
            print(f"  Active: {token.is_active}")
            print(f"  Credits: {token.credits}")
            print(f"  Tier: {token.user_paygate_tier}")
            print(f"  Project ID: {token.current_project_id}")
            
            # Check if AT is valid
            from datetime import timezone
            if token.at_expires:
                now = datetime.now(timezone.utc)
                at_expires = token.at_expires
                if at_expires.tzinfo is None:
                    at_expires = at_expires.replace(tzinfo=timezone.utc)
                
                if now < at_expires:
                    remaining = at_expires - now
                    print(f"  AT expires in: {remaining.total_seconds()/3600:.1f} hours")
                    active_token = token
                    break
                else:
                    print(f"  AT EXPIRED!")
            else:
                print(f"  AT expiry not set")
    
    if not active_token:
        print("\nERROR: No active token with valid AT found!")
        print("\nTrying to refresh AT for first token...")
        
        if tokens:
            token = tokens[0]
            print(f"Attempting to refresh AT for: {token.email}")
            
            try:
                # Test ST to AT conversion
                result = await flow_client.st_to_at(token.st)
                print(f"OK: ST is valid")
                
                # Update token with new AT
                new_at = result['access_token']
                print(f"New AT: {new_at[:30]}...")
                
                # Update token in database
                await db.update_token(
                    token.id,
                    at=new_at,
                    at_expires=datetime.fromisoformat(result['expires'].replace('Z', '+00:00'))
                )
                
                # Reload token
                active_token = await db.get_token(token.id)
                print(f"OK: Token AT refreshed successfully")
                
            except Exception as e:
                print(f"FAIL: Could not refresh AT: {e}")
                return
    
    print("\n[6/6] Testing image generation API...")
    
    # Ensure project exists
    if not active_token.current_project_id:
        print("\nCreating project...")
        try:
            project_id = await flow_client.create_project(
                active_token.st,
                f"Test Project {datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            print(f"OK: Project created: {project_id}")
            
            # Update token
            await db.update_token(active_token.id, current_project_id=project_id)
            active_token = await db.get_token(active_token.id)
            
        except Exception as e:
            print(f"FAIL: Could not create project: {e}")
            return
    
    project_id = active_token.current_project_id
    print(f"\nUsing Project ID: {project_id}")
    
    # Test parameters
    test_cases = [
        {
            "name": "Simple landscape image",
            "prompt": "A beautiful sunset over mountains",
            "model_name": "GEM_PIX",
            "aspect_ratio": "IMAGE_ASPECT_RATIO_LANDSCAPE",
            "image_inputs": []
        },
        {
            "name": "Simple portrait image",
            "prompt": "A cute cat sitting on a windowsill",
            "model_name": "GEM_PIX",
            "aspect_ratio": "IMAGE_ASPECT_RATIO_PORTRAIT",
            "image_inputs": []
        }
    ]
    
    for idx, test_case in enumerate(test_cases, 1):
        print_section(f"Test Case #{idx}: {test_case['name']}")
        
        print("Request Parameters:")
        print(f"  Prompt: {test_case['prompt']}")
        print(f"  Model: {test_case['model_name']}")
        print(f"  Aspect Ratio: {test_case['aspect_ratio']}")
        print(f"  Image Inputs: {len(test_case['image_inputs'])} images")
        print(f"  Project ID: {project_id}")
        print(f"  AT Token: {active_token.at[:30]}...")
        
        try:
            print("\nCalling flow_client.generate_image()...")
            start_time = asyncio.get_event_loop().time()
            
            result = await flow_client.generate_image(
                at=active_token.at,
                project_id=project_id,
                prompt=test_case['prompt'],
                model_name=test_case['model_name'],
                aspect_ratio=test_case['aspect_ratio'],
                image_inputs=test_case['image_inputs']
            )
            
            end_time = asyncio.get_event_loop().time()
            duration_ms = int((end_time - start_time) * 1000)
            
            print(f"\nOK: API call succeeded in {duration_ms}ms")
            
            # Print full response
            print_section("Full API Response")
            print_json(result, "Response JSON")
            
            # Extract and display image URL
            print_section("Extracted Data")
            
            media = result.get("media", [])
            if media:
                print(f"Number of media items: {len(media)}")
                
                for media_idx, media_item in enumerate(media, 1):
                    print(f"\nMedia #{media_idx}:")
                    
                    if "image" in media_item:
                        image_data = media_item["image"]
                        
                        if "generatedImage" in image_data:
                            gen_image = image_data["generatedImage"]
                            
                            print(f"  Image URL: {gen_image.get('fifeUrl', 'N/A')}")
                            print(f"  Image ID: {gen_image.get('name', 'N/A')}")
                            print(f"  Width: {gen_image.get('width', 'N/A')}")
                            print(f"  Height: {gen_image.get('height', 'N/A')}")
                            
                            if 'metadata' in gen_image:
                                metadata = gen_image['metadata']
                                print(f"  Metadata: {json.dumps(metadata, indent=4)}")
                
                print("\nOK: Image generated successfully!")
                
            else:
                print("WARNING: No media items in response")
                
            # Check remaining credits
            remaining = result.get("remainingCredits")
            if remaining is not None:
                print(f"\nRemaining Credits: {remaining}")
            
        except Exception as e:
            print(f"\nFAIL: API call failed")
            print(f"Error Type: {type(e).__name__}")
            print(f"Error Message: {str(e)}")
            
            # Print detailed error info
            import traceback
            print("\nFull Traceback:")
            print(traceback.format_exc())
            
            # Try to extract response details if available
            if hasattr(e, '__dict__'):
                print("\nError Details:")
                for key, value in e.__dict__.items():
                    print(f"  {key}: {value}")
        
        # Pause between tests
        if idx < len(test_cases):
            print("\nWaiting 3 seconds before next test...")
            await asyncio.sleep(3)
    
    print_section("Test Complete")

if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(test_generate_image_api())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
