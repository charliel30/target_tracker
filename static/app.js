// app.js — Target Tracker Intelligence Network
// Vanilla JS, no frameworks. Simple DOM manipulation + fetch.

// ---- State ----------------------------------------------------------------

let conversationHistory = []; // Array of {role: "user"|"assistant", content: string}

// ---- DOM refs -------------------------------------------------------------

const chatMessages = document.getElementById('chatMessages');
const messageInput  = document.getElementById('messageInput');
const sendBtn       = document.getElementById('sendBtn');
const alertsList    = document.getElementById('alertsList');

// ---- Chat -----------------------------------------------------------------

// Add a message bubble to the chat area and scroll to bottom.
function addMessageToChat(role, content) {
  const wrapper = document.createElement('div');
  wrapper.classList.add('message', role);

  const label = document.createElement('div');
  label.classList.add('message-role');
  label.textContent = role === 'user' ? 'You' : 'Agent';

  const body = document.createElement('div');
  body.textContent = content;

  wrapper.appendChild(label);
  wrapper.appendChild(body);
  chatMessages.appendChild(wrapper);

  // Scroll to the latest message
  chatMessages.scrollTop = chatMessages.scrollHeight;

  return wrapper;
}

// Show a three-dot typing indicator while waiting for the server.
function showTypingIndicator() {
  const indicator = document.createElement('div');
  indicator.classList.add('typing-indicator');
  indicator.id = 'typingIndicator';
  indicator.innerHTML = '<span></span><span></span><span></span>';
  chatMessages.appendChild(indicator);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTypingIndicator() {
  const el = document.getElementById('typingIndicator');
  if (el) el.remove();
}

// Send the current input to the backend.
async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text) return;

  // Clear input and disable controls while waiting
  messageInput.value = '';
  messageInput.style.height = 'auto';
  sendBtn.disabled = true;

  // Display the user's message and add it to history
  addMessageToChat('user', text);
  conversationHistory.push({ role: 'user', content: text });

  showTypingIndicator();

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        history: conversationHistory,
      }),
    });

    removeTypingIndicator();

    if (!response.ok) {
      addMessageToChat('assistant', '[Error: server returned ' + response.status + ']');
      return;
    }

    const data = await response.json();
    const reply = data.message || data.response || '';

    // Display and record the assistant reply
    addMessageToChat('assistant', reply);
    conversationHistory.push({ role: 'assistant', content: reply });

    // If the response includes new alerts, prepend them to the sidebar
    if (Array.isArray(data.new_alerts) && data.new_alerts.length > 0) {
      data.new_alerts.forEach(alert => prependAlert(alert));
    }

  } catch (err) {
    removeTypingIndicator();
    addMessageToChat('assistant', '[Error: ' + err.message + ']');
  } finally {
    sendBtn.disabled = false;
    messageInput.focus();
  }
}

// ---- Alerts ---------------------------------------------------------------

// Fetch all current alerts from the server and render them.
async function loadAlerts() {
  try {
    const response = await fetch('/api/alerts');
    if (!response.ok) return;

    const data = await response.json();
    const alerts = Array.isArray(data) ? data : (data.alerts || []);

    alertsList.innerHTML = '';

    if (alerts.length === 0) {
      renderEmptyState();
      return;
    }

    // Newest first: assume server returns oldest first, so reverse
    alerts.slice().reverse().forEach(alert => {
      alertsList.appendChild(renderAlert(alert));
    });

  } catch (err) {
    console.error('Failed to load alerts:', err);
  }
}

// Build and return a single alert card element.
function renderAlert(alert) {
  const card = document.createElement('div');
  card.classList.add('alert-card');
  card.dataset.alertId = alert.id;

  const ts = document.createElement('div');
  ts.classList.add('alert-timestamp');
  ts.textContent = formatTimestamp(alert.timestamp || alert.created_at);

  const desc = document.createElement('div');
  desc.classList.add('alert-description');
  desc.textContent = alert.description || alert.message || '';

  const dismiss = document.createElement('button');
  dismiss.classList.add('alert-dismiss');
  dismiss.textContent = '[x]';
  dismiss.title = 'Dismiss alert';
  dismiss.onclick = () => dismissAlert(alert.id, card);

  card.appendChild(ts);
  card.appendChild(desc);
  card.appendChild(dismiss);

  return card;
}

// Insert a new alert at the top of the list (newest first).
function prependAlert(alert) {
  // Remove the empty-state placeholder if present
  const empty = alertsList.querySelector('.alerts-empty');
  if (empty) empty.remove();

  const card = renderAlert(alert);
  alertsList.insertBefore(card, alertsList.firstChild);
}

// DELETE the alert on the server, then remove it from the DOM.
async function dismissAlert(alertId, cardEl) {
  try {
    const response = await fetch('/api/alerts/' + alertId, { method: 'DELETE' });
    if (!response.ok) {
      console.error('Failed to dismiss alert', alertId);
      return;
    }
  } catch (err) {
    console.error('Error dismissing alert:', err);
    return;
  }

  cardEl.remove();

  // Show empty state if no alerts remain
  if (alertsList.querySelectorAll('.alert-card').length === 0) {
    renderEmptyState();
  }
}

function renderEmptyState() {
  const empty = document.createElement('div');
  empty.classList.add('alerts-empty');
  empty.textContent = 'No active alerts.';
  alertsList.appendChild(empty);
}

// ---- Helpers --------------------------------------------------------------

// Format an ISO timestamp or unix epoch into a short human-readable string.
function formatTimestamp(raw) {
  if (!raw) return '—';
  const date = typeof raw === 'number' ? new Date(raw * 1000) : new Date(raw);
  if (isNaN(date)) return String(raw);
  return date.toLocaleString(undefined, {
    month:  'short',
    day:    'numeric',
    hour:   '2-digit',
    minute: '2-digit',
  });
}

// ---- Input behaviour ------------------------------------------------------

// Auto-grow the textarea as the user types.
messageInput.addEventListener('input', () => {
  messageInput.style.height = 'auto';
  messageInput.style.height = messageInput.scrollHeight + 'px';
});

// Enter sends; Shift+Enter inserts a newline.
messageInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// ---- Init -----------------------------------------------------------------

// Focus the input and load existing alerts when the page first loads.
messageInput.focus();
loadAlerts();
