import requests
from typing import Optional, Dict, List

class SearchAPIProcessor:
    name = "Search-API"
    developer = "@CPUCycle"

    @staticmethod
    def required_settings() -> List[str]:
        return ['search_api_key']

    async def search(self, email: str, settings: Dict[str, str], proxy: str) -> Optional[Dict]:
        api_key = settings.get('search_api_key')
        if not api_key:
            raise ValueError("Search API key not found in settings")

        url = f'https://search-api.dev/search.php?email={email}&api_key={api_key}'
        
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        }

        try:
            response = requests.get(
                url, 
                headers=headers, 
                timeout=30
            )
            print(response.text)
            response.raise_for_status()
            
            if response.text == '{"error":"No data found."}':
                return None
                
            data = response.json()
            
            result = {
                'email': data.get("email", ""),
                'name': data.get("name", ""),
                'phone_numbers': data.get("numbers", []),
                'address': data.get("address", ""),
                'dob': data.get("dob", ""),
            }
            
            return result

        except requests.exceptions.RequestException as e:
            print(f"Error fetching details for {email}: {str(e)}")
            return None
        except Exception as e:
            print(f"Unexpected error for {email}: {str(e)}")
            return None

    def supports_email(self, email: str) -> bool:
        return True