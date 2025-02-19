from bs4 import BeautifulSoup
from typing import Optional, Dict, List
import time
import requests
from curl_cffi import requests
import json
import collections
collections.Callable = collections.abc.Callable
import logging
import time
from requests.packages.urllib3.exceptions import InsecureRequestWarning

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1

class SearchAPIProcessor:
    name = "CyberBackgroundChecks.com"
    developer = "@CPUCycle"

    @staticmethod
    def required_settings() -> List[str]:
        return []
    
    async def search(self, email: str, settings: Dict[str, str], proxy: str) -> Optional[Dict]:
        print(f"Processing {email} with CyberBackgroundChecks")
        self.proxy = proxy
        
        session = requests.Session()
        session.proxies = {'http': proxy, 'https': proxy}
        response, details = self.get_details(session, email)

        fullname = ''
        phone_numbers = []
        age = ''
        address = ''

        if details:
            fullname = details['name']
            other_phone_numbers = details.get('telephone', [])
            if isinstance(other_phone_numbers, str):
                phone_numbers.append(f'"{other_phone_numbers}"')
            else:
                phone_numbers.extend([f'"{number}"' for number in other_phone_numbers])
            soup = BeautifulSoup(response.text, 'html.parser')
            age_span = soup.find('span', class_='age')
            age = age_span.get_text() if age_span else ''

            address = f"{details['address'][0]['streetAddress']} {details['address'][0]['addressLocality']} {details['address'][0]['addressRegion']} {details['address'][0]['postalCode']}"

            output = f"{email} | \"{fullname}\" | [{', '.join(phone_numbers)}] | {address} | Age: {age}"
            print(output)
            return {
                'email': email,
                'name': fullname or None,
                'phone_numbers': phone_numbers,
                'address': address,
                'dob': age or None,
            }
            
        else:
            logging.info(f"{email}: Failed to retrieve information")
            return None
            
    def get_details(self, session, email, retries=MAX_RETRIES):
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9,nl-NL;q=0.8,nl;q=0.7',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'priority': 'u=0, i',
            'referer': 'https://www.cyberbackgroundchecks.com/email',
            'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
            'sec-ch-ua-arch': '"x86"',
            'sec-ch-ua-bitness': '"64"',
            'sec-ch-ua-full-version': '"133.0.6943.98"',
            'sec-ch-ua-full-version-list': '"Not(A:Brand";v="99.0.0.0", "Google Chrome";v="133.0.6943.98", "Chromium";v="133.0.6943.98"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"19.0.0"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        }

        try:
            response = session.get(f'https://www.cyberbackgroundchecks.com/email/{email.replace("@", "_.")}', headers=headers, impersonate="chrome133a")
            #print(response.text)
            if "Just a moment..." in response.text:
                raise Exception("Cloudflare")
            #print(response.text)

            if response.status_code == 200 and '[{"@context":"http://schema.org","@type":"Person"' in response.text:
                details = json.loads('[{"@context":"http://schema.org","@type":"Person"' +
                                    response.text.split('[{"@context":"http://schema.org","@type":"Person"')[1].split('\n')[0])[0]

                return response, details

            elif response.status_code == 403 and retries > 0:
                raise Exception("[CBC] - 403")

            elif response.status_code == 503 and retries > 0:
                raise Exception("[CBC] - 503")

            else:
                return None, None

        except requests.exceptions.RequestException as e:
            raise Exception