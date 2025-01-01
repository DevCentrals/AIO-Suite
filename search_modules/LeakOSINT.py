import requests, json, re
from typing import Optional, Dict

ZIP_PATTERN = r'\b\d{5}(-\d{4})?\b'
STREET_PATTERN = r'\d+\s+[A-Za-z]+(?:\s+[A-Za-z]+)*\s+(?:St|Street|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Rd|Road|Ln|Lane|Ct|Court|Pl|Place|Way|Terrace|Trail|Circle|Square|Pkwy|Parkway)'
CITY_STATE_PATTERN = r'\b(?:[A-Za-z\s]+(?:,?\s*[A-Za-z]{2})?)\b|(?:[A-Za-z]+(?:,\s?[A-Za-z]{2})?\s+\d{5}(-\d{4})?)'
STATE_ABBR_PATTERN = r'\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b'
COUNTRY_PATTERN = r'\b(US|Canada|United States|UK|United Kingdom|Australia|India|Germany|France|Mexico|Brazil|China|Japan|Russia|Italy|Spain|Argentina|South Africa|Singapore)\b'

BASE_SCORE = 1
STREET_SCORE = 3
CITY_STATE_SCORE = 2
ZIP_SCORE = 3
COUNTRY_SCORE = 2
LENGTH_SCORE = 1

class SearchAPIProcessor:
    name = "LeakOSINT"
    developer = "@CPUCycle"

    @staticmethod
    def required_settings() -> list:
        return ['leakosint_key']

    @staticmethod
    def address_score(address: str) -> int:
        score = 0

        if re.search(ZIP_PATTERN, address):
            score += ZIP_SCORE
        if re.search(STREET_PATTERN, address):
            score += STREET_SCORE
        if re.search(CITY_STATE_PATTERN, address):
            score += CITY_STATE_SCORE
        if re.search(STATE_ABBR_PATTERN, address):
            score += CITY_STATE_SCORE
        if re.search(COUNTRY_PATTERN, address):
            score += COUNTRY_SCORE
        if len(address.split()) > 6:
            score += LENGTH_SCORE
        
        return score

    @staticmethod
    def compare_addresses(address1: str, address2: str) -> str:
        score1 = SearchAPIProcessor.address_score(address1)
        score2 = SearchAPIProcessor.address_score(address2)
        
        if score1 > score2:
            return address1
        elif score2 > score1:
            return address2
        else:
            return address1

    @staticmethod
    def extract_details(json_response: dict) -> dict:
        details = {
            'name': None,
            'phone_numbers': [],
            'address': None,
            'age': None
        }

        address_details = {
            'address': None,
            'city': None,
            'zip': None,
            'country': None,
            'billing': None
        }

        phone_variations = ["phone", "phonenumber", "number", "mobile", "cellphone", "phone2", "cell", "contact"]
        name_variations = ["fullname", "name", "user", "username", "account", "id"]
        age_variations = ["age", "birthdate", "dob", "yearofbirth", "birthday"]

        address_variations = ["address", "street", "location"]
        city_variations = ["city", "town"]
        zip_variations = ["postcode", "zipcode", "postal", "zip"]
        country_variations = ["country", "countrycode", "region"]
        billing_variations = ["billing", "billing address"]

        for entry, data in json_response.get('List', {}).items():
            for record in data.get('Data', []):
                record_lower = {key.lower(): value for key, value in record.items()}

                if not details['name']:
                    for name_key in name_variations:
                        if name_key in record_lower:
                            try:
                                details['name'] = record_lower[name_key].upper()
                                break
                            except:
                                pass

                if not details['phone_numbers']:
                    for phone_key in phone_variations:
                        if phone_key in record_lower:
                            phone = record_lower[phone_key]
                            if phone and "XX" not in phone and "**" not in phone:
                                try:
                                    int(phone.replace("+", ""))
                                    if 4 < len(phone) < 15:
                                        details['phone_numbers'].append(phone)
                                except:
                                    pass

                if not address_details['address']:
                    for addr_key in address_variations:
                        if addr_key in record_lower:
                            address_details['address'] = record_lower[addr_key]
                            break

                if not address_details['city']:
                    for addr_key in city_variations:
                        if addr_key in record_lower:
                            address_details['city'] = record_lower[addr_key]
                            break

                if not address_details['zip']:
                    for addr_key in zip_variations:
                        if addr_key in record_lower:
                            address_details['zip'] = record_lower[addr_key]
                            break

                if not address_details['country']:
                    for addr_key in country_variations:
                        if addr_key in record_lower:
                            address_details['country'] = record_lower[addr_key]
                            break

                for addr_key in billing_variations:
                    if addr_key in record_lower:
                        address_details['billing'] = record_lower[addr_key]
                        break

                if not details['age']:
                    for age_key in age_variations:
                        if age_key in record_lower:
                            birthdate = record_lower.get(age_key)
                            if birthdate and birthdate != 'NULL':
                                try:
                                    birth_year = int(birthdate.split('-')[0]) if '-' in birthdate else int(birthdate)
                                    details['age'] = 2024 - birth_year
                                except:
                                    pass

        address1 = ', '.join(sorted(set(value for value in [address_details['address'], address_details['city'], address_details['country']] if value is not None)))
        if address_details['zip'] and address_details['zip'] not in address1:
            address1 = f"{address1} {address_details['zip']}"

        details['address'] = SearchAPIProcessor.compare_addresses(address1, address_details['billing'] or '')
        details['address'] = details['address'].replace('  ', ' ')
        return details

    async def search(self, email: str, settings: Dict[str, str], proxy: Optional[str] = None) -> Optional[Dict]:
        try:
            leakosint_key = settings.get('leakosint_key')
            if not leakosint_key:
                raise ValueError("API key is missing in settings")

            data = {"token": leakosint_key, "request": f"{email}", "limit": 600, "lang": "en", "type": "json"}
            url = 'https://leakosintapi.com/'

            while True:
                try:
                    response = requests.post(url, json=data, proxies={'http': proxy, 'https': proxy})
                    break
                except Exception as e:
                    print(f"Error during request: {e}")
                    return None

            if 'error' in response.json() and 'You are running too many queries' in response.json()['error']:
                raise Exception("Ratelimited!")

            results = SearchAPIProcessor.extract_details(response.json())
            return results

        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return None