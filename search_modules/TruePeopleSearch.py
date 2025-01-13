from bs4 import BeautifulSoup
from typing import Optional, Dict, List
import time
from curl_cffi import CurlMime, requests

import re
import base64
import traceback

class SearchAPIProcessor:
    name = "TruePeopleSearch (CF-UAM + Turnstile)"
    developer = "@CPUCycle"

    @staticmethod
    def required_settings() -> List[str]:
        return ['capmonster_key']

    def convert_email(self, email):
        domain_map = {
            '@hotmail.com': 'cvxnfdjtyui',
            '@gmail.com': 'ertpoiqwertr',
            '@yahoo.com': 'fdgsdfjwert',
            '@icloud.com': 'ytowesdghtyow',
            '@outlook.com': 'ghoekcdktrmwd',
            '@aol.com': 'nmqwuisdfyure',
            '@live.com': 'dfsxczgirejdf'
        }

        local_part, domain = email.split('@', 1)
        domain = '@' + domain

        if domain in domain_map:
            converted_domain = domain_map[domain]
        else:
            domain_parts = domain[1:].split('.')
            
            if len(domain_parts) == 2:
                domain_name = domain_parts[0]
                domain_extension = domain_parts[1]
            else:
                domain_name = '_'.join(domain_parts[:-1])
                domain_extension = domain_parts[-1]

            converted_domain = f'_at_{domain_name}_dot_{domain_extension}'

        return local_part + converted_domain
    
    def clean_text(self, text):
        return re.sub(r'\s+', ' ', text.strip())
    
    async def search(self, email: str, settings: Dict[str, str], proxy: str) -> Optional[Dict]:
        print(f"Processing {email} with TruePeopleSearch")
        self.proxy = proxy
        self.CAPMON_KEY = settings.get('capmonster_key')
        if not self.CAPMON_KEY:
            raise ValueError("Capmonster key not found in settings")

        corrected_email = self.convert_email(email)
        session = requests.Session()

        session.timeout = 30
        session.proxies = {'http': self.proxy, 'https': self.proxy}

        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'priority': 'u=0, i',
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        }

        url = f'https://www.truepeoplesearch.com/resultemail?email={corrected_email}'
        response = session.get(url, headers=headers, impersonate="chrome124")
        htmlbase64 = base64.b64encode(response.text.encode()).decode()
        cf_clearance = self.get_captcha_solution(self.proxy, url, htmlbase64)
        session.cookies.set("cf_clearance", cf_clearance)
        response = session.get(url, headers=headers, impersonate="chrome124")
        
        if "internalcaptcha" in response.text or "Captcha" in response.text:
            print(f"Solving Internal Captcha")
            token = self.get_turnstile_solution()
            
            headers = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9,nl-NL;q=0.8,nl;q=0.7',
                'origin': 'https://www.truepeoplesearch.com',
                'priority': 'u=1, i',
                'referer': f'https://www.truepeoplesearch.com/InternalCaptcha?returnUrl=https%3a%2f%2fwww.truepeoplesearch.com%2fresultemail%3femail%3d{corrected_email}',
                'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                'sec-ch-ua-arch': '"x86"',
                'sec-ch-ua-bitness': '"64"',
                'sec-ch-ua-full-version': '"131.0.6778.264"',
                'sec-ch-ua-full-version-list': '"Google Chrome";v="131.0.6778.264", "Chromium";v="131.0.6778.264", "Not_A Brand";v="24.0.0.0"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-model': '""',
                'sec-ch-ua-platform': '"Windows"',
                'sec-ch-ua-platform-version': '"15.0.0"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'x-requested-with': 'XMLHttpRequest',
            }

            params = {
                'returnUrl': f'https://www.truepeoplesearch.com/resultemail?email={corrected_email}',
                'rrstamp': '0',
            }

            mp = CurlMime()
            mp.addpart(
                name="cf-turnstile-response",
                data=token,
            )
            mp.addpart(
                name="captchaToken",
                data=token,
            )

            response = session.post('https://www.truepeoplesearch.com/internalcaptcha/captchasubmit',params=params,headers=headers, multipart=mp, allow_redirects=False, impersonate="chrome124")
            if "Invalid captcha" in response.text:
                raise Exception("Turnstile Captcha Failed")
            #print(response.text)
            #print(response.headers)
            headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept-language': 'en-US,en;q=0.9',
                'priority': 'u=0, i',
                'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'none',
                'sec-fetch-user': '?1',
                'upgrade-insecure-requests': '1',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            }
            url = f'https://www.truepeoplesearch.com/resultemail?email={corrected_email}'
            response = session.get(url, headers=headers, impersonate="chrome124")
        if "Attention Required!" in response.text:
            raise Exception("Cloudflare Attack Protection")
        
        soup = BeautifulSoup(response.text, 'html.parser')

        div_element = soup.find('div', class_='card-summary')

        if div_element:
            data_detail_link = div_element.get('data-detail-link', '')
        else:
            print(f"{email} - No information available")

        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'priority': 'u=0, i',
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        }

        response = session.get(f'https://www.truepeoplesearch.com{data_detail_link}', headers=headers)
        #print(response.text)
        soup = BeautifulSoup(response.text, 'html.parser')

        h1_element = soup.find('h1', class_='oh1')

        age_span = soup.find('span', string=lambda x: x and 'Age' in x)
        age = age_span.text.split(',')[0].strip() if age_span else ''

        full_name = h1_element.text.strip()

        address_divs = soup.find_all('div', class_='col-12 col-sm-11 pl-sm-1')
        address, locality, region, postal_code, house_info = None, None, None, None, None

        for div in address_divs:
            address_header = div.find('div', class_='h5')
            if address_header and "Current Address" in address_header.text:
                address_div = div
                address = address_div.find('span', itemprop='streetAddress').text.strip()
                locality = address_div.find('span', itemprop='addressLocality').text.strip()
                region = address_div.find('span', itemprop='addressRegion').text.strip()
                postal_code = address_div.find('span', itemprop='postalCode').text.strip()
                house_info = address_div.find('div', class_='mt-1 dt-ln').text.strip().replace('\n', ' ')
                break

        phone_divs = soup.find_all('div', class_='col-12 col-md-6 mb-3')
        phone_numbers = []

        for div in phone_divs:
            phone_link = div.find('a', {'data-link-to-more': 'phone'})
            if phone_link:
                phone_number = phone_link.find('span', itemprop='telephone').text.strip()
                carrier = div.find('div', class_='mt-1 dt-ln').find_all('span', class_='dt-sb')[-1].text.strip()
                phone_numbers.append(f"{phone_number}")

        cleaned_age = self.clean_text(age).replace("Age ", "")
        cleaned_address = self.clean_text(address)
        cleaned_locality = self.clean_text(locality)
        cleaned_region = self.clean_text(region)
        cleaned_postal_code = self.clean_text(postal_code)
        formatted_address = f"{cleaned_address}, {cleaned_postal_code}, {cleaned_locality}, {cleaned_region}"
        
        return {
            'email': email,
            'name': full_name or None,
            'phone_numbers': phone_numbers,
            'address': formatted_address,
            'dob': cleaned_age or None,
        }

    def supports_email(self, email: str) -> bool:
        return True

    def get_captcha_solution(self, selected_proxy, url, htmlbase64):
        proxy_type, rest = selected_proxy.split("://")
        login_info, proxy_info = rest.split("@")
        proxy_login, proxy_password = login_info.split(":")
        proxy_address, proxy_port = proxy_info.split(":")
        while True:
            try:
                payload = {
                    "clientKey": self.CAPMON_KEY,
                    "task": {
                    "type":"TurnstileTask",
                    "websiteURL":url,
                    "websiteKey":"xxxxxxxxxx",
                    "cloudflareTaskType": "cf_clearance",
                    "htmlPageBase64": htmlbase64,
                    "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "proxyType": proxy_type,
                    "proxyAddress": proxy_address,
                    "proxyPort": int(proxy_port),
                    "proxyLogin": proxy_login,
                    "proxyPassword": proxy_password
                }
                }

                response = requests.post("https://api.capmonster.cloud/createTask", json=payload)
                #print(response.text)
                task_id = response.json().get("taskId")

                while True:
                    task_result_payload = {
                        "clientKey": self.CAPMON_KEY,
                        "taskId": task_id
                    }
                    response = requests.post("https://api.capmonster.cloud/getTaskResult", json=task_result_payload)
                    #print(response.text)

                    if response.status_code == 403:
                        print("Received a 403 error. Check your API key, task ID, or possible IP blocking.")
                        raise Exception

                    if "ERROR_" in response.text:
                        break

                    result = response.json().get("status")

                    if result == "ready":
                        cf_clearance = response.json().get("solution").get("cf_clearance")
                        return cf_clearance
                    time.sleep(1)
            except Exception as e:
                print(e)
                traceback.format_exc()
            
    def get_turnstile_solution(self):
        while True:
            try:
                payload = {
                    "clientKey": self.CAPMON_KEY,
                    "task": {
                        "type": "TurnstileTaskProxyless",
                        "websiteURL": "https://www.truepeoplesearch.com/",
                        "websiteKey": "0x4AAAAAAAmywfqBst8n7ro5"
                    }
                }

                response = requests.post("https://api.capmonster.cloud/createTask", json=payload)
                task_id = response.json().get("taskId")

                while True:
                    task_result_payload = {
                        "clientKey": self.CAPMON_KEY,
                        "taskId": task_id
                    }
                    response = requests.post("https://api.capmonster.cloud/getTaskResult", json=task_result_payload)
                    #print(response.text)
                    if response.status_code == 403:
                        #print("Received a 403 error. Check your API key, task ID, or possible IP blocking.")
                        raise Exception

                    if "ERROR_" in response.text:
                        print(f"Received Capmonster error {response.text}")
                        break

                    result = response.json().get("status")

                    if result == "ready":
                        token = response.json().get("solution").get("token")
                        return token
                    time.sleep(1)
            except Exception as e:
                #print(e)
                raise Exception