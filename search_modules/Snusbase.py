import requests
import ssl
import urllib3
from typing import Optional, Dict, List
from bs4 import BeautifulSoup
from colorama import Fore

class SearchAPIProcessor:
    name = "Snusbase.com"
    developer = "@CPUCycle"

    @staticmethod
    def required_settings() -> List[str]:
        return ['snusbase_api_key']

    def search(self, email: str, settings: Dict[str, str], proxy: str) -> Optional[Dict]:
        try:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            session = requests.Session()
            api_key = settings.get('snusbase_api_key')
            if not api_key:
                raise ValueError("Snusbase API key is missing in settings")

            response = session.post(
                "https://www.snusbase.com/search",
                data={"term": email, "searchtype": "email"},
                proxies={"http": proxy, "https": proxy} if proxy else None,
                verify=False
            )

            html_data = response.content

            name = "None"
            names = self.extract_all_key_values_from_html(html_data, 'xname')
            for nm in names:
                if all(char not in nm for char in '1234567890@.com'):
                    name = nm
                    break

            address = self.extract_single_key_value_from_html(html_data, 'xaddress')
            if address:
                for detail in ['xcity', 'xstate', 'xzip']:
                    extra = self.extract_single_key_value_from_html(html_data, detail)
                    if extra and extra != 'None':
                        address = f"{address}, {extra}"

            age = self.extract_single_key_value_from_html(html_data, 'xage')
            if not age:
                birthdate = self.extract_single_key_value_from_html(html_data, 'xbirthdate')
                if birthdate:
                    dobs = self.extract_all_key_values_from_html(html_data, 'xbirthdate')
                    for dob in dobs:
                        try:
                            year = int(dob.split('-')[0])
                            if year < 2010 and (2024 - year) < 100:
                                age = str(2024 - year)
                                break
                        except ValueError:
                            pass

            phones_found = self.extract_all_key_values_from_html(html_data, 'xphone')
            phones = [phone for phone in phones_found if "XX" not in phone and "**" not in phone and len(phone) <= 15]

            return {
                "email": email,
                "name": name,
                "phone_numbers": phones,
                "address": address,
                "age": age
            }

        except Exception as e:
            print(f"Error during search: {str(e)}")
            return None

    def supports_email(self, email: str) -> bool:
        return True

    @staticmethod
    def extract_all_key_values_from_html(html, target_class):
        soup = BeautifulSoup(html, 'html.parser')
        results = soup.find_all('td', class_=f'datatable {target_class}')
        return [result.get_text(strip=True) for result in results] if results else []

    @staticmethod
    def extract_single_key_value_from_html(html, target_class):
        soup = BeautifulSoup(html, 'html.parser')
        result = soup.find('td', class_=f'datatable {target_class}')
        return result.get_text(strip=True) if result else None
