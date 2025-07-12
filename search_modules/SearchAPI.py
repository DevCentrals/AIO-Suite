import requests
from typing import Optional, Dict, List

class SearchAPIProcessor:
    name = "Search-API - @ADSearchEngine_bot"
    developer = "@CPUCycle"

    @staticmethod
    def required_settings() -> List[str]:
        return ['search_api_key']

    def search(self, email: str, settings: Dict[str, str], proxy: str) -> Optional[Dict]:
        print(f"Processing {email} with SearchAPI")
        api_key = settings.get('search_api_key')
        if not api_key:
            raise ValueError("Search API key not found in settings")

        url = f'https://search-api.dev/search.php?email={email}&api_key={api_key}&extra_info=True'
        
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

            response.raise_for_status()
            
            if response.text == '{"error":"No data found."}':
                return None
                
            data = response.json()
            #print(data)
            
            addresses = data.get("addresses", [])
            address = ""
            if isinstance(addresses, list) and addresses:
                for addr in addresses:
                    if addr and addr.strip():
                        address = addr.strip()
                        break
            elif isinstance(addresses, str) and addresses.strip():
                address = addresses.strip()
            
            result = {
                'email': data.get("email", ""),
                'name': data.get("name", ""),
                'phone_numbers': data.get("numbers", []),
                'address': address,
                'dob': data.get("dob", ""),
            }
            #print(result)
            
            has_data = any([
                result['name'],
                result['address'],
                result['dob'],
                result['phone_numbers']
            ])
            
            if has_data:
                return result
            else:
                return None

        except requests.exceptions.RequestException as e:
            print(f"Error fetching details for {email}: {str(e)}")
            return None
        except Exception as e:
            print(f"Unexpected error for {email}: {str(e)}")
            return None

    def supports_email(self, email: str) -> bool:
        return True