# StoreTrac Scraper

This script automates logging in to the Coach PCS tracking site, collects UPS tracking
links for shipments scheduled to arrive on the current day, and emails a summary.

## Usage

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Export environment variables for login, UPS, and email credentials:
   - `COACH_USERNAME` – Coach PCS username (defaults to `Coh4501`)
   - `COACH_PASSWORD` – Coach PCS password (defaults to `Coach1181`)
   - `UPS_API_KEY` – UPS API key for tracking lookups
   - `EMAIL_FROM` – email address used to send the summary
   - `EMAIL_PASSWORD` – password or app password for the above account
   - `SMTP_SERVER` – SMTP server (default: `smtp.gmail.com`)
   - `SMTP_PORT` – SMTP port (default: `587`)
3. Run the script:
   ```bash
   python scrape_shipments.py
   ```

The login form asks for the username first and then displays the password
field. The script now clicks **Next** after entering the username before
submitting the password. It also handles the optional "Add Two-Step
Verification" page by pressing **Skip For Now** if it appears.
The script uses Selenium in headless mode to navigate the website, handle an optional
"Add Two-Step Verification" page by clicking **Skip For Now**, then selects the
shipment matching today's date. For each category (e.g. `D01`), it collects item
information, uses the UPS Tracking API to find the delivery date, and, if that date
is today, includes the item in the email report. The report is emailed to
`creativeappmaking@gmail.com` along with a count of unique tracking numbers.
