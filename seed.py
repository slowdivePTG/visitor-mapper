import httpx
import time

# A list of real public IP addresses from around the world
TEST_IPS = [
    "8.8.8.8",         # Mountain View, USA
    "210.130.1.1",     # Tokyo, Japan
    "177.43.255.255",  # Sao Paulo, Brazil
    "41.190.211.0",    # Cape Town, South Africa
    "114.114.114.114", # Nanjing, China
    "82.165.230.17",   # Berlin, Germany
    "139.130.4.5"      # Sydney, Australia
]

def seed_visitors():
    print("Sending mocked requests to local backend to test IP geolocation...")
    
    with httpx.Client() as client:
        for ip in TEST_IPS:
            print(f"Tracking IP: {ip} ... ", end="")
            try:
                # Spoof the X-Forwarded-For header to simulate a real visitor
                response = client.get(
                    "http://localhost:8000/api/track",
                    headers={"X-Forwarded-For": ip}
                )
                if response.status_code == 200 and response.json().get("status") == "success":
                    print("Success!")
                else:
                    print(f"Failed! Response: {response.text}")
            except httpx.ConnectError:
                print("\nError: Could not connect to the local server.")
                print("Make sure 'uvicorn main:app --reload' is running in another terminal.")
                return
            
            # Sleep briefly to avoid overwhelming the free ip-api.com endpoint
            time.sleep(1.5)

if __name__ == "__main__":
    seed_visitors()
