# Home Assistant Coop Sverige

A custom Home Assistant integration for the **Coop Bonus** loyalty program in Sweden.

This integration tracks your Coop Bonus points, monetary earnings, monthly bonuses, member prices, extra bonuses, and progress to the next loyalty level as sensors in Home Assistant.

## Features

- **Total Bonus (kr / poäng)** – Lifetime points and monetary value.
- **Monthly Bonus (kr / poäng)** – Bonus earned this month.
- **Member Prices (kr / poäng)** – Member pricing discounts.
- **Extra Bonus (kr / poäng)** – Additional bonus rewards.
- **Next Level (kr)** – Amount needed for the next loyalty level.
- **Days Until Next Level** – Countdown to the next level.
- **Last Login** – Last login timestamp.
- **Member ID** – Coop membership ID.

## Setup

### Install

1. Copy the `ha_coop_sverige` folder into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

### Get session cookie from Coop

1. Log in to [Coop.se](https://www.coop.se).
2. Open **Developer Tools** (F12) → **Network** tab.
3. Refresh the page or trigger an API call.
4. Find a request to `www.coop.se/api/spa/token`.
5. Inspect the request and copy the **`.AspNetCore.Cookies`** cookie value.

### Configure

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Coop Bonus** / **ha_coop_sverige**.
3. Paste the session cookie when prompted.

## API details

- Token endpoint: `https://login.coop.se/connect/token`
- Balance: `https://external.api.coop.se/loyalty/account/points/balance?api-version=v3`
- Yearly summary: `https://external.api.coop.se/loyalty/account/points/summary/yearly?api-version=v4`

