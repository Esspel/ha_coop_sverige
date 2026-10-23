# Coop Sverige för Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![Validate](https://img.shields.io/badge/HA-Integration-blue.svg)](https://www.home-assistant.io/)

En komplett och kraftfull Home Assistant-integration för **Coop Sverige**. Integrationen ger dig inte bara full koll på dina **bonussaldon och medlemsrabatter**, utan integrerar även Coops digitala **inköpslistor** (direkt i Home Assistants Todo-plattform), **personliga medlemserbjudanden**, samt **butiksinformation, ordinarie och avvikande öppettider (helgdagar) och serviceutbud**.

---

## 🌟 Funktioner

### 🛒 1. Inköpslistor (Home Assistant Todo-integration)
- **Inbyggd To-do-plattform**: Alla dina Coop-inköpslistor synkroniseras automatiskt som infödda `todo`-entiteter i Home Assistant (t.ex. `todo.coop_inkopslista`).
- **Full tvåvägs-interaktivitet**:
  - Lägg till varor direkt i Home Assistant-appen eller via Lovelace Todo-kort.
  - Bocka av och avmarkera varor i butiken eller hemma.
  - Radera varor och rensa klara poster.
  - Röststyrning via **Home Assistant Assist**, Google Assistant eller Alexa: *"Lägg till mjölk på Coop-listan"*.
- **Avancerade åtgärder / tjänster**:
  - `ha_coop_sverige.add_item`: Lägg till vara med kvantitet, enhet och butiksplacering/avdelning.
  - `ha_coop_sverige.update_item`: Ändra namn, mängd, avdelning eller avbockningsstatus på en vara.
  - `ha_coop_sverige.delete_item`: Radera specifik vara.
  - `ha_coop_sverige.clear_completed`: Rensa alla avbockade varor i en lista.
  - `ha_coop_sverige.create_shopping_list`: Skapa en helt ny inköpslista.
  - `ha_coop_sverige.delete_shopping_list`: Ta bort en befintlig lista.

---

### 🎁 2. Personliga Medlemserbjudanden (Personal Offers API)
- **Sensor**: `sensor.aktiva_personliga_erbjudanden` visar hur många aktiva riktade rabatter du har just nu.
- **Attribut**: Komplett lista med:
  - Erbjudanderubrik och beskrivning
  - Rabatt (t.ex. 20%, 10 kr rabatt)
  - Återstående användningar (`remainingUse`)
  - Giltighetsdatum
  - Aktiverande EAN-streckkoder för scanning i kassan
  - Giltiga kanaler (appen, butik, ShopExpress etc.)
- **Åtgärd med svarsdata**: `ha_coop_sverige.get_personal_offers` returnerar samtliga erbjudanden direkt till skript och automationer.

---

### 🏪 3. Butiksinformation, Helgdagar & Öppettider (Store API)
- **Sensor**: `sensor.coop_favoritbutik` för din valda Coop-butik med:
  - Adress, postnummer, ort, telefonnummer och webblänk
  - **Ordinarie öppettider** för veckans alla dagar
  - **Avvikande öppettider & Helgdagskalender** (`futureIrregularOpeningHours`): Midsommar, Julafton, Nyår, m.fl.
  - **Varningar**: Identifierar flaggan `visibleForEndUsers` så du kan få notiser i god tid inför ändrade tider!
  - **Tjänsteutbud / Services**: Boolska flaggor för t.ex. *Scan & Pay*, *Coop Snabbkassa*, *Salladsbar*, samt post- och paketombud (*Instabox, Budbee, PostNord, ATG, Svenska Spel*).
- **Åtgärder med svarsdata**:
  - `ha_coop_sverige.get_store_info`: Hämta full butiksinformation för valfri Coop-butik baserat på reskontranummer.
  - `ha_coop_sverige.get_store_offers`: Hämta alla aktuella kampanjer, varugrupper och extrapriser för vald butik.

---

### 💳 4. Coop Bonus & Medlemspoäng (Loyalty API)
Spåra ditt medlemskap och dina intjänade poäng i realtid:
- **Total Bonus (kr / poäng)** – Intjänat totalt saldo.
- **Månadsbonus (kr / poäng)** – Bonus intjänad under innevarande månad.
- **Medlemspriser (kr / poäng)** – Hur mycket du sparat genom medlemspriser.
- **Extrabonus (kr / poäng)** – Tilläggsbonusar och kampanjbelöningar.
- **Nästa nivå (kr)** – Hur mycket du har kvar att handla för till nästa bonusnivå.
- **Dagar till nästa nivå** – Dagar kvar att samla poäng för månaden.
- **Senaste inloggning** & **Medlems-ID**.

---

## 🚀 Installation

### Alternativ 1: Via HACS (rekommenderas)
1. Öppna **HACS** i Home Assistant.
2. Klicka på de tre prickarna uppe i högra hörnet och välj **Custom repositories** (Anpassade integrationer).
3. Ange URL:en till detta repository och välj kategori **Integration**.
4. Klicka på **Ladda ner** och starta därefter om Home Assistant.

### Alternativ 2: Manuell installation
1. Ladda ner eller klona detta repository.
2. Kopiera mappen `ha_coop_sverige` till din Home Assistant-katalog `<config>/custom_components/`.
3. Starta om Home Assistant.

---

## 🔑 Konfiguration

### Steg 1: Hämta sessionscookie från Coop
1. Logga in på ditt konto på [Coop.se](https://www.coop.se).
2. Öppna webbläsarens **Utvecklarverktyg** (tryck `F12` eller högerklicka och välj *Inspektera*).
3. Gå till fliken **Nätverk** (Network).
4. Ladda om sidan eller klicka runt för att trigga ett anrop (t.ex. mot `coop.se/api/spa/token`).
5. Klicka på ett anrop och titta under fliken **Cookies** eller rubriken **Request Headers** -> `Cookie`.
6. Kopiera värdet för kakan **`.AspNetCore.Cookies`** (en lång textsträng).

### Steg 2: Lägg till i Home Assistant
1. Gå till **Inställningar → Enheter och tjänster → Lägg till integration**.
2. Sök efter **Coop Sverige**.
3. Klistra in din `.AspNetCore.Cookies`-cookie i fältet och spara.
4. Dina sensorer och inköpslistor läggs automatiskt till!

---

## 🛠️ Tjänster / Åtgärder (Actions)

### Inköpslistor

#### `ha_coop_sverige.add_item`
Lägger till en vara i en inköpslista.
```yaml
action: ha_coop_sverige.add_item
data:
  name: "Havremjölk 1L"
  quantity: "2"
  unit: "st"
  placement: "Mejeri"
```

#### `ha_coop_sverige.update_item`
Uppdaterar status på en vara (t.ex. bocka av eller ändra mängd).
```yaml
action: ha_coop_sverige.update_item
data:
  product_id: "123456"
  is_checked: true
```

#### `ha_coop_sverige.clear_completed`
Tar bort alla avbockade varor från listan.
```yaml
action: ha_coop_sverige.clear_completed
```

#### `ha_coop_sverige.create_shopping_list`
Skapar en ny inköpslista.
```yaml
action: ha_coop_sverige.create_shopping_list
data:
  name: "Tacos på Fredag"
```

---

### Butiker och erbjudanden

#### `ha_coop_sverige.get_store_info`
Hämtar information och helgöppettider för en butik. Om `store_id` utelämnas hämtas din favoritbutik.
```yaml
action: ha_coop_sverige.get_store_info
response_variable: butik
```

#### `ha_coop_sverige.get_store_offers`
Hämtar veckans kampanjer och erbjudanden från din butik.
```yaml
action: ha_coop_sverige.get_store_offers
response_variable: erbjudanden
```

#### `ha_coop_sverige.get_personal_offers`
Hämtar dina aktiva personliga rabattkuponger.
```yaml
action: ha_coop_sverige.get_personal_offers
response_variable: kuponger
```

---

## 💡 Automations-exempel

### 1. Få notis när det är avvikande öppettider i butiken
```yaml
alias: "Varna för helgöppettider på Coop"
trigger:
  - platform: time
    at: "09:00:00"
condition:
  - condition: template
    value_template: >
      {{ state_attr('sensor.coop_favoritbutik', 'upcoming_holiday_warnings') | length > 0 }}
action:
  - action: notify.notify
    data:
      title: "Coop: Ändrade öppettider på gång"
      message: >
        Tänk på att Coop har avvikande tider snart: 
        {{ state_attr('sensor.coop_favoritbutik', 'upcoming_holiday_warnings')[0].description }}
```

### 2. Lägg till receptingredienser på inköpslistan med en knapp
```yaml
alias: "Lägg till ingredienser för Pannkakor"
trigger:
  - platform: state
    entity_id: input_button.handla_pannkakor
action:
  - action: ha_coop_sverige.add_item
    data:
      name: "Mjölk"
      quantity: "1"
      unit: "l"
  - action: ha_coop_sverige.add_item
    data:
      name: "Ägg 6-pack"
      quantity: "1"
      unit: "st"
  - action: ha_coop_sverige.add_item
    data:
      name: "Vetemjöl"
      quantity: "1"
      unit: "kg"
```

---

## 📡 API-Översikt
Integrationen ansluter mot Coops officiella API-tjänster:
- **Autentisering**: `https://login.coop.se/connect/token` (Bearer JWT via sessionscookie).
- **Inköpslistor**: `https://proxy.api.coop.se/digital/shoppinglist` (`api-version=v2`).
- **Personliga rabatter**: `https://external.api.coop.se/digital/personaloffers/offers` (`api-version=v2`).
- **Butiker & Öppettider**: `https://proxy.api.coop.se/external/store/stores/{id}` (`api-version=v3`).
- **Favoritbutiker**: `https://proxy.api.coop.se/external/store/favorite-stores/me` (`api-version=v1`).
- **Erbjudanden & Kampanjer**: `https://external.api.coop.se/dke/offers/sorting-groups/{store_id}` (`api-version=v3`).
- **Bonus & Poäng**: `https://external.api.coop.se/loyalty/account/points/...` (`api-version=v3/v4`).
