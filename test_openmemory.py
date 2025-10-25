"""Test OpenMemory SSE connection"""
import requests

OPENMEMORY_URL = "http://localhost:8765"
USER_ID = "markus"
API_KEY = "local-dev-key"

def test_health():
    """Test if OpenMemory API is responding"""
    try:
        r = requests.get(f"{OPENMEMORY_URL}/health", timeout=5)
        print(f"[OK] Health check: {r.status_code}")
        print(f"   Response: {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"[FAIL] Health check failed: {e}")
        return False

def test_add_memory():
    """Test adding a memory via API"""
    try:
        headers = {"Content-Type": "application/json"}
        data = {
            "messages": [{"role": "user", "content": "Test memory from botMaster v2.0"}],
            "user_id": USER_ID,
            "metadata": {"source": "botmaster_test"}
        }
        r = requests.post(
            f"{OPENMEMORY_URL}/v1/memories",
            headers=headers,
            json=data,
            timeout=10
        )
        print(f"[OK] Add memory: {r.status_code}")
        print(f"   Response: {r.json()}")
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[FAIL] Add memory failed: {e}")
        return False

def test_search_memory():
    """Test searching memories"""
    try:
        params = {
            "query": "botMaster",
            "user_id": USER_ID
        }
        r = requests.get(f"{OPENMEMORY_URL}/v1/memories/search", params=params, timeout=10)
        print(f"[OK] Search memory: {r.status_code}")
        results = r.json()
        print(f"   Found {len(results.get('results', []))} memories")
        return r.status_code == 200
    except Exception as e:
        print(f"[FAIL] Search memory failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing OpenMemory Connection...\n")

    health_ok = test_health()
    print()

    if health_ok:
        add_ok = test_add_memory()
        print()

        if add_ok:
            search_ok = test_search_memory()
            print()

            if search_ok:
                print("[SUCCESS] OpenMemory Connection WORKING!")
            else:
                print("[WARN] Search failed but API is responding")
        else:
            print("[WARN] Add memory failed but API is responding")
    else:
        print("[FAIL] OpenMemory API not responding - check Docker containers")
