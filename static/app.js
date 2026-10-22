/* Connect Four — browser controller and recorded-search explorer.
   All game rules and AI decisions remain on the Flask server. */
(() => {
    'use strict';

    const $ = (id) => document.getElementById(id);
    const boardEl = $('board');
    const statusEl = $('game-status');
    const messageEl = $('game-message');
    const algorithmEl = $('algorithm');
    const depthEl = $('depth');
    const simulationsEl = $('num-simulations');
    const slider = $('trace-step');
    const svg = $('tree-svg');
    const NS = 'http://www.w3.org/2000/svg';

    let game = null;
    let busy = false;
    let trace = null;
    let step = 0;
    let selectedNode = null;
    let playback = null;
    let replayState = new Map();

    async function api(path, data) {
        const options = data === undefined ? {} : {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        };
        const response = await fetch(path, options);
        let payload;
        try { payload = await response.json(); }
        catch { throw new Error(`Server returned HTTP ${response.status}`); }
        if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
        return payload;
    }

    function setBusy(value) {
        busy = value;
        $('new-game-btn').disabled = value;
        renderBoard();
    }

    function winningCells(board, player) {
        if (!player) return new Set();
        const directions = [[0, 1], [1, 0], [1, 1], [-1, 1]];
        for (let r = 0; r < 6; r++) for (let c = 0; c < 7; c++) {
            if (board[r][c] !== player) continue;
            for (const [dr, dc] of directions) {
                const cells = Array.from({ length: 4 }, (_, i) => [r + i * dr, c + i * dc]);
                if (cells.every(([rr, cc]) => rr >= 0 && rr < 6 && cc >= 0 && cc < 7 && board[rr][cc] === player)) {
                    return new Set(cells.map(([rr, cc]) => `${rr},${cc}`));
                }
            }
        }
        return new Set();
    }

    function renderBoard() {
        if (!game) return;
        const winning = winningCells(game.board, game.winner);
        boardEl.replaceChildren();
        const canPlay = !busy && !game.terminal && game.turn === 1;
        boardEl.classList.toggle('disabled', !canPlay);
        for (let r = 0; r < 6; r++) for (let c = 0; c < 7; c++) {
            const player = game.board[r][c];
            const cell = document.createElement('button');
            cell.type = 'button';
            cell.className = 'cell' + (player === 1 ? ' human' : player === 2 ? ' ai' : '') +
                (winning.has(`${r},${c}`) ? ' winning' : '');
            cell.setAttribute('role', 'gridcell');
            cell.setAttribute('aria-label', `Row ${r + 1}, column ${c + 1}: ${player === 1 ? 'red' : player === 2 ? 'yellow' : 'empty'}`);
            cell.disabled = !canPlay || !game.valid_moves.includes(c);
            cell.addEventListener('click', () => playColumn(c));
            boardEl.append(cell);
        }
        statusEl.className = 'status';
        if (game.winner === 1) { statusEl.textContent = 'You win!'; statusEl.classList.add('win'); }
        else if (game.winner === 2) { statusEl.textContent = 'AI wins'; statusEl.classList.add('lose'); }
        else if (game.draw) { statusEl.textContent = 'Draw'; }
        else if (busy || game.turn === 2) { statusEl.textContent = 'AI thinking…'; }
        else { statusEl.textContent = 'Your turn'; }
    }

    async function playColumn(column) {
        if (busy || !game || game.turn !== 1 || game.terminal) return;
        setBusy(true);
        messageEl.textContent = '';
        try {
            game = await api('/api/play', { column });
            renderBoard();
            if (!game.terminal) {
                const algorithm = algorithmEl.value;
                const options = { algorithm };
                if (algorithm === 'mcts') options.num_simulations = Number(simulationsEl.value);
                else if (algorithm !== 'random') options.depth = Number(depthEl.value);
                const answer = await api('/api/ai-move', options);
                game = answer.state;
                showStats(algorithm, answer.search);
                loadTrace(answer.search);
            }
        } catch (err) { messageEl.textContent = `Error: ${err.message}`; }
        finally { setBusy(false); }
    }

    function showStats(algorithm, search) {
        const names = { random: 'Random', minimax: 'Minimax', alphabeta: 'Alpha-Beta', mcts: 'MCTS' };
        $('stat-algorithm').textContent = names[algorithm] || algorithm;
        $('stat-move').textContent = search.move == null ? '—' : String(search.move + 1);
        $('stat-score').textContent = search.score == null ? '—' : String(search.score);
        $('stat-nodes').textContent = Number(search.nodes_explored).toLocaleString();
        $('stat-time').textContent = `${(search.time * 1000).toFixed(1)} ms`;
        $('stat-events').textContent = (search.events || []).length.toLocaleString();
    }

    function clearStats() {
        for (const id of ['stat-algorithm', 'stat-move', 'stat-score', 'stat-nodes', 'stat-time', 'stat-events']) $(id).textContent = '—';
    }

    function configure() {
        const name = algorithmEl.value;
        $('depth-settings').hidden = !['minimax', 'alphabeta'].includes(name);
        $('mcts-settings').hidden = name !== 'mcts';
        $('depth-value').textContent = depthEl.value;
    }

    function stopPlayback() {
        if (playback !== null) clearInterval(playback);
        playback = null;
        $('trace-play').textContent = '▶ Play';
    }

    function loadTrace(search) {
        stopPlayback();
        trace = search && search.search_tree && search.events && search.events.length ? {
            nodes: search.search_tree.nodes || [],
            events: search.events,
            truncated: Boolean(search.search_tree.truncated),
        } : null;
        step = 0;
        selectedNode = null;
        slider.max = trace ? String(trace.events.length) : '0';
        slider.value = '0';
        const available = Boolean(trace);
        for (const id of ['trace-first', 'trace-prev', 'trace-play', 'trace-next', 'trace-last', 'trace-step']) $(id).disabled = !available;
        $('trace-status').textContent = !trace ? 'No search recorded' :
            `${trace.nodes.length} visible nodes · ${trace.events.length} events${trace.truncated ? ' · tree truncated' : ''}`;
        renderTrace();
    }

    function eventState() {
        // Reconstruct node values at the current replay step, not their final values.
        const states = new Map();
        if (!trace) return states;
        for (let i = 0; i < step; i++) {
            const event = trace.events[i];
            if (event.node === null || event.node === undefined) continue;
            if (!states.has(event.node)) states.set(event.node, { visited: false, pruned: false });
            const s = states.get(event.node);
            if (event.type === 'visit') s.visited = true;
            if (event.type === 'prune') { s.pruned = true; s.skipped_moves = event.skipped_moves; }
            if (event.type === 'update') {
                for (const key of ['score', 'visits', 'mean_reward', 'alpha', 'beta', 'pruned']) {
                    if (Object.hasOwn(event, key)) s[key] = event[key];
                }
            }
        }
        return states;
    }

    function svgElement(tag, attrs, parent) {
        const el = document.createElementNS(NS, tag);
        for (const [key, value] of Object.entries(attrs || {})) el.setAttribute(key, String(value));
        if (parent) parent.appendChild(el);
        return el;
    }

    function treePositions(nodes) {
        // Leaf-order layout keeps siblings together and works for incomplete traces.
        const children = new Map(nodes.map(n => [n.id, []]));
        const roots = [];
        for (const node of nodes) {
            if (children.has(node.parent)) children.get(node.parent).push(node.id);
            else roots.push(node.id);
        }
        let leafIndex = 0;
        const pos = new Map();
        const visit = (id, level) => {
            const kids = children.get(id) || [];
            for (const kid of kids) visit(kid, level + 1);
            const x = kids.length ? (pos.get(kids[0]).x + pos.get(kids[kids.length - 1]).x) / 2 : leafIndex++ * 74 + 40;
            pos.set(id, { x, y: 45 + level * 90 });
        };
        for (const root of roots) visit(root, 0);
        return pos;
    }

    function renderTree(states, activeId) {
        svg.replaceChildren();
        const placeholder = $('tree-placeholder');
        if (!trace || !trace.nodes.length) {
            placeholder.hidden = false;
            svg.removeAttribute('viewBox');
            return;
        }
        placeholder.hidden = true;
        const visible = trace.nodes.filter(n => states.get(n.id)?.visited);
        if (!visible.length) { svg.setAttribute('viewBox', '0 0 600 350'); return; }
        const pos = treePositions(visible);
        const width = Math.max(600, ...[...pos.values()].map(p => p.x + 40));
        const height = Math.max(350, ...[...pos.values()].map(p => p.y + 45));
        svg.setAttribute('width', width);
        svg.setAttribute('height', height);
        svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
        for (const n of visible) {
            const a = pos.get(n.parent), b = pos.get(n.id);
            if (a && b) svgElement('path', { d: `M ${a.x} ${a.y + 18} L ${b.x} ${b.y - 18}`, class: 'tree-edge' }, svg);
        }
        for (const n of visible) {
            const p = pos.get(n.id), s = states.get(n.id) || {};
            const classes = ['tree-node', n.player === 2 ? 'max' : 'min'];
            if (n.id === activeId) classes.push('active');
            if (n.id === selectedNode) classes.push('selected');
            if (s.pruned) classes.push('pruned');
            const group = svgElement('g', { class: classes.join(' '), transform: `translate(${p.x} ${p.y})`, tabindex: '0', role: 'button', 'aria-label': `Node ${n.id}` }, svg);
            svgElement('circle', { r: 22 }, group);
            const title = svgElement('title', {}, group);
            title.textContent = `Node ${n.id}, move ${n.move == null ? 'root' : n.move + 1}`;
            const label = svgElement('text', { x: 0, y: -4 }, group);
            label.textContent = n.move == null ? 'ROOT' : String(n.move + 1);
            const score = svgElement('text', { x: 0, y: 11 }, group);
            score.textContent = s.score != null ? String(s.score) : s.mean_reward != null ? Number(s.mean_reward).toFixed(2) : '';
            group.addEventListener('click', () => { selectedNode = n.id; renderTrace(); });
            group.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectedNode = n.id; renderTrace(); } });
        }
    }

    function renderTrace() {
        slider.value = String(step);
        $('trace-counter').textContent = `${step} / ${trace ? trace.events.length : 0}`;
        if (!trace) {
            svg.replaceChildren();
            $('tree-placeholder').hidden = false;
            $('event-details').textContent = 'No event selected.';
            $('node-details').replaceChildren();
            return;
        }
        replayState = eventState();
        const event = step ? trace.events[step - 1] : null;
        renderTree(replayState, event?.node);
        $('event-details').textContent = event ? JSON.stringify({ step, ...event }, null, 2) : 'Ready. Press Next or Play to start replay.';
        const nodeId = selectedNode ?? event?.node;
        const node = trace.nodes.find(n => n.id === nodeId);
        const values = node ? { ...node, ...replayState.get(node.id) } : null;
        const details = $('node-details');
        details.replaceChildren();
        if (values) {
            for (const key of ['id', 'parent', 'move', 'player', 'depth', 'score', 'alpha', 'beta', 'visits', 'mean_reward', 'pruned']) {
                const row = document.createElement('div');
                const dt = document.createElement('dt'); dt.textContent = key.replaceAll('_', ' ');
                const dd = document.createElement('dd');
                let value = values[key];
                if (key === 'move' && value != null) value += 1;
                if (key === 'player') value = value === 2 ? 'AI / MAX' : 'Human / MIN';
                dd.textContent = value == null ? '—' : String(value);
                row.append(dt, dd); details.append(row);
            }
        } else { details.textContent = 'No node selected.'; }
    }

    function seek(nextStep) {
        if (!trace) return;
        step = Math.max(0, Math.min(trace.events.length, nextStep));
        renderTrace();
        if (step === trace.events.length) stopPlayback();
    }

    $('trace-first').addEventListener('click', () => { stopPlayback(); seek(0); });
    $('trace-prev').addEventListener('click', () => { stopPlayback(); seek(step - 1); });
    $('trace-next').addEventListener('click', () => { stopPlayback(); seek(step + 1); });
    $('trace-last').addEventListener('click', () => { stopPlayback(); seek(trace?.events.length || 0); });
    slider.addEventListener('input', () => { stopPlayback(); seek(Number(slider.value)); });
    $('trace-play').addEventListener('click', () => {
        if (!trace) return;
        if (playback !== null) { stopPlayback(); return; }
        if (step >= trace.events.length) seek(0);
        $('trace-play').textContent = '⏸ Pause';
        playback = setInterval(() => seek(step + 1), Number($('trace-speed').value));
    });
    $('trace-speed').addEventListener('change', () => {
        if (playback !== null) { stopPlayback(); $('trace-play').click(); }
    });
    algorithmEl.addEventListener('change', configure);
    depthEl.addEventListener('input', configure);
    $('new-game-btn').addEventListener('click', async () => {
        if (busy) return;
        setBusy(true);
        try {
            game = await api('/api/new-game', {});
            clearStats(); loadTrace(null); messageEl.textContent = '';
        } catch (err) { messageEl.textContent = `Error: ${err.message}`; }
        finally { setBusy(false); }
    });

    async function initialize() {
        configure(); clearStats(); loadTrace(null);
        try { game = await api('/api/state'); renderBoard(); }
        catch (err) { statusEl.textContent = 'Connection failed'; messageEl.textContent = `Error: ${err.message}`; }
    }
    initialize();
})();