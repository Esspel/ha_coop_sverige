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
          .list-controls { display: flex; gap: 8px; }
          .list-title { margin: 8px 0 0 0; font-size: 1.1em; color: var(--primary-text-color); }
          .items-container { display: flex; flex-direction: column; gap: 6px; max-height: 350px; overflow-y: auto; }
          .item-row { display: flex; align-items: center; justify-content: space-between; background: var(--secondary-background-color); padding: 8px 12px; border-radius: 8px; }
          .item-row.completed span { text-decoration: line-through; opacity: 0.6; }
          .item-label { display: flex; align-items: center; gap: 8px; cursor: pointer; flex: 1; }
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
          .item-category { font-size: 0.85em; opacity: 0.75; margin-left: 6px; font-style: italic; }
          .item-actions { display: flex; align-items: center; gap: 6px; }
          .edit-btn { background: none; border: 1px solid var(--divider-color); color: var(--primary-text-color); border-radius: 6px; padding: 4px 8px; cursor: pointer; font-size: 0.9em; }
          .edit-btn:hover { background: var(--secondary-background-color); }
          .delete-btn { background: none; border: none; color: var(--error-color, #db4437); font-size: 1.2em; cursor: pointer; padding: 0 4px; }
        </style>
      `;
      this.content = true;
      this.currentListEntityId = null;
      this._bindEvents();
    }

    this._updateListsDropdown();
    this._renderItems();
  }

  _bindEvents() {
    const listSelector = this.querySelector('#list-selector');
    listSelector.addEventListener('change', (e) => {
      this.currentListEntityId = e.target.value;
      this._renderItems();
    });

    const createListBtn = this.querySelector('#create-list-btn');
    createListBtn.addEventListener('click', () => this._createNewList());

    const addForm = this.querySelector('#add-item-form');
    addForm.addEventListener('submit', (e) => {
      e.preventDefault();
      this._addItem();
    });
  }

  _getCoopTodoEntities() {
    if (!this._hass || !this._hass.states) return [];
    const entities = Object.values(this._hass.states).filter(
      (e) => e.entity_id.startsWith('todo.')
    );
    // Filter to Coop shopping lists (our integration) - be flexible about naming
    return entities.filter((e) => {
      if (!e || e.state === 'unavailable' || e.state === 'unknown') return false;
      const attrs = e.attributes || {};
      if (attrs.shopping_list_id || attrs.list_id || attrs.id) return true;
      if (e.entity_id.includes('coop')) return true;
      if (attrs.integration === 'ha_coop_sverige') return true;
      // Also check friendly name
      const fn = (attrs.friendly_name || '').toLowerCase();
      if (fn.includes('coop') || fn.includes('inköpslista') || fn.includes('shopping')) return true;
      return false;
    });
  }

  _updateListsDropdown() {
    const lists = this._getCoopTodoEntities();
    const selector = this.querySelector('#list-selector');
    if (!selector) return;

    // If no lists found, keep existing selection or clear
    if (lists.length === 0) {
      selector.innerHTML = '';
      // Don't clear currentListEntityId if it might become available
      return;
    }

    const currentVal = this.currentListEntityId && lists.find(l => l.entity_id === this.currentListEntityId) 
      ? this.currentListEntityId 
      : lists[0].entity_id;
    this.currentListEntityId = currentVal;

    selector.innerHTML = lists
      .map(
        (l) => `<option value="${l.entity_id}" ${l.entity_id === currentVal ? 'selected' : ''}>
          ${l.attributes.friendly_name || l.entity_id}
        </option>`
      )
      .join('');
  }

  _renderItems() {
    const container = this.querySelector('#shopping-list-container');
    const titleEl = this.querySelector('#list-name');
    if (!container) return;
    
    if (!this.currentListEntityId) {
      container.innerHTML = '<div style="padding: 8px; opacity: 0.7;">Välj en lista från menyn</div>';
      if (titleEl) titleEl.textContent = 'Ingen lista vald';
      return;
    }

    const listEntity = this._hass.states[this.currentListEntityId];
    if (!listEntity || listEntity.state === 'unavailable' || listEntity.state === 'unknown') {
      container.innerHTML = '<div class="empty">Ingen lista tillgänglig</div>';
      if (titleEl) titleEl.textContent = listEntity?.attributes?.friendly_name || this.currentListEntityId;
      return;
    }

    if (titleEl) titleEl.textContent = listEntity.attributes.friendly_name || listEntity.entity_id;
    const items = listEntity.attributes.items || [];

    if (!Array.isArray(items) || items.length === 0) {
      container.innerHTML = '<div style="padding: 8px; opacity: 0.7;">Listan är tom</div>';
      // Bind events even if empty? No need
      return;
    }

    container.innerHTML = items
      .map((item, idx) => {
        const isCompleted = item.status === 'completed';
        const qtyStr = item.quantity ? `${item.quantity} ` : '';
        const unitStr = item.unit ? `${item.unit} ` : '';
        const categoryDisplay = item.placement ? ` <span class="item-category">${item.placement}</span>` : '';
        return `
          <div class="item-row ${isCompleted ? 'completed' : ''}">
            <label class="item-label">
              <input type="checkbox" ${isCompleted ? 'checked' : ''} data-idx="${idx}" class="item-checkbox">
              <span>${qtyStr}${unitStr}${item.summary || item.name || ''}${categoryDisplay}</span>
            </label>
            <div class="item-actions">
              <button class="edit-btn" data-idx="${idx}" title="Redigera">✏️</button>
              <button class="delete-btn" data-idx="${idx}">×</button>
            </div>
          </div>
        `;
      })
      .join('');

    // Koppla event-lyssnare för checkboxes och ta bort-knappar
    container.querySelectorAll('.item-checkbox').forEach((cb) => {
      cb.addEventListener('change', (e) => {
        const idx = parseInt(e.target.dataset.idx, 10);
        this._toggleItem(items[idx]);
      });
    });

    container.querySelectorAll('.delete-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const idx = parseInt(e.target.dataset.idx, 10);
        this._deleteItem(items[idx]);
      });
    });

    container.querySelectorAll('.edit-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const idx = parseInt(e.target.dataset.idx, 10);
        this._editItem(items[idx]);
      });
    });
  }

  async _editItem(item) {
    const nameInput = this.querySelector('#item-name');
    const qtyInput = this.querySelector('#item-quantity');
    const unitSelect = this.querySelector('#item-unit');
    const placementSelect = this.querySelector('#placement-select');

    const name = prompt('Redigera vara:', item.summary || item.name || '');
    if (name === null) return;

    const qty = prompt('Antal:', item.quantity ? String(item.quantity) : '1');
    if (qty === null) return;

    const qtyNum = parseFloat(qty.replace(',', '.'));
    const unit = prompt('Enhet (st, kg, g, l, dl, pkt):', item.unit || '');
    if (unit === null) return;

    const placement = prompt('Kategori / Placering:', item.placement || '');
    if (placement === null) return;

    const listEntity = this._hass.states[this.currentListEntityId];
    const listId = listEntity.attributes.id || listEntity.attributes.shopping_list_id || listEntity.attributes.list_id || this._listId || listEntity.attributes.friendly_name;

    await this._hass.callService('ha_coop_sverige', 'update_item', {
      list_id: String(listId),
      product_id: item.id || item.summary,
      name: name,
      quantity: qtyNum,
      unit: unit,
      placement: placement,
      is_checked: item.status === 'completed',
    });
  }

  async _addItem() {
    const nameInput = this.querySelector('#item-name');
    const qtyInput = this.querySelector('#item-quantity');
    const unitSelect = this.querySelector('#item-unit');
    const placementSelect = this.querySelector('#placement-select');

    const name = nameInput.value.trim();
    if (!name || !this.currentListEntityId) return;

    const listEntity = this._hass.states[this.currentListEntityId];
    const listId = listEntity.attributes.id || listEntity.attributes.shopping_list_id || listEntity.attributes.list_id || this._listId || listEntity.attributes.friendly_name;

    const payload = {
      name: name,
      quantity: qtyInput.value || 1,
      unit: unitSelect.value || '',
      placement: placementSelect.value || '',
    };
    if (listId) payload.list_id = String(listId);

    await this._hass.callService('ha_coop_sverige', 'add_item', payload);

    nameInput.value = '';
  }

  async _toggleItem(item) {
    const listEntity = this._hass.states[this.currentListEntityId];
    const listId = listEntity.attributes.id || listEntity.attributes.shopping_list_id || listEntity.attributes.list_id || this._listId || listEntity.attributes.friendly_name;
    const isCompleted = item.status === 'completed';

    await this._hass.callService('ha_coop_sverige', 'update_item', {
      list_id: String(listId),
      product_id: item.id || item.summary,
      is_checked: !isCompleted,
    });
  }

  async _deleteItem(item) {
    if (!confirm(`Ta bort "${item.summary || item.name}"?`)) return;
    const listEntity = this._hass.states[this.currentListEntityId];
    const listId = listEntity.attributes.id || listEntity.attributes.shopping_list_id || listEntity.attributes.list_id || this._listId || listEntity.attributes.friendly_name;

    await this._hass.callService('ha_coop_sverige', 'delete_item', {
      list_id: String(listId),
      product_id: item.id || item.summary,
    });
  }

  async _createNewList() {
    const name = prompt('Ange namn på nya inköpslistan:');
    if (!name) return;

    await this._hass.callService('ha_coop_sverige', 'create_shopping_list', {
      name: name,
    });
  }

  setConfig(config) {
    this._config = config;
  }

  getCardSize() {
    return 4;
  }
}

customElements.define('coop-shopping-list-card', CoopShoppingListCard);