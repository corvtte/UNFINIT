import asyncio
import os
import sys
sys.path.append(os.getcwd())

async def test_endpoint():
    from app import handle_crawler_rescrap_item
    
    payload = {"url": "https://abasmanesh.com/fa/take-it-easy-so-that-become-easy/"}
    res = handle_crawler_rescrap_item(payload)
    print("Endpoint result:", res)
        
if __name__ == "__main__":
    asyncio.run(test_endpoint())
