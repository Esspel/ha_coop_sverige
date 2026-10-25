class CoopShoppingListCard extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (!this.content) {
      this.innerHTML = `
        <ha-card header="Coop Inköpslista">
          <div class="card-content">
            <div class="list-controls">
              <select id="list-selector" class="styled-select"></select>
              <button id="create-list-btn" class="styled-btn">+ Ny lista</button>
              <button id="remove-list-btn" class="styled-btn danger-btn">Ta bort lista</button>
            </div>
            
            <h3 id="list-name" class="list-title">Ingen lista vald</h3>

            <div id="shopping-list-container" class="items-container"></div>

            <form id="add-item-form" class="add-form">
              <input type="text" id="item-name" placeholder="Vara..." required class="styled-input name-input">
              <div class="form-row">
                <input type="number" id="item-quantity" placeholder="Antal" value="1" step="any" class="styled-input qty-input">
                <select id="item-unit" class="styled-select unit-select">
                  <option value="">Enhet</option>
                  <option value="st">st</option>
                  <option value="kg">kg</option>
                  <option value="g">g</option>
                  <option value="l">l</option>
                  <option value="dl">dl</option>
                  <option value="pkt">pkt</option>
                </select>
                <select id="placement-select" class="styled-select placement-select">
                  <option value="">Kategori / Placering</option>
                  <option value="Frukt och grönt">Frukt och grönt</option>
                  <option value="Mejeri">Mejeri</option>
                  <option value="Bröd">Bröd</option>
                  <option value="Drycker">Drycker</option>
                  <option value="Konserver · Skafferi">Konserver · Skafferi</option>
                  <option value="Kryddor · Smaksättare">Kryddor · Smaksättare</option>
                  <option value="Bakning · Efterrätter · Frukost">Bakning · Efterrätter · Frukost</option>
                  <option value="Mos · Pasta · Ris">Mos · Pasta · Ris</option>
                  <option value="Djupfryst">Djupfryst</option>
                  <option value="Huvudingrediens">Huvudingrediens</option>
                  <option value="Godis · Snacks">Godis · Snacks</option>
                  <option value="Hygien">Hygien</option>
                  <option value="Städa · Tvätta · Diska">Städa · Tvätta · Diska</option>
                  <option value="Barn · Baby">Barn · Baby</option>
                  <option value="Alkohol">Alkohol</option>
                  <option value="Erbjudanden">Erbjudanden</option>
                  <option value="Övrigt">Övrigt</option>
                </select>
              </div>
              <button type="submit" class="styled-btn add-btn">Lägg till vara</button>
            </form>
          </div>
        </ha-card>
        <style>
          .card-content { display: flex; flex-direction: column; gap: 12px; }
          .list-controls { display: flex; gap: 8px; flex-wrap: wrap; }
          .list-title { margin: 8px 0 0 0; font-size: 1.1em; color: var(--primary-text-color); }
          .items-container { display: flex; flex-direction: column; gap: 6px; max-height: 350px; overflow-y: auto; }
          .item-row { display: flex; align-items: center; justify-content: space-between; background: var(--secondary-background-color); padding: 8px 12px; border-radius: 8px; }
          .item-row.completed span { text-decoration: line-through; opacity: 0.6; }
          .item-label { display: flex; align-items: center; gap: 8px; cursor: pointer; flex: 1; flex-wrap: wrap; }
          .item-meta { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
          .item-qty { font-size: 0.85em; color: var(--secondary-text-color, rgba(0,0,0,0.6)); background: var(--primary-background-color, #f5f5f5); padding: 1px 6px; border-radius: 4px; }
          .item-cat { font-size: 0.75em; color: var(--accent-color, #03a9f4); background: var(--primary-background-color, #e3f2fd); padding: 1px 6px; border-radius: 4px; }
          .item-category { font-size: 0.85em; opacity: 0.75; margin-left: 6px; font-style: italic; }
          .item-actions { display: flex; align-items: center; gap: 6px; }
          .edit-btn { background: none; border: 1px solid var(--divider-color); color: var(--primary-text-color); border-radius: 6px; padding: 4px 8px; cursor: pointer; font-size: 0.9em; }
          .edit-btn:hover { background: var(--secondary-background-color); }
          .delete-btn { background: none; border: none; color: var(--error-color, #db4437); font-size: 1.2em; cursor: pointer; padding: 0 4px; }
          .add-form { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; border-top: 1px solid var(--divider-color); padding-top: 10px; }
          .form-row { display: flex; gap: 6px; }
          .styled-input, .styled-select { padding: 8px; border-radius: 6px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); }
          .name-input { width: 100%; box-sizing: border-box; }
          .qty-input { width: 70px; }
          .unit-select { width: 80px; }
          .placement-select { flex: 1; }
          .styled-btn { padding: 8px 14px; border-radius: 6px; border: none; background: var(--primary-color); color: var(--text-primary-color, #fff); font-weight: bold; cursor: pointer; }
          .styled-btn:hover { opacity: 0.9; }
          .danger-btn { background: var(--error-color, #db4437); color: #fff; }
        </style>
      `;
      this.content = true;
      this.currentListEntityId = null;
      this._bindEvents();
    }

    this._updateListsDropdown();
    this._renderItems();
  }
