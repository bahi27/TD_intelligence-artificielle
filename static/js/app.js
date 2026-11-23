(() => {
        const $ = id => document.getElementById(id);
        const colors = ['red', 'blue', 'green', 'yellow', 'white', 'orange'];
        const dirs = {
            N: { axis: 'NS', x: 465, y: -75, dx: 0, dy: 1, stop: 254, rotation: 180 },
            S: { axis: 'NS', x: 535, y: 1075, dx: 0, dy: -1, stop: 746, rotation: 0 },
            W: { axis: 'EW', x: -75, y: 535, dx: 1, dy: 0, stop: 254, rotation: 90 },
            E: { axis: 'EW', x: 1075, y: 465, dx: -1, dy: 0, stop: 746, rotation: 270 }
        };
        const laneIds = Object.keys(dirs);
        const arrivalRates = { low: 0.4, normal: 0.8, rush: 1.5 };
        const trafficStepSeconds = 3;
        let environment = { max_queue: 10, arrival_rate: 0.8, service_capacity: 2, switch_lost_steps: 1, switch_penalty: 0, max_arrivals: 3 };
        const lightPositions = [
            { x: 343, y: 287, axis: 'NS' }, { x: 657, y: 713, axis: 'NS' },
            { x: 287, y: 657, axis: 'EW' }, { x: 713, y: 343, axis: 'EW' }
        ];
        const place = (el, x, y) => {
            el.style.left = `${x/10}%`;
            el.style.top = `${y/10}%`;
        };

        const rand = (() => {
            let state = 1;

            return {
                reset() {
                    state = crypto.getRandomValues(new Uint32Array(1))[0];
                },

                next() {
                    state = (1664525 * state + 1013904223) >>> 0;
                    return state / 4294967296;
                }
            };
        })();

        class Intersection {
            constructor(prefix, automated = false) {
                this.prefix = prefix;
                this.automated = automated;
                this.carsLayer = $(`${prefix}-cars`);
                this.lightsLayer = $(`${prefix}-lights`);
                this.signals = [];
                this.reset();
                for (const p of lightPositions) {
                    const el = document.createElement('img');
                    el.className = 'light';
                    el.alt = '';
                    place(el, p.x, p.y);
                    this.lightsLayer.appendChild(el);
                    this.signals.push({...p, el });
                }
                this.updateSignals();
            }
            reset() {
                if (this.carsLayer) this.carsLayer.replaceChildren();
                this.cars = [];
                this.pending = { N: [], S: [], E: [], W: [] };
                this.green = 'NS';
                this.phase = 'green';
                this.phaseTime = 0;
                this.greenTime = 0;
                this.served = 0;
                this.arrived = 0;
                this.totalWait = 0;
                this.nextId = 0;
                this.switches = 0;
                this.lostSteps = 0;
                this.serviceTokens = environment.service_capacity;
                this.reward = 0;
                if (this.signals?.length) this.updateSignals();
                this.updateStats();
            }
            signalColor(axis) { return this.phase === 'green' ? (axis === this.green ? 'green' : 'red') : (this.phase === 'yellow' && axis === this.green ? 'yellow' : 'red'); }
            updateSignals() {
                for (const light of this.signals) light.el.src = `/static/assets/traffic_light_${this.signalColor(light.axis)}.svg`;
                for (const [axis, id] of[['NS', 'ns'], ['EW', 'ew']]) {
                    const el = $(`${this.prefix}-${id}-state`);
                    const color = this.signalColor(axis);
                    el.textContent = color.toUpperCase();
                    el.className = color;
                }
                const phase = $(`${this.prefix}-phase`);
                phase.textContent = this.phase === 'green' ? `${this.green==='NS'?'NORTH–SOUTH':'EAST–WEST'} GREEN` : (this.phase === 'yellow' ? 'YELLOW · CLEARING' : 'ALL RED · SAFETY');
                phase.style.color = this.phase === 'green' ? '#65e6ad' : '#ffd36d';
                if (!this.automated) $('switch').disabled = this.phase !== 'green' || this.lostSteps > 0 || paused || !matchActive;
            }
            switchLights() {
                if (this.phase !== 'green' || this.lostSteps > 0) return;
                this.switches++;
                this.reward -= environment.switch_penalty;
                this.lostSteps = environment.switch_lost_steps;
                this.serviceTokens = 0;
                this.phase = 'yellow';
                this.phaseTime = 0.9;
                this.updateSignals();
            }
            axisQueue(axis) { return this.cars.filter(c => dirs[c.dir].axis === axis && !c.committed).length + Object.entries(this.pending).filter(([dir]) => dirs[dir].axis === axis).reduce((n, [, q]) => n + q.length, 0); }
            receive(event) {
                if (this.axisQueue(dirs[event.dir].axis) >= environment.max_queue) return;
                this.pending[event.dir].push(event.color);
                this.arrived++;
            }
            mdpTick() {
                if (this.lostSteps > 0) {
                    this.lostSteps--;
                    this.serviceTokens = 0;
                } else this.serviceTokens = environment.service_capacity;
                this.reward -= this.axisQueue('NS') + this.axisQueue('EW');
                // Cooldown changes on MDP ticks, not on signal-phase transitions.
                // Refresh the manual button even if the lights remain green.
                if (!this.automated) this.updateSignals();
            }
            renderCar(c) {
                const d = dirs[c.dir];
                place(c.el, d.x + d.dx * c.progress, d.y + d.dy * c.progress);
            }
            spawnPending() {
                for (const key of laneIds) {
                    if (!this.pending[key].length || this.cars.some(c => c.dir === key && c.progress < 95)) continue;
                    const d = dirs[key],
                        color = this.pending[key].shift();
                    const el = document.createElement('img');
                    el.className = 'car';
                    el.alt = '';
                    el.src = `/static/assets/car_${color}.svg`;
                    el.style.transform = `translate(-50%,-50%) rotate(${d.rotation}deg)`;
                    this.carsLayer.appendChild(el);
                    const c = { id: this.nextId++, dir: key, progress: 0, waiting: 0, committed: false, el };
                    this.cars.push(c);
                    this.renderCar(c);
                }
            }
            updateStats() {
                $(`${this.prefix}-served`).textContent = this.served;
                $(`${this.prefix}-waiting`).textContent = this.cars.filter(c => c.waiting > 0).length + Object.values(this.pending).reduce((n, q) => n + q.length, 0);
                $(`${this.prefix}-arrived`).textContent = this.arrived;
                $(`${this.prefix}-waittime`).textContent = Math.floor(this.totalWait);
            }
            step(dt) {
                if (this.phase === 'green') {
                    this.greenTime += dt;
                    if (this.automated && activeModelId === null && this.greenTime >= 15) this.switchLights();
                } else {
                    this.phaseTime -= dt;
                    if (this.phaseTime <= 0) {
                        if (this.phase === 'yellow') {
                            this.phase = 'allred';
                            this.phaseTime = 0.65;
                        } else if (
                            this.lostSteps > 0 ||
                            this.cars.some(c => c.committed && c.progress < 760)
                        ) {
                            // Keep all-red until the cooldown ends and the intersection clears.
                            this.phaseTime = 0.1;
                        } else {
                            this.green = this.green === 'NS' ? 'EW' : 'NS';
                            this.phase = 'green';
                            this.greenTime = 0;
                            // Allow cars to start crossing as soon as green appears.
                            this.serviceTokens = environment.service_capacity;
                        }
                        this.updateSignals();
                    }
                }
                this.spawnPending();
                for (const key of laneIds) {
                    const d = dirs[key];
                    let prev = Infinity;
                    const lane = this.cars.filter(c => c.dir === key).sort((a, b) => b.progress - a.progress);
                    for (const c of lane) {
                        const distanceToStop = Math.abs(d.stop - (d.dx ? d.x : d.y));
                        const allowed = this.phase === 'green' && this.green === d.axis && (c.committed || this.serviceTokens > 0);
                        const limit = (allowed || c.committed) ? Infinity : distanceToStop;
                        const target = Math.min(c.progress + 155 * dt, limit, prev - 76);
                        const next = Math.max(c.progress, target);
                        if (next - c.progress < 1e-5) c.waiting += dt;
                        c.progress = next;
                        if (!c.committed && allowed && c.progress >= distanceToStop - 0.01) {
                            c.committed = true;
                            this.serviceTokens = Math.max(0, this.serviceTokens - 1);
                        }
                        prev = c.progress;
                        this.renderCar(c);
                    }
                }
                this.cars = this.cars.filter(c => {
                    if (c.progress > 1110) {
                        c.el.remove();
                        this.served++;
                        return false;
                    }
                    return true;
                });
                const waitingOnRoad = this.cars.filter(c => c.waiting > 0).length;
                const pendingCount = Object.values(this.pending).reduce((n, q) => n + q.length, 0);
                this.totalWait += (waitingOnRoad + pendingCount) * dt;
                this.updateStats();
            }
        }

        let paused = false,
            rate = 1,
            elapsed = 0,
            spawnClock = 0,
            last = performance.now();
        let matchFinished = false;
        let countdownTimer = null,
            matchActive = false;
        let activeModelId = null,
            decisionClock = 0,
            decisionBusy = false,
            decisionGeneration = 0;
        let decisionLog = [];
        const decisionInterval = 3;
        const fmtQ = n => n == null ? '—' : Number(n).toFixed(2);

        function observedState() {
            // Approximate the discrete MDP state from cars stopped at the signals + pending arrivals.
            const counts = { NS: 0, EW: 0 };
            for (const car of baseline.cars) {
                const d = dirs[car.dir];
                const distance = Math.abs(d.stop - (d.dx ? d.x : d.y));
                if (!car.committed && car.progress <= distance + 0.01) counts[d.axis]++;
            }
            for (const [dir, queue] of Object.entries(baseline.pending)) counts[dirs[dir].axis] += queue.length;
            const cap = activeModelConfig?.max_queue ?? environment.max_queue;
            return [Math.min(cap, counts.NS), Math.min(cap, counts.EW), baseline.green === 'NS' ? 0 : 1, Math.min((activeModelConfig?.switch_lost_steps ?? 1) - 1, Math.max(0, baseline.lostSteps - 1))];
        }
        let activeModelConfig = null;

        function drawDecisionHistory() {
            $('ai-history-body').replaceChildren();
            for (const row of[...decisionLog].reverse()) {
                const tr = document.createElement('tr');
                for (const value of[row.time, row.state.slice(0, 3).join(', '), fmtQ(row.keep), fmtQ(row.switch), row.action]) {
                    const td = document.createElement('td');
                    td.textContent = value;
                    tr.appendChild(td);
                }
                $('ai-history-body').appendChild(tr);
            }
            const chart = $('ai-q-chart');
            chart.replaceChildren();
            const data = decisionLog.slice(-20),
                series = [
                    ['keep', '#5ce4af'],
                    ['switch', '#f2b36a']
                ];
            const nums = data.flatMap(row => [row.keep, row.switch]).filter(Number.isFinite);
            if (!nums.length) return;
            const lo = Math.min(...nums),
                hi = Math.max(...nums),
                range = Math.max(1, hi - lo);
            const ns = 'http://www.w3.org/2000/svg';
            for (const [key, color] of series) {
                const points = data.map((row, i) => Number.isFinite(row[key]) ? `${25+i*450/Math.max(1,data.length-1)},${135-(row[key]-lo)/range*110}` : null).filter(Boolean);
                if (points.length < 2) continue;
                const poly = document.createElementNS(ns, 'polyline');
                poly.setAttribute('points', points.join(' '));
                poly.setAttribute('fill', 'none');
                poly.setAttribute('stroke', color);
                poly.setAttribute('stroke-width', '3');
                chart.appendChild(poly);
            }
            const label = document.createElementNS(ns, 'text');
            label.setAttribute('x', '25');
            label.setAttribute('y', '153');
            label.setAttribute('fill', '#a8bfcb');
            label.setAttribute('font-size', '12');
            label.textContent = `KEEP (green) / SWITCH (orange) · ${data.length} decisions`;
            chart.appendChild(label);
        }
        async function loadOpponent() {
            const selected = $('setup-model').value;
            const generation = ++decisionGeneration;
            activeModelId = null;
            activeModelConfig = null;
            decisionLog = [];
            decisionClock = 0;
            decisionBusy = false;
            $('ai-history-panel').hidden = mode !== 'versus';
            $('ai-q-keep').textContent = '—';
            $('ai-q-switch').textContent = '—';
            $('ai-choice').textContent = 'Waiting for decision';
            $('ai-state').textContent = 'Waiting for traffic…';
            if (mode !== 'versus' || selected === 'baseline') {
                $('ai-controller').textContent = 'Fixed-time baseline';
                $('ai-explanation').textContent = 'Switch after 15 seconds of green.';
                $('ai-controller-note').textContent = 'Automatic controller · switches every 15 s of green';
                $('ai-history-panel').hidden = true;
                $('baseline-arena').querySelector('h1').textContent = '🤖 Fixed-time baseline';
                return;
            }
            const response = await fetch(`/api/training/models/${encodeURIComponent(selected)}`);
            if (!response.ok) throw Error(`Cannot load selected model (HTTP ${response.status})`);
            const model = await response.json();
            if (generation !== decisionGeneration) return;
            activeModelId = selected;
            activeModelConfig = model.settings.mdp;
            const label = model.settings.algorithm === 'value_iteration' ? 'Value Iteration' : 'Policy Iteration';
            $('baseline-arena').querySelector('h1').textContent = `🤖 ${label}`;
            $('ai-controller').textContent = label;
            $('ai-controller-note').textContent = `Learned policy · decision every ${decisionInterval} s (approximate MDP state)`;
            $('ai-explanation').textContent = 'Actions are selected from the trained policy; Q-values are evaluated with the saved MDP.';
            drawDecisionHistory();
        }
        async function aiDecision() {
            if (!activeModelId || decisionBusy || paused || !matchActive || baseline.phase !== 'green' || baseline.lostSteps > 0) return;
            decisionBusy = true;
            const generation = decisionGeneration,
                state = observedState(),
                modelId = activeModelId;
            try {
                const response = await fetch(`/api/training/models/${encodeURIComponent(modelId)}/decision`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ state })
                });
                const data = await response.json();
                if (!response.ok) throw Error(data.error || `HTTP ${response.status}`);
                if (generation !== decisionGeneration || paused || !matchActive || baseline.phase !== 'green') return;
                const keep = data.actions.KEEP?.q ?? null,
                    sw = data.actions.SWITCH?.q ?? null;
                $('ai-state').textContent = `State: (${state.join(', ')}) · NS ${state[0]} / EW ${state[1]}`;
                $('ai-q-keep').textContent = fmtQ(keep);
                $('ai-q-switch').textContent = fmtQ(sw);
                document.querySelectorAll('.q-row').forEach(el => el.classList.toggle('best', el.textContent.includes(data.action)));
                $('ai-choice').textContent = `${data.action==='SWITCH'?'⇄ SWITCH':'✓ KEEP'} · ${data.action==='SWITCH'?'Change green axis':'Maintain green axis'}`;
                const winner = data.actions[data.action];
                $('ai-explanation').textContent = sw == null ? 'Switch unavailable during cooldown.' : `Best action: ${data.action} · ΔQ = ${Math.abs(keep-sw).toFixed(2)}`;
                $('ai-bellman-breakdown').textContent = `For ${data.action}: E[R] = ${fmtQ(winner.immediate)}, γ E[V(s′)] = ${fmtQ(winner.future)}, Q = ${fmtQ(winner.q)} (γ = ${data.gamma}).`;
                decisionLog.push({ time: `${Math.floor(elapsed/60).toString().padStart(2,'0')}:${Math.floor(elapsed%60).toString().padStart(2,'0')}`, state, keep, switch: sw, action: data.action });
                if (decisionLog.length > 20) decisionLog.shift();
                drawDecisionHistory();
                if (data.action === 'SWITCH') baseline.switchLights();
            } catch (err) {
                $('ai-choice').textContent = `AI decision error: ${err.message}`;
                paused = true;
                $('status').textContent = 'Match paused: AI decision failed';
            } finally { if (generation === decisionGeneration) decisionBusy = false; }
        }

        const matchDuration = () => Number($('match-duration').value);
        let mode = 'train';
        const human = new Intersection('human');
        const baseline = new Intersection('baseline', true);

        function reset() {
            human.reset();
            baseline.reset();
            rand.reset();
            paused = true;
            elapsed = 0;
            spawnClock = 0;
            matchFinished = false;
            decisionClock = 0;
            decisionGeneration++;
            decisionBusy = false;
            $('match-result').hidden = true;
            $('pause').textContent = 'Ⅱ Pause simulation';
            $('clock').textContent = `${String(Math.floor(matchDuration()/60)).padStart(2,'0')}:00 remaining`;
            $('status').textContent = 'Both intersections receive identical arrivals';
            human.updateSignals();
            $('pause').disabled = false;
        }
        const queueCount = sim => sim.cars.filter(c => c.waiting > 0).length + Object.values(sim.pending).reduce((n, q) => n + q.length, 0);

        function finishMatch() {
            matchFinished = true;
            paused = true;
            human.updateSignals();
            const versus = mode === 'versus';
            const diff = human.totalWait - baseline.totalWait;
            const tie = versus && Math.abs(diff) < 0.001;
            const win = versus && diff < 0;
            $('result-icon').textContent = versus ? (tie ? '🤝' : win ? '🏆' : '🤖') : '🚦';
            $('result-heading').textContent = versus ? (tie ? 'It’s a tie!' : win ? 'Human wins!' : 'AI wins!') : 'Shift complete!';
            $('result-message').textContent = versus ? (tie ? 'A photo finish. Even the traffic lights are undecided.' : win ? 'You outsmarted the algorithm. The machines request a rematch.' : 'The toaster has a traffic engineering degree now. Rematch?') : 'Your traffic-control shift is over. Here is how you did.';
            $('result-message').textContent += ` · Reward score: human ${human.reward.toFixed(0)}${versus?`, AI ${baseline.reward.toFixed(0)}`:''} (queue cost + switching penalty).`;
    $('result-opponent-title').textContent=versus?$('baseline-arena').querySelector('h1').textContent.replace('🤖 ',''):'—';
    $('result-human-wait').textContent=`${human.totalWait.toFixed(1)} s`;
    $('result-human-served').textContent=human.served;
    $('result-human-avg').textContent=`${(human.totalWait/Math.max(1,human.arrived)).toFixed(1)} s`;
    $('result-human-queue').textContent=queueCount(human);
    $('result-ai-wait').textContent=versus?`${baseline.totalWait.toFixed(1)} s`:'—';
    $('result-ai-served').textContent=versus?baseline.served:'—';
    $('result-ai-avg').textContent=versus?`${(baseline.totalWait/Math.max(1,baseline.arrived)).toFixed(1)} s`:'—';
    $('result-ai-queue').textContent=versus?queueCount(baseline):'—';
    $('result-confetti').classList.toggle('celebrate',win);
    $('status').textContent='Match complete';
    $('pause').disabled=true;
    $('match-result').hidden=false;
    $('play-again').focus();
  }
  function step(dt){
    dt=Math.min(dt,matchDuration()-elapsed);
    elapsed+=dt;spawnClock+=dt;
    while(spawnClock>=trafficStepSeconds){
      spawnClock-=trafficStepSeconds;
      // One independent, truncated Poisson draw per axis, as in the MDP.
      for(const axis of ['NS','EW']){
        let arrivals=0,product=1,threshold=Math.exp(-environment.arrival_rate);
        do{product*=rand.next();if(product>threshold)arrivals++;}while(product>threshold && arrivals<environment.max_arrivals);
        for(let k=0;k<arrivals;k++){
          const lanes=axis==='NS'?['N','S']:['E','W'];
          const event={dir:lanes[Math.floor(rand.next()*2)],color:colors[Math.floor(rand.next()*colors.length)]};
          human.receive(event);if(mode==='versus')baseline.receive(event);
        }
      }
      human.mdpTick();if(mode==='versus')baseline.mdpTick();
    }
    human.step(dt);if(mode==='versus'){baseline.step(dt);if(activeModelId){decisionClock+=dt;if(decisionClock>=decisionInterval){decisionClock=0;aiDecision();}}else{$('ai-state').textContent=`Green ${baseline.green} · ${Math.max(0,15-baseline.greenTime).toFixed(1)} s until switch`;$('ai-choice').textContent='Fixed-time rule';}}
    const remaining=Math.max(0,Math.ceil(matchDuration()-elapsed));
    $('clock').textContent=`${String(Math.floor(remaining/60)).padStart(2,'0')}:${String(remaining%60).padStart(2,'0')} remaining`;
    $('match-timer-hud').classList.toggle('timer-urgent',remaining<=10 && remaining>0);
    if(elapsed>=matchDuration()-1e-6)finishMatch();
  }
  $('switch').addEventListener('click',()=>human.switchLights());
  $('pause').addEventListener('click',()=>{
    if(matchFinished)return;
    paused=!paused;$('pause').textContent=paused?'▶ Resume simulation':'Ⅱ Pause simulation';
    $('status').textContent=paused?'Simulation paused':'Both intersections receive identical arrivals';
    human.updateSignals();
  });
  const modelConfigs = new Map();
  const environmentFields = [
    ['arrival_rate','Traffic intensity','setup-traffic'],
    ['max_queue','Maximum queue / axis','setup-queues'],
    ['service_capacity','Service capacity / step','setup-service'],
    ['switch_lost_steps','Switch cooldown / steps','setup-cooldown'],
    ['switch_penalty','Switching penalty β','setup-penalty'],
    ['max_arrivals','Maximum arrivals / step','setup-arrivals']
  ];
  function gameEnvironmentFromSetup(){
    return {
      arrival_rate:arrivalRates[$('setup-traffic').value],
      max_queue:Number($('setup-queues').value),
      service_capacity:Number($('setup-service').value),
      switch_lost_steps:Number($('setup-cooldown').value),
      switch_penalty:Number($('setup-penalty').value),
      max_arrivals:Number($('setup-arrivals').value)
    };
  }
  function displayEnvironmentValue(key,value){
    if(value===undefined||value===null||!Number.isFinite(Number(value)))return 'Unknown';
    if(key==='arrival_rate'){
      const preset=Object.keys(arrivalRates).find(k=>Math.abs(arrivalRates[k]-Number(value))<1e-9);
      return preset?({low:'Low',normal:'Normal',rush:'Rush Hour'}[preset]):`λ=${value} (no preset)`;
    }
    return String(value);
  }
  function renderOpponentEnvironment(){
    const panel=$('opponent-environment');
    const id=$('setup-model').value;
    const cfg=modelConfigs.get(id);
    panel.hidden=mode!=='versus'||id==='baseline';
    if(panel.hidden)return;
    const details=$('opponent-environment-details');
    details.replaceChildren();
    const game=gameEnvironmentFromSetup();
    if(!cfg){
      $('opponent-environment-status').textContent='Loading training configuration…';
      $('use-ai-environment').disabled=true;
      return;
    }
    const mismatches=[];
    for(const [key,label] of environmentFields){
      const trained=cfg[key];
      const different=!Number.isFinite(Number(trained))||!Number.isFinite(Number(game[key]))||Math.abs(Number(trained)-Number(game[key]))>1e-9;
      if(different)mismatches.push(label);
      const row=document.createElement('div');row.className=`opponent-environment-row${different?' mismatch':''}`;
      for(const value of [label,displayEnvironmentValue(key,trained),displayEnvironmentValue(key,game[key])]){
        const cell=document.createElement('span');cell.textContent=value;row.appendChild(cell);
      }
      details.appendChild(row);
    }
    $('use-ai-environment').disabled=false;
    $('opponent-environment-status').textContent=mismatches.length
      ?`⚠ Environment mismatch: ${mismatches.join(', ')}. You can still play, but the AI was trained under different conditions.`
      :'✓ Environment match — game settings match the AI training MDP.';
    $('opponent-environment-status').classList.toggle('mismatch',mismatches.length>0);
  }
  async function showSelectedOpponentEnvironment(){
    const id=$('setup-model').value;
    renderOpponentEnvironment();
    if(id==='baseline'||modelConfigs.has(id))return;
    try{
      const response=await fetch(`/api/training/models/${encodeURIComponent(id)}`);
      if(!response.ok)throw Error(`HTTP ${response.status}`);
      const model=await response.json();
      if(model.settings?.mdp)modelConfigs.set(id,model.settings.mdp);
      if($('setup-model').value===id)renderOpponentEnvironment();
    }catch(err){if($('setup-model').value===id)$('opponent-environment-status').textContent=`Cannot read model configuration: ${err.message}`;}
  }
  $('setup-model').addEventListener('change',showSelectedOpponentEnvironment);
  for(const id of ['setup-traffic','setup-queues','setup-service','setup-cooldown','setup-penalty','setup-arrivals']){
    $(id).addEventListener('input',renderOpponentEnvironment);
    $(id).addEventListener('change',renderOpponentEnvironment);
  }
  $('use-ai-environment').addEventListener('click',()=>{
    const cfg=modelConfigs.get($('setup-model').value);
    if(!cfg)return;
    const preset=Object.keys(arrivalRates).find(k=>Math.abs(arrivalRates[k]-Number(cfg.arrival_rate))<1e-9);
    if(!preset){$('opponent-environment-status').textContent='This model uses an arrival rate outside the available traffic-intensity presets.';return;}
    const queueOption=[...$('setup-queues').options].find(o=>Number(o.value)===Number(cfg.max_queue));
    if(!queueOption){$('opponent-environment-status').textContent='This model uses a maximum queue size not available in the game selector.';return;}
    $('setup-traffic').value=preset;
    $('setup-queues').value=queueOption.value;
    for(const [key,id] of [['service_capacity','setup-service'],['switch_lost_steps','setup-cooldown'],['switch_penalty','setup-penalty'],['max_arrivals','setup-arrivals']]){
      $(id).value=cfg[key];
    }
    renderOpponentEnvironment();
  });
  function showSetup(){
    const solo=mode==='solo';
    $('setup-eyebrow').textContent=solo?'PLAY ALONE · GAME SETUP':'HUMAN VS AI · MATCH SETUP';
    $('setup-title').textContent=solo?'Configure your game':'Configure your match';
    $('setup-description').textContent=solo?'Configure your traffic environment and game duration.':'Choose an opponent and configure the traffic environment for both intersections.';
    $('setup-model-field').hidden=solo; $('setup-model-note').hidden=solo;
    if(!solo)showSelectedOpponentEnvironment();else $('opponent-environment').hidden=true;
    $('countdown-mode').textContent=solo?'Play Alone':'Human vs AI';
    clearInterval(countdownTimer);countdownTimer=null;matchActive=false;paused=true;activeModelId=null;decisionGeneration++;
    $('match-countdown').hidden=true;$('match-setup').hidden=false;
    $('play-screen').classList.add('setup-active');
    document.querySelector('#play-screen .mode-banner').hidden=true;$('game-main').hidden=true;
    document.querySelector('#play-screen .game-bar').hidden=true;$('match-timer-hud').hidden=true;
  }
  async function beginMatch(){
    clearInterval(countdownTimer);
    $('model-select').value=$('setup-model').value;
    $('match-duration').value=$('setup-duration').value;
    environment={
      max_queue:Number($('setup-queues').value),
      arrival_rate:arrivalRates[$('setup-traffic').value],
      service_capacity:Number($('setup-service').value),
      switch_lost_steps:Number($('setup-cooldown').value),
      switch_penalty:Number($('setup-penalty').value),
      max_arrivals:Number($('setup-arrivals').value)
    };
    if(!Number.isInteger(environment.service_capacity)||environment.service_capacity<1||environment.service_capacity>10||
       !Number.isInteger(environment.switch_lost_steps)||environment.switch_lost_steps<1||environment.switch_lost_steps>5||
       !Number.isInteger(environment.max_arrivals)||environment.max_arrivals<1||environment.max_arrivals>10||
       !Number.isFinite(environment.switch_penalty)||environment.switch_penalty<0||environment.switch_penalty>100){
      $('environment-warning').hidden=false;$('environment-warning').textContent='Please enter valid environment parameters.';return;
    }
    $('environment-warning').hidden=true;
    rate=environment.arrival_rate;
    document.querySelectorAll('[data-rate]').forEach(b=>b.classList.toggle('selected',Math.abs(Number(b.dataset.rate)-({0.4:0.55,0.8:1,1.5:1.7}[rate]))<0.01));
    reset();paused=true;matchActive=false;
    $('start-match').disabled=true;
    try{await loadOpponent();
      if(activeModelConfig){
        const differences=Object.keys(environment).filter(k=>Math.abs(Number(activeModelConfig[k])-environment[k])>1e-9);
        if(differences.length){$('environment-warning').hidden=false;$('environment-warning').textContent=`⚠ AI trained in a different MDP (${differences.join(', ')}). Its policy may perform differently.`;$('ai-controller-note').textContent+=` · ⚠ Mismatch: ${differences.join(', ')}`;}
      }
    }
    catch(err){$('setup-model-note').textContent=`Cannot start match: ${err.message}`;$('start-match').disabled=false;return;}
    $('start-match').disabled=false;
    $('match-setup').hidden=true;$('match-countdown').hidden=false;
    $('play-screen').classList.add('setup-active');
    let count=3;$('countdown-number').textContent=count;
    countdownTimer=setInterval(()=>{
      count--;
      if(count>0){$('countdown-number').textContent=count;return;}
      clearInterval(countdownTimer);countdownTimer=null;
      if(mode!=='versus'&&mode!=='solo')return;
      $('match-countdown').hidden=true;document.querySelector('#play-screen .mode-banner').hidden=false;
      $('game-main').hidden=false;document.querySelector('.game-bar').hidden=false;$('match-timer-hud').hidden=false;
      $('play-screen').classList.remove('setup-active');
      matchActive=true;paused=false;human.updateSignals();
    },1000);
  }
  $('start-match').addEventListener('click',beginMatch);
  $('restart').addEventListener('click',()=>{if(mode==='versus'||mode==='solo'){reset();showSetup();}else reset();});
  $('play-again').addEventListener('click',()=>{if(mode==='versus'||mode==='solo'){reset();showSetup();}else reset();});
  $('match-duration').addEventListener('change',reset);
  document.querySelectorAll('[data-rate]').forEach(btn=>btn.addEventListener('click',()=>{
    rate=Number(btn.dataset.rate);environment.arrival_rate=({0.55:0.4,1:0.8,1.7:1.5})[rate];spawnClock=0;
    document.querySelectorAll('[data-rate]').forEach(b=>b.classList.toggle('selected',b===btn));
  }));
  function selectMode(next){
    mode=next;
    document.querySelectorAll('[data-tab]').forEach(btn=>{
      const selected=btn.dataset.tab===next;
      btn.classList.toggle('selected',selected);
      btn.setAttribute('aria-selected',String(selected));
    });
    $('train-screen').hidden=next!=='train';
    $('play-screen').hidden=next==='train';
    $('baseline-arena').hidden=next!=='versus';
    $('game-main').classList.toggle('solo',next==='solo');
    $('model-picker').hidden=true; // Opponent selection belongs exclusively to match setup.
    $('mode-heading').textContent=next==='solo'?'Play Alone':'Human vs AI';
    $('mode-description').textContent=next==='solo'?'Practice controlling one intersection.':'Identical traffic arrivals · learned policy or fixed-time opponent';
    $('status').textContent=next==='versus'?'Both intersections receive identical arrivals':'Human-controlled intersection';
    clearInterval(countdownTimer);countdownTimer=null;
    reset();
    if(next==='versus'||next==='solo')showSetup();
    else{$('play-screen').classList.remove('setup-active');$('match-setup').hidden=true;$('match-countdown').hidden=true;document.querySelector('#play-screen .mode-banner').hidden=false;$('game-main').hidden=false;document.querySelector('.game-bar').hidden=false;$('match-timer-hud').hidden=false;matchActive=false;}
    paused=true;
    $('pause').textContent=paused?'▶ Resume simulation':'Ⅱ Pause simulation';
    human.updateSignals();
  }
  document.querySelectorAll('[data-tab]').forEach(btn=>btn.addEventListener('click',()=>selectMode(btn.dataset.tab)));
  $('train-algorithm').addEventListener('change',e=>{$('policy-eval-field').hidden=e.target.value!=='pi';});
  initTraining();
  function initTraining(){
    const button=$('train-start'), status=$('train-status'), summary=$('train-summary');
    const log=$('train-console'), chart=$('train-chart'), count=$('train-chart-count');
    let source=null, points=[], busy=false;
    const append=(line)=>{log.textContent+='\n'+line;log.scrollTop=log.scrollHeight;};
    const setBusy=(value)=>{busy=value;button.disabled=value;button.textContent=value?'◌ Training…':'▶ Start training';};
    const escapeXml=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
    function render(){
      count.textContent=`${points.length} iteration${points.length===1?'':'s'}`;
      if(!points.length){chart.innerHTML='<text x="310" y="115" text-anchor="middle" fill="#93a9b6">Waiting for iterations…</text>';return;}
      const W=620,H=230,L=60,R=16,T=20,B=36;
      const xs=points.map(p=>p.iteration), ys=points.map(p=>Math.log10(Math.max(Number(p.delta),1e-12)));
      const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
      const x=v=>L+(v-minX)/Math.max(1,maxX-minX)*(W-L-R);
      const y=v=>H-B-(v-minY)/Math.max(1e-9,maxY-minY)*(H-T-B);
      const coords=points.map((p,i)=>`${x(xs[i]).toFixed(1)},${y(ys[i]).toFixed(1)}`).join(' ');
      const ticks=[0,1,2,3,4].map(i=>{const v=minY+(maxY-minY)*i/4;const yy=y(v);return `<line x1="${L}" y1="${yy}" x2="${W-R}" y2="${yy}" stroke="#34515d" stroke-dasharray="3 5"/><text x="${L-9}" y="${yy+4}" fill="#9ab5c2" font-size="11" text-anchor="end">${v.toFixed(1)}</text>`;}).join('');
      chart.innerHTML=`${ticks}<line x1="${L}" y1="${H-B}" x2="${W-R}" y2="${H-B}" stroke="#678391"/><polyline points="${escapeXml(coords)}" fill="none" stroke="#50e3b2" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/><circle cx="${x(xs.at(-1))}" cy="${y(ys.at(-1))}" r="4" fill="#f7d46a"/><text x="${L}" y="${H-10}" fill="#9ab5c2" font-size="11">${minX}</text><text x="${W-R}" y="${H-10}" text-anchor="end" fill="#9ab5c2" font-size="11">${maxX} iterations</text><text x="${L}" y="12" fill="#9ab5c2" font-size="11">log₁₀(Δ)</text>`;
    }
    const config=()=>({
      algorithm:$('train-algorithm').value==='vi'?'value_iteration':'policy_iteration',
      gamma:Number($('train-gamma').value),epsilon:Number($('train-epsilon').value),
      max_iterations:Number($('train-max-iterations').value),
      arrival_rate:arrivalRates[$('train-traffic').value],
      max_queue:Number($('train-queues').value),service_capacity:Number($('train-service').value),
      switch_lost_steps:Number($('train-cooldown').value),switch_penalty:Number($('train-penalty').value),max_arrivals:Number($('train-arrivals').value),
      evaluation_epsilon:Number($('train-policy-epsilon').value)
    });
    async function refreshModels(){
      try{
        const res=await fetch('/api/training/models');if(!res.ok)throw Error(`HTTP ${res.status}`);
        const {models=[]}=await res.json(),select=$('model-select'),current=select.value;
        select.replaceChildren(new Option('Fixed-time baseline · 15 s (demo)','baseline'));
        modelConfigs.clear();
        for(const m of models){if(m.settings?.mdp)modelConfigs.set(m.model_id,m.settings.mdp);const label=`${m.settings.algorithm==='value_iteration'?'Value Iteration':'Policy Iteration'} · γ=${m.settings.gamma} · ${Object.keys(arrivalRates).find(k=>arrivalRates[k]===m.settings.mdp.arrival_rate)||'λ='+m.settings.mdp.arrival_rate} · ${m.model_id.slice(0,8)}`;select.add(new Option(label,m.model_id));}
        if([...select.options].some(o=>o.value===current))select.value=current;
        const setupSelect=$('setup-model'),setupCurrent=setupSelect.value;
        setupSelect.replaceChildren(...[...select.options].map(o=>new Option(o.textContent,o.value)));
        if([...setupSelect.options].some(o=>o.value===setupCurrent))setupSelect.value=setupCurrent;
        if(mode==='versus')showSelectedOpponentEnvironment();
        // Saved models are selectable opponents with live policy execution.
        const hint=document.querySelector('#model-picker small');
        if(hint)hint.textContent=models.length?`${models.length} saved model(s) · Trained controllers ready to play.`:'Train a model to make it available here.';
      }catch(err){append(`[WARN] Could not load saved models: ${err.message}`);}
    }
    button.addEventListener('click',async()=>{
      if(busy)return;
      if(source){source.close();source=null;}
      points=[];render();log.textContent='[START] Submitting training configuration…';
      summary.textContent='Training in progress…';status.textContent='TRAINING';setBusy(true);
      try{
        const response=await fetch('/api/training/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(config())});
        const payload=await response.json();
        if(!response.ok)throw Error(payload.error||`HTTP ${response.status}`);
        append(`[JOB] ${payload.job_id}`);
        source=new EventSource(payload.stream_url);
        source.addEventListener('iteration',event=>{
          const row=JSON.parse(event.data);points.push(row);render();
          append(`[${String(row.iteration).padStart(4,'0')}] Δ=${Number(row.delta).toExponential(3)} · policy changes=${row.policy_changes} · ${(row.elapsed_seconds*1000).toFixed(1)} ms${row.evaluation_iterations!=null?' · evaluation steps='+row.evaluation_iterations:''}`);
        });
        source.addEventListener('complete',async event=>{
          const data=JSON.parse(event.data);
          if(data.cached&&Array.isArray(data.history)){points=data.history;render();append(`[CACHE] Reused existing trained model ${data.model_id}`);}
          const r=data.result;
          status.textContent=r.converged?'CONVERGED':'LIMIT REACHED';
          summary.textContent=`${r.converged?'Converged':'Stopped without convergence'} · ${r.iterations} iterations · ${(r.elapsed_seconds*1000).toFixed(1)} ms${data.model_id?' · model '+data.model_id.slice(0,8):''}`;
          append(`[DONE] ${summary.textContent}`);
          await refreshModels();
        });
        source.addEventListener('error',event=>{
          if(event instanceof MessageEvent){try{append(`[ERROR] ${JSON.parse(event.data).message}`);}catch{append('[ERROR] Training failed.');}}
          else append('[ERROR] Training stream disconnected.');
          status.textContent='ERROR';summary.textContent='Training failed or connection lost.';
          source?.close();source=null;setBusy(false);
        });
        source.addEventListener('end',()=>{source?.close();source=null;setBusy(false);});
      }catch(err){append(`[ERROR] ${err.message}`);summary.textContent=err.message;status.textContent='ERROR';setBusy(false);}
    });
    refreshModels();
  }

  function frame(now){const dt=Math.min((now-last)/1000,.06);last=now;if(!paused&&mode!=='train'&&matchActive)step(dt);requestAnimationFrame(frame);}
  selectMode('train');requestAnimationFrame(frame);
})();