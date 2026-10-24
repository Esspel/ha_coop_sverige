/* Coop Sverige shopping list custom card */
import {hass} from '/static/config.js';

// Global state
let currentListId = null;
let currentListName = null;
let shoppingListItems = [];

const PLACEMENTS = [
  "Alkohol",
  "Bakning · Efterrätter · Frukost",
  "Barn · Baby",
  "Bröd",
  "Djupfryst",
  "Drycker",
  "Erbjudanden",
  "Frukt och grönt",
  "Godis · Snacks",
  "Huvudingrediens",
  "Hygien",
  "Konserver · Skafferi",
  "Kryddor · Smaksättare",
  "Mejeri",
  "Mos · Pasta · Ris",
  "Städa · Tvätta · Diska",
  "Övrigt",
];

const VALID_UNITS = ["dl", "g", "kg", "l", "pkt", "st"];

async function loadShoppingLists() {
  const entities = Object.values(hass.states || {});
  const todoEntities = entities.filter(e => e.domain === 'todo' && e.entity_id && e.entity_id.startsWith('todo.coop_'));
  return todoEntities.map(e => ({
    id: e.entity_id,
    name: e.attributes.name || e.entity_id,
    items: e.attributes.items || []
  }));
}

function renderPlacementSelector() {
  const selected = document.getElementById('placement-select').value;
  const html = PLACEMENTS.map(p => `<option value="${p}" ${p === selected ? 'selected' : ''}>${p}</option>`).join('');
  document.getElementById('placement-select').innerHTML = html;
}

function formatItem(item) {
  const qty = item.quantity || '1';
  const unit = item.unit || '';
  const name = item.name || '';
  return `${qty} ${unit} ${name}`.trim();
}

async function saveItemToList(listId, name, quantity, unit, placement) {
  await fetch(`/api/services/ha_coop_sverige/add_item`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      shopping_list_id: listId,
      name,
      quantity,
      unit,
      placement
    })
  });
  location.reload();
}

function initAddItemForm() {
  const form = document.getElementById('add-item-form');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('item-name').value.trim();
    const quantity = document.getElementById('item-quantity').value || 1;
    const unit = document.getElementById('item-unit').value || '';
    const placement = document.getElementById('placement-select').value || '';

    if (!name) return;

    await saveItemToList(currentListId, name, quantity, unit, placement);
    form.reset();
    renderShoppingList();
  });
}

function renderShoppingList() {
  const listEntity = Object.values(hass.states || {}).find(e =>
    e.domain === 'todo' && e.entity_id && e.entity_id === currentListId
  );

  if (!listEntity) return;

  shoppingListItems = listEntity.attributes.items || [];

  const container = document.getElementById('shopping-list-container');
  container.innerHTML = '';

  shoppingListItems.forEach((item, idx) => {
    const div = document.createElement('div');
    div.className = 'card';
    div.innerHTML = `
      <label class="card-header">
        <input type="checkbox" ${item.state === 'completed' ? 'checked' : ''}
               onchange="toggleItem(${idx})">
        <span>${formatItem(item)}</span>
      </label>
      <button class="card-actions" onclick="deleteItem(${idx})">×</button>
    `;
    container.appendChild(div);
  });

  const addBtn = document.getElementById('add-item-btn');
  addBtn.style.display = 'block';
}

async function toggleItem(idx) {
  const item = shoppingListItems[idx];
  const newState = !item.state;
  await fetch(`/api/services/ha_coop_sverige/update_item`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      shopping_list_id: currentListId,
      item_id: idx,
      name: item.name,
      quantity: item.quantity,
      unit: item.unit,
      state: newState ? 'on' : 'off'
    })
  });
  renderShoppingList();
}

async function deleteItem(idx) {
  if (!confirm('Ta bort denna vara?')) return;
  await fetch(`/api/services/ha_coop_sverige/delete_item`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      shopping_list_id: currentListId,
      item_id: idx
    })
  });
  renderShoppingList();
}

async function createNewList() {
  const name = prompt('Ange namn på nya inköpslistan:');
  if (!name) return;
  await fetch('/api/services/ha_coop_sverige/create_shopping_list', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name})
  });
  location.reload();
}

document.addEventListener('DOMContentLoaded', async () => {
  renderPlacementSelector();
  const lists = await loadShoppingLists();

  const listSelector = document.getElementById('list-selector');
  listSelector.innerHTML = '<option value="">Välj inköpslista</option>' +
    lists.map(l => `<option value="${l.id}">${l.name}</option>`).join('');

  listSelector.addEventListener('change', (e) => {
    currentListId = e.target.value;
    currentListName = e.target.options[e.target.selectedIndex].text;
    document.getElementById('list-name').textContent = currentListName || 'Ingen lista vald';
    renderShoppingList();
    document.getElementById('add-item-btn').style.display = 'none';
  });

  if (lists.length > 0) {
    currentListId = lists[0].id;
    renderShoppingList();
  }

  initAddItemForm();

  const createListBtn = document.getElementById('create-list-btn');
  createListBtn.addEventListener('click', createNewList);
});