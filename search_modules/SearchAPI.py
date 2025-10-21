import requests
import json
from typing import Optional, Dict, List

class SearchAPIProcessor:
    name = "Search-API - @ADSearchEngine_bot"
    developer = "@CPUCycle"

    @staticmethod
    def required_settings() -> List[str]:
        return ['search_api_key', 'house_value']

    def search(self, email: str, settings: Dict[str, str], proxy: str) -> Optional[Dict]:
        print(f"Processing {email} with SearchAPI")
        api_key = settings.get('search_api_key')
        if not api_key:
            raise ValueError("Search API key not found in settings")

        # Check if house value features are enabled
        house_value_enabled = settings.get('house_value', 'false').lower() in ['true', '1', 'yes', 'on']
        
        # Build URL with house_value parameter
        url = f'https://search-api.dev/search.php?email={email}&api_key={api_key}&extra_info=True&house_value={"True" if house_value_enabled else "False"}'
        print(f"SearchAPI URL: {url}")
        
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
            print(f"SearchAPI raw data for {email}: {json.dumps(data, indent=2)}")
            
            # Extract basic information
            addresses = data.get("addresses", [])
            addresses_structured = data.get("addresses_structured", [])
            alternative_names = data.get("alternative_names", [])
            
            # Get primary address for backward compatibility
            address = ""
            if isinstance(addresses, list) and addresses:
                for addr in addresses:
                    if addr and addr.strip():
                        address = addr.strip()
                        break
            elif isinstance(addresses, str) and addresses.strip():
                address = addresses.strip()
            
            # Extract zestimate values and property details if house value is enabled
            zestimate_values = []
            property_details = []
            
            if house_value_enabled and addresses_structured:
                for addr_struct in addresses_structured:
                    if isinstance(addr_struct, dict) and 'components' in addr_struct:
                        components = addr_struct['components']
                        
                        # Extract zestimate
                        zestimate = components.get('zestimate')
                        if zestimate is not None:
                            zestimate_values.append(zestimate)
                        else:
                            zestimate_values.append(None)
                        
                        # Extract property details
                        prop_details = components.get('property_details', {})
                        if prop_details:
                            property_details.append(prop_details)
                        else:
                            property_details.append({})
                    else:
                        zestimate_values.append(None)
                        property_details.append({})
            
            result = {
                'email': data.get("email", ""),
                'name': data.get("name", ""),
                'phone_numbers': data.get("numbers", []),
                'address': address,
                'dob': data.get("dob", ""),
                'addresses_list': addresses if isinstance(addresses, list) else [addresses] if addresses else [],
                'addresses_structured': addresses_structured,
                'zestimate_values': zestimate_values,
                'property_details': property_details,
                'alternative_names': alternative_names,
                'house_value_enabled': house_value_enabled
            }
            
            print(f"SearchAPI processed result for {email}: {json.dumps(result, indent=2)}")
            
            has_data = any([
                result['name'],
                result['address'],
                result['dob'],
                result['phone_numbers'],
                result['addresses_list'],
                result['alternative_names']
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