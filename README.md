# BookMyShow Automation

Python automation for BookMyShow ticket discovery and booking flows using Playwright and a Chrome/Chromium browser connected through the Chrome DevTools Protocol (CDP).

This project is designed to handle the repetitive parts of the booking flow for a specific event, including:

- opening the event page
- checking availability and session data
- monitoring queue wait times
- selecting a valid session and seat category
- filling patron details and continuing through checkout

## Features

- Connects to an existing Chrome/Chromium instance using `--remote-debugging-port=9222`
- Uses Playwright for automation and DOM interaction
- Tracks session availability for specific event dates and categories
- Handles waiting/Queue-It flows automatically
- Supports configurable ticket quantity, date selection, and category preference
- Accepts booking requests through JSON payloads on standard input

## Important note

This script interacts with a public booking website and can trigger rate limits, anti-bot protections, or terms-of-service restrictions. Use it responsibly and only for legitimate personal use. Do not use it to overload the service or bypass platform policies.

## Requirements

- Python 3.10+
- Google Chrome or Chromium installed
- Playwright browser binaries
- Poetry (recommended)

## Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/<your-user>/bookmyshow-automation.git
   cd bookmyshow-automation
   ```

2. Install dependencies:

   ```bash
   poetry install
   ```

3. Install the Playwright browser runtime:

   ```bash
   poetry run playwright install chromium
   ```

4. Start Chrome with remote debugging enabled:

   On Windows:

   ```powershell
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Temp\bookmyshow-automation"
   ```

   On macOS:

   ```bash
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="/tmp/bookmyshow-automation"
   ```

   On Linux:

   ```bash
   google-chrome --remote-debugging-port=9222 --user-data-dir="/tmp/bookmyshow-automation"
   ```

## Running the automation

The project starts a listener that reads a JSON configuration from standard input. Run it with:

```bash
poetry run python entrypoint.py
```

Then send a booking request in JSON format:

```json
{
  "endpoint": "http://127.0.0.1:9222",
  "code": "ET00012345",
  "quantity": 2,
  "datetimes": [
    "2026-11-15T18:30:00",
    "2026-11-16T18:30:00"
  ],
  "categories": ["SL", "PL"],
  "full_name": "John Doe",
  "email": "john@example.com",
  "phone": "9876543210"
}
```

The app accepts the request, creates an automation instance, and starts the booking flow for the selected event.

## Configuration fields

- `endpoint`: browser endpoint for Playwright CDP connection (default: `http://127.0.0.1:9222`)
- `code`: BookMyShow event code
- `quantity`: number of seats to attempt
- `datetimes`: preferred show times as ISO-like datetime strings
- `categories`: seat categories such as `PL`, `SL`, `F`, etc.
- `full_name`: patron full name
- `email`: email address for checkout
- `phone`: phone number without country code
- `payment_method`: optional `VISA` or `MASTERCARD`
- `cardholder_name`: optional card holder name
- `card_number`: optional card number
- `card_expiry`: optional expiry date in datetime format
- `card_cvv`: optional card security code

## Example workflow

```bash
poetry run python entrypoint.py
```

Then paste:

```json
{
  "code": "ET00012345",
  "quantity": 2,
  "datetimes": ["2026-11-15T18:30:00"],
  "categories": ["SL"],
  "full_name": "Jane Doe",
  "email": "jane@example.com",
  "phone": "9876543210"
}
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
