"""Test OpenMemory API connection"""
import requests

OPENMEMORY_URL = "http://localhost:8765"
USER_ID = "markus"

def test_list_memories():
    """Test listing memories for user"""
    try:
        params = {"user_id": USER_ID}
        r = requests.get(f"{OPENMEMORY_URL}/api/v1/memories/", params=params, timeout=5)
        print(f"[OK] List memories: {r.status_code}")
        data = r.json()
        print(f"   Found {len(data.get('results', []))} memories")
        return r.status_code == 200
    except Exception as e:
        print(f"[FAIL] List memories failed: {e}")
        return False

def test_add_memory():
    """Test adding a memory"""
    try:
        data = {
            "messages": [
                {"role": "user", "content": "OpenMemory test from botMaster v2.0 - Agent Orchestrator"}
            ],
            "user_id": USER_ID
        }
        r = requests.post(f"{OPENMEMORY_URL}/api/v1/memories/", json=data, timeout=10)
        print(f"[OK] Add memory: {r.status_code}")
        result = r.json()
        print(f"   Memory ID: {result.get('id', 'N/A')}")
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[FAIL] Add memory failed: {e}")
        return False

def test_search_memories():
    """Test searching memories"""
    try:
        params = {
            "query": "botMaster",
            "user_id": USER_ID
        }
        r = requests.get(f"{OPENMEMORY_URL}/api/v1/memories/search/", params=params, timeout=10)
        print(f"[OK] Search memories: {r.status_code}")
        results = r.json()
        print(f"   Found {len(results.get('results', []))} matches")
        return r.status_code == 200
    except Exception as e:
        print(f"[FAIL] Search memories failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing OpenMemory API Connection...\n")

    list_ok = test_list_memories()
    print()

    if list_ok:
        add_ok = test_add_memory()
        print()

        if add_ok:
            search_ok = test_search_memories()
            print()

            if search_ok:
                print("[SUCCESS] OpenMemory API fully functional!")
            else:
                print("[WARN] Search failed but basic API works")
        else:
            print("[WARN] Add failed but read API works")
    else:
        print("[FAIL] OpenMemory API not responding - check Docker")
