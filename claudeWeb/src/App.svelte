<script>
  let expression = $state('');
  let result = $state('');
  let error = $state('');
  let loading = $state(false);
  let justEvaluated = false;

  const OPERATORS = ['+', '-', '*', '/', '^'];

  // Pretty symbols for the display; the backend always receives the plain ones.
  const pretty = (s) => s.replaceAll('*', '×').replaceAll('/', '÷').replaceAll('-', '−');

  function press(token) {
    error = '';
    if (justEvaluated) {
      // Operators continue from the result; anything else starts fresh.
      expression = OPERATORS.includes(token) && result ? result : '';
      justEvaluated = false;
    }
    result = '';
    expression += token;
  }

  function clear() {
    expression = result = error = '';
    justEvaluated = false;
  }

  function backspace() {
    if (justEvaluated) return clear();
    error = '';
    expression = expression.slice(0, -1);
  }

  async function equals() {
    if (!expression.trim() || loading) return;
    loading = true;
    try {
      const res = await fetch('/api/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expression }),
      });
      const data = await res.json();
      if (data.error) {
        error = data.error;
      } else {
        result = data.result;
        error = '';
        justEvaluated = true;
      }
    } catch {
      error = 'Cannot reach backend (is server.py running?)';
    } finally {
      loading = false;
    }
  }

  function onKey(e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (/^[0-9.()+\-*/^]$/.test(e.key)) press(e.key);
    else if (e.key === 'Enter' || e.key === '=') { e.preventDefault(); equals(); }
    else if (e.key === 'Backspace') backspace();
    else if (e.key === 'Escape') clear();
  }

  // [label, action, css class]
  const keys = [
    ['C', clear, 'fn'], ['(', () => press('('), 'fn'], [')', () => press(')'), 'fn'], ['⌫', backspace, 'fn'],
    ['7', () => press('7')], ['8', () => press('8')], ['9', () => press('9')], ['÷', () => press('/'), 'op'],
    ['4', () => press('4')], ['5', () => press('5')], ['6', () => press('6')], ['×', () => press('*'), 'op'],
    ['1', () => press('1')], ['2', () => press('2')], ['3', () => press('3')], ['−', () => press('-'), 'op'],
    ['0', () => press('0')], ['.', () => press('.')], ['^', () => press('^'), 'op'], ['+', () => press('+'), 'op'],
  ];
</script>

<svelte:window onkeydown={onKey} />

<main>
  <div class="calc">
    <div class="brand">CALC-U-LATOR <span>SOLAR</span></div>

    <div class="screen" class:error={!!error}>
      <div class="expr">{pretty(expression) || '\u00a0'}</div>
      <div class="out">
        {#if error}{error}{:else if loading}…{:else}{result || '0'}{/if}
      </div>
    </div>

    <div class="keys">
      {#each keys as [label, action, cls]}
        <button class={cls} onclick={action}>{label}</button>
      {/each}
      <button class="eq" onclick={equals}>=</button>
    </div>
  </div>
</main>

<style>
  :global(body) {
    margin: 0;
    min-height: 100vh;
    display: grid;
    place-items: center;
    background: #cfd3d6;
    font-family: 'Helvetica Neue', Arial, sans-serif;
  }

  .calc {
    width: 320px;
    padding: 20px;
    border-radius: 22px;
    background: linear-gradient(160deg, #3b3f44, #25282c);
    box-shadow: 0 18px 40px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.15);
  }

  .brand {
    color: #aab0b6;
    font-size: 11px;
    letter-spacing: 2px;
    margin-bottom: 12px;
    display: flex;
    justify-content: space-between;
  }
  .brand span { color: #e0a030; }

  .screen {
    background: #b7c4a3;
    color: #1d2418;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 18px;
    box-shadow: inset 0 3px 8px rgba(0, 0, 0, 0.35);
    font-family: 'Courier New', monospace;
    text-align: right;
    min-height: 74px;
    overflow: hidden;
  }
  .expr {
    font-size: 15px;
    opacity: 0.7;
    overflow-x: auto;
    white-space: nowrap;
  }
  .out {
    font-size: 34px;
    font-weight: bold;
    margin-top: 4px;
    overflow-wrap: anywhere;
  }
  .screen.error .out { font-size: 14px; line-height: 1.3; color: #7a1a10; }

  .keys {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
  }

  button {
    height: 52px;
    border: none;
    border-radius: 10px;
    font-size: 20px;
    cursor: pointer;
    color: #f2f2f2;
    background: #5a5f66;
    box-shadow: 0 4px 0 #2f3236;
    transition: transform 0.05s, box-shadow 0.05s;
  }
  button:active {
    transform: translateY(3px);
    box-shadow: 0 1px 0 #2f3236;
  }
  button.fn { background: #c0463a; box-shadow: 0 4px 0 #7d2a22; }
  button.fn:active { box-shadow: 0 1px 0 #7d2a22; }
  button.op { background: #e0a030; color: #2b2208; box-shadow: 0 4px 0 #94691a; }
  button.op:active { box-shadow: 0 1px 0 #94691a; }
  button.eq {
    grid-column: 1 / -1;
    background: #3f8f5b;
    box-shadow: 0 4px 0 #265a39;
  }
  button.eq:active { box-shadow: 0 1px 0 #265a39; }
</style>
