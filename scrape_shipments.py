import datetime
import os
import smtplib
from collections import defaultdict
from email.mime.text import MIMEText
from typing import List, Dict, Set

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests

LOGIN_URL = (
    "https://auth.gln.com/IdentityService/login?appId=526789C9-0A46-488A-AF55-289458F78EFD&"
    "returnUrl=https://coach.pcstrac.com/getGlnSSO.php&tenant=coach"
)
USERNAME = os.getenv("COACH_USERNAME", "Coh4501")
PASSWORD = os.getenv("COACH_PASSWORD", "Coach1181")

UPS_TRACKING_API_URL = "https://onlinetools.ups.com/track/v1/details/{tracking_number}"
# Replace with a valid UPS API key/token
UPS_API_KEY = os.getenv("UPS_API_KEY", "YOUR_UPS_API_KEY")

EMAIL_TO = "creativeappmaking@gmail.com"
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))


class CoachScraper:
    def __init__(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 20)

    def login(self):
        self.driver.get(LOGIN_URL)
        # The login form requires submitting the username first and then the
        # password on the next screen. Older versions of the script attempted to
        # fill fields that were not present which caused a TimeoutException.
        user_field = self.wait.until(
            EC.presence_of_element_located((By.ID, "UserName"))
        )
        user_field.send_keys(USERNAME)
        self.driver.find_element(By.ID, "UsernameNext").click()

        pass_field = self.wait.until(
            EC.presence_of_element_located((By.ID, "Password"))
        )
        pass_field.send_keys(PASSWORD)
        self.driver.find_element(By.ID, "Login").click()

        # Optional two factor page
        try:
            skip_btn = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Skip For Now')]"))
            )
            skip_btn.click()
        except Exception:
            pass  # Two step page did not appear

    def select_today_shipment(self):
        today = datetime.datetime.now().strftime("%m/%d/%Y")
        row_xpath = f"//table//th[contains(text(), 'In Store Delivery Date')]/..//td[contains(text(), '{today}')]/.."
        row = self.wait.until(EC.element_to_be_clickable((By.XPATH, row_xpath)))
        row.click()

    def scrape_categories(self) -> Dict[str, List[Dict]]:
        data = defaultdict(list)
        categories = self.wait.until(
            EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@href, 'D') and contains(@href, '=')]"))
        )
        for category in categories:
            cat_code = category.text.strip()
            category.click()
            items = self.scrape_items()
            data[cat_code].extend(items)
            self.driver.back()
        return data

    def scrape_items(self) -> List[Dict]:
        items = []
        rows = self.wait.until(
            EC.presence_of_all_elements_located((By.XPATH, "//table//tr[td]"))
        )
        for row in rows:
            desc = row.find_element(By.XPATH, "./td[contains(@class, 'Description')]").text
            sku = row.find_element(By.XPATH, "./td[contains(@class, 'SKU') or contains(text(), 'SKU')]").text
            count = row.find_element(By.XPATH, "./td[contains(@class, 'Item')]").text
            row.click()
            tracking_info = self.scrape_tracking()
            row_data = {
                "description": desc,
                "sku": sku,
                "count": count,
                "tracking": tracking_info,
            }
            items.append(row_data)
            self.driver.back()
        return items

    def scrape_tracking(self) -> List[Dict]:
        tracking_rows = self.wait.until(
            EC.presence_of_all_elements_located(
                (By.XPATH, "//a[contains(text(), 'Tracking Link')]/..")
            )
        )
        results = []
        for tr in tracking_rows:
            text = tr.text
            if "Tracking Link:" in text:
                parts = text.split("Tracking Link:")
                tracking_number = parts[1].strip()
                code = parts[0].split("-")[0].strip()
                delivery_date = self.get_delivery_date(tracking_number)
                results.append(
                    {
                        "code": code,
                        "tracking_number": tracking_number,
                        "delivery_date": delivery_date,
                    }
                )
        return results

    def get_delivery_date(self, tracking_number: str) -> str:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "transId": "1",
            "transactionSrc": "test",
            "AccessLicenseNumber": UPS_API_KEY,
        }
        url = UPS_TRACKING_API_URL.format(tracking_number=tracking_number)
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.ok:
                json_data = response.json()
                date = (
                    json_data.get("trackResponse", {})
                    .get("shipment", [{}])[0]
                    .get("package", [{}])[0]
                    .get("deliveryDate", "")
                )
                return date
        except Exception:
            pass
        return ""

    def close(self):
        self.driver.quit()


def send_email(results: Dict[str, List[Dict]], unique_count: int):
    lines = []
    for cat, items in results.items():
        lines.append(f"Category {cat}:")
        for item in items:
            for tr in item["tracking"]:
                if tr["delivery_date"] == datetime.datetime.now().strftime("%Y-%m-%d"):
                    lines.append(
                        f"{item['description']} - {item['sku']} - {item['count']} - {tr['tracking_number']} - {tr['delivery_date']}"
                    )
        lines.append("")
    lines.append(f"Total unique tracking numbers: {unique_count}")
    body = "\n".join(lines)

    msg = MIMEText(body)
    msg["Subject"] = "Today's Shipments"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.send_message(msg)


def main():
    scraper = CoachScraper()
    try:
        scraper.login()
        scraper.select_today_shipment()
        data = scraper.scrape_categories()
        unique_numbers: Set[str] = {
            tr["tracking_number"]
            for items in data.values()
            for item in items
            for tr in item["tracking"]
        }
        send_email(data, len(unique_numbers))
    finally:
        scraper.close()


if __name__ == "__main__":
    main()
