import requests
import json

def test_api(symbol, detay=False):
    """Test the chatbot API with the given symbol and detay parameter."""
    url = f"https://tdx-api.onrender.com/chatbot?symbol={symbol}"
    if detay:
        url += "&detay=true"
    
    print(f"Testing API with URL: {url}")
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {data['response'][:100]}...")  # Print first 100 chars
            return True
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Exception: {e}")
        return False

if __name__ == "__main__":
    # Test with normal request
    print("\n=== Testing normal request ===")
    test_api("THYAO.IS", False)
    
    # Test with detailed request
    print("\n=== Testing detailed request ===")
    test_api("THYAO.IS", True)
    
    # Test with symbol without .IS
    print("\n=== Testing symbol without .IS ===")
    test_api("THYAO", False)
    
    # Test with symbol without .IS and detailed request
    print("\n=== Testing symbol without .IS and detailed request ===")
    test_api("THYAO", True) 