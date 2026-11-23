"""Flask Blueprint for training TrafficMDP policies.

Register with: app.register_blueprint(training_bp)
Optional: set TRAFFICRL_MODEL_DIR to choose the persistent model directory.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
from queue import Queue
from threading import Lock, Thread
from uuid import uuid4

from flask import Blueprint, Response, jsonify, request, stream_with_context, current_app

from .mdp import MDPConfig, TrafficMDP
from .solvers import policy_iteration, value_iteration

training_bp = Blueprint('trafficrl_training', __name__)
_jobs: dict[str, dict] = {}
_lock = Lock()


def _model_dir() -> Path:
    path = Path(os.environ.get('TRAFFICRL_MODEL_DIR', 'models/trafficrl'))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _number(obj, key, default, low, high, integer=False):
    val = obj.get(key, default)
    if isinstance(val, bool) or not isinstance(val, (int, float)) or (integer and not isinstance(val, int)):
        raise ValueError(f'{key} must be a {"integer" if integer else "number"}')
    if not low <= val <= high:
        raise ValueError(f'{key} must be between {low} and {high}')
    return val


def _parameters(data):
    if not isinstance(data, dict):
        raise ValueError('Expected a JSON object')
    algorithm = data.get('algorithm', 'value_iteration')
    if algorithm not in ('value_iteration', 'policy_iteration'):
        raise ValueError('algorithm must be value_iteration or policy_iteration')
    config = MDPConfig(
        max_queue=_number(data, 'max_queue', 10, 1, 30, True),
        arrival_rate=_number(data, 'arrival_rate', 0.8, 0, 10),
        service_capacity=_number(data, 'service_capacity', 2, 1, 10, True),
        switch_lost_steps=_number(data, 'switch_lost_steps', 1, 1, 5, True),
        switch_penalty=_number(data, 'switch_penalty', 0, 0, 100),
        max_arrivals=_number(data, 'max_arrivals', 3, 1, 10, True),
    )
    settings = {
        'algorithm': algorithm,
        'gamma': _number(data, 'gamma', 0.95, 0, 0.999),
        'epsilon': _number(data, 'epsilon', 0.001, 1e-10, 1),
        'max_iterations': _number(data, 'max_iterations', 1000, 1, 10000, True),
        'evaluation_epsilon': _number(data, 'evaluation_epsilon', 1e-5, 1e-10, 1),
        'max_evaluation_iterations': _number(data, 'max_evaluation_iterations', 10000, 1, 100000, True),
        'mdp': asdict(config),
    }
    return settings, config


def _key(settings):
    return sha256(json.dumps(settings, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:24]


def _path(model_id):
    if not isinstance(model_id, str) or len(model_id) != 24 or any(c not in '0123456789abcdef' for c in model_id):
        raise ValueError('Invalid model ID')
    return _model_dir() / f'{model_id}.json'


def _load(model_id):
    path = _path(model_id)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def _worker(job_id, settings, config, model_id):
    with _lock:
        job = _jobs[job_id]
    def emit(event, payload):
        job['events'].put({'event': event, 'data': payload})
    try:
        cached = _load(model_id)
        if cached is not None:
            emit('complete', {'model_id': model_id, 'cached': True, 'result': cached['summary'], 'history': cached['history']})
            return
        mdp = TrafficMDP(config)
        kwargs = dict(gamma=settings['gamma'], epsilon=settings['epsilon'],
                      max_iterations=settings['max_iterations'],
                      on_iteration=lambda record: emit('iteration', record))
        if settings['algorithm'] == 'value_iteration':
            result = value_iteration(mdp, **kwargs)
        else:
            result = policy_iteration(mdp, evaluation_epsilon=settings['evaluation_epsilon'],
                                      max_evaluation_iterations=settings['max_evaluation_iterations'], **kwargs)
        summary = {'converged': result.converged, 'iterations': result.iterations,
                   'elapsed_seconds': result.elapsed_seconds, 'n_states': len(mdp.states)}
        payload = {'model_id': model_id, 'settings': settings, 'summary': summary,
                   'history': result.history,
                   'policy': [{'state': list(s), 'action': a} for s, a in result.policy.items()],
                   'values': [{'state': list(s), 'value': v} for s, v in result.values.items()]}
        # Never cache an incomplete solution as a trained model.
        if result.converged:
            path = _path(model_id)
            tmp = path.with_name(f'{path.name}.{uuid4().hex}.tmp')
            tmp.write_text(json.dumps(payload, allow_nan=False), encoding='utf-8')
            tmp.replace(path)
        emit('complete', {'model_id': model_id if result.converged else None,
                          'cached': False, 'result': summary})
    except Exception as exc:
        emit('error', {'message': str(exc)})
    finally:
        emit('end', {})


@training_bp.post('/api/training/start')
def start_training():
    try:
        settings, config = _parameters(request.get_json(silent=True))
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    model_id = _key(settings)
    job_id = uuid4().hex
    with _lock:
        _jobs[job_id] = {'events': Queue()}
    Thread(target=_worker, args=(job_id, settings, config, model_id), daemon=True).start()
    return jsonify({'job_id': job_id, 'model_id': model_id, 'stream_url': f'/api/training/{job_id}/events'}), 202


@training_bp.get('/api/training/<job_id>/events')
def training_events(job_id):
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return jsonify({'error': 'Unknown training job'}), 404
        if job.get('claimed'):
            return jsonify({'error': 'Training stream already consumed'}), 409
        job['claimed'] = True
    def stream():
        try:
            while True:
                message = job['events'].get()
                yield f"event: {message['event']}\ndata: {json.dumps(message['data'])}\n\n"
                if message['event'] == 'end':
                    break
        finally:
            with _lock:
                _jobs.pop(job_id, None)
    return Response(stream_with_context(stream()), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@training_bp.get('/api/training/models')
def list_models():
    models = []
    for path in sorted(_model_dir().glob('*.json')):
        try:
            item = json.loads(path.read_text(encoding='utf-8'))
            models.append({'model_id': item['model_id'], 'settings': item['settings'], 'summary': item['summary']})
        except (OSError, ValueError, KeyError):
            continue
    return jsonify({'models': models})


@training_bp.get('/api/training/models/<model_id>')
def get_model(model_id):
    try:
        model = _load(model_id)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    if model is None:
        return jsonify({'error': 'Model not found'}), 404
    return jsonify(model)


@training_bp.post('/api/training/models/<model_id>/decision')
def model_decision(model_id):
    try:
        model = _load(model_id)
        if model is None:
            return jsonify({'error': 'Model not found'}), 404
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get('state'), list) or len(body['state']) != 4:
            raise ValueError('Expected state as [NS queue, EW queue, green axis, cooldown]')
        state = tuple(body['state'])
        if any(type(x) is not int for x in state):
            raise ValueError('State components must be integers')
        mdp = TrafficMDP(MDPConfig(**model['settings']['mdp']))
        mdp._check_state(state)
        values = {tuple(item['state']): item['value'] for item in model['values']}
        policy = {tuple(item['state']): item['action'] for item in model['policy']}
        gamma = model['settings']['gamma']
        actions = {}
        for action in mdp.valid_actions(state):
            transitions = mdp.transitions(state, action)
            immediate = sum(prob * reward for prob, _, reward in transitions)
            future = sum(prob * gamma * values[next_state] for prob, next_state, _ in transitions)
            actions[action] = {'q': immediate + future, 'immediate': immediate, 'future': future}
        chosen = policy[state]
        if chosen not in actions:
            raise ValueError('Saved policy action is invalid for the current state')
        return jsonify({'state': list(state), 'action': chosen, 'actions': actions,
                        'gamma': gamma, 'algorithm': model['settings']['algorithm']})
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        current_app.logger.exception('Unexpected failure in AI decision endpoint')
        return jsonify({'error': 'Internal AI decision error. See Flask server logs for traceback.'}), 500
