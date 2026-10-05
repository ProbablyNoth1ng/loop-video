"""Serializable motion plans. Coordinates are normalized to the original image."""
import copy
import hashlib
import json
import math


def plan_fingerprint(plan):
    data = {k: v for k, v in plan.items() if k not in ('review', 'feedback')}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def canvas_transform(size, short_side=720):
    width, height = size
    if min(width, height) < 1 or not 256 <= short_side <= 2160:
        raise ValueError('Invalid source size or generation short side')
    scale = short_side / min(size)
    content_w, content_h = round(width * scale), round(height * scale)
    canvas_w, canvas_h = math.ceil(content_w / 64)*64, math.ceil(content_h / 64)*64
    return {'source': list(size), 'canvas': [canvas_w, canvas_h],
            'content': [(canvas_w-content_w)//2, (canvas_h-content_h)//2,
                        content_w, content_h]}


def frame_count(duration, fps):
    count = duration * fps
    if not math.isfinite(count) or count < 8 or abs(count-round(count)) > 1e-6 or round(count) % 8:
        raise ValueError('Duration × FPS must be a positive multiple of 8 (6s × 24 = 144)')
    return round(count) + 1


def returning_path(x, y, amplitude, samples=17):
    # Sinusoidal excursion has zero position and velocity at the cycle boundary.
    path = [{'t': i/(samples-1),
             'x': x + amplitude * (1-math.cos(2*math.pi*i/(samples-1))) / 2,
             'y': y} for i in range(samples)]
    path[-1] = {'t': 1., 'x': x, 'y': y}
    return path


def new_plan(identity, size, prompt, requested, landmarks, duration=6, fps=24,
             strength=.01, short_side=720, feedback=None, analysis=None):
    plan = {'schema': 'ambient-motion-plan/1', 'source_id': identity,
            'source_size': list(size), 'prompt': prompt, 'requested': requested,
            'duration': float(duration), 'fps': int(fps), 'strength': float(strength),
            'short_side': int(short_side), 'frames': frame_count(duration, fps),
            'transform': canvas_transform(size, short_side), 'landmarks': [],
            'review': {'state': 'pending'}, 'feedback': feedback or []}
    if analysis is not None:
        plan['analysis'] = copy.deepcopy(analysis)
    for point in landmarks:
        fixed = (point['motion_role'] == 'anchor' if 'motion_role' in point else
                 any(word in point['label'].lower() for word in ('root', 'head', 'shoulder')))
        amplitude = 0 if fixed else min(strength, 1-point['x'])
        plan['landmarks'].append({**point, 'enabled': True, 'strength': 1.,
                                  'path': returning_path(point['x'], point['y'], amplitude)})
    validate_plan(plan)
    return plan


def coordinate(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Point/path coordinate is outside normalized bounds [0,1]')
    return value


def validate_semantics(point):
    if point.get('motion_role') not in ('move', 'anchor'):
        raise ValueError('Motion role must be move or anchor')
    for field in ('body_part', 'reason'):
        if not isinstance(point.get(field), str) or not point[field].strip():
            raise ValueError(f'Every semantic landmark needs a {field}')


def validate_plan(plan):
    if not isinstance(plan, dict) or plan.get('schema') != 'ambient-motion-plan/1':
        raise ValueError('Invalid motion plan; Prepare or place points manually')
    if plan['frames'] != frame_count(plan['duration'], plan['fps']):
        raise ValueError('Motion plan timing changed; prepare and review again')
    if plan['transform'] != canvas_transform(plan['source_size'], plan['short_side']):
        raise ValueError('Recorded image transform changed; prepare and review again')
    if not 0 <= plan['strength'] <= .1 or not isinstance(plan['landmarks'], list):
        raise ValueError('Invalid motion strength or landmark list')
    for point in plan['landmarks']:
        if any(field in point for field in ('motion_role', 'body_part', 'reason')):
            validate_semantics(point)
        if not isinstance(point.get('label'), str) or not point['label'].strip():
            raise ValueError('Every landmark needs a label')
        coordinate(point['x']); coordinate(point['y'])
        if not isinstance(point.get('enabled'), bool) or not 0 <= point['strength'] <= 2:
            raise ValueError('Invalid point enabled state or strength')
        path = point['path']
        if len(path) < 2 or path[0]['t'] != 0 or path[-1]['t'] != 1:
            raise ValueError('Each trajectory must cover timing 0 through 1')
        previous = -1
        for key in path:
            coordinate(key['x']); coordinate(key['y']); coordinate(key['t'])
            if key['t'] <= previous:
                raise ValueError('Path times must increase')
            previous = key['t']
            coordinate(point['x'] + (key['x']-point['x'])*point['strength'])
            coordinate(point['y'] + (key['y']-point['y'])*point['strength'])
            if point.get('motion_role') == 'anchor' and any(
                    abs(key[axis]-point[axis]) > 1e-8 for axis in ('x', 'y')):
                raise ValueError('Anchor paths must stay stationary; change the role to move to edit motion')
        if any(abs(path[0][axis]-point[axis]) > 1e-8 or
               abs(path[-1][axis]-point[axis]) > 1e-8 for axis in ('x','y')):
            raise ValueError('Returning paths must start and end at their landmark')
    return plan


def review_plan(plan):
    plan = copy.deepcopy(validate_plan(plan))
    if not any(p['enabled'] for p in plan['landmarks']):
        raise ValueError('Add or enable at least one landmark before review')
    plan['review'] = {'state': 'reviewed', 'fingerprint': plan_fingerprint(plan)}
    return plan


def require_review(plan, identity, size, prompt, duration, fps, strength, short_side):
    validate_plan(plan)
    expected = (identity, list(size), prompt, float(duration), int(fps), float(strength), int(short_side))
    actual = tuple(plan[k] for k in ('source_id','source_size','prompt','duration','fps','strength','short_side'))
    if actual != expected or plan.get('review', {}).get('state') != 'reviewed' or plan['review'].get('fingerprint') != plan_fingerprint(plan):
        raise ValueError('Image, prompt, settings or points changed; renewed point review required')


def parse_landmarks(raw, requested, feedback=None, require_semantics=False):
    feedback = feedback if feedback is not None else []
    try:
        text = raw.strip()
        if text.startswith('```'):
            text = text.split('\n',1)[1].rsplit('```',1)[0]
        response = json.loads(text)
        points = response['landmarks']
        if not isinstance(points, list) or not points or len(points) > 64:
            raise ValueError('Missing landmarks')
        result = []
        for index, p in enumerate(points):
            try:
                if not isinstance(p['label'], str) or not p['label'].strip():
                    raise ValueError('Missing landmark label')
                for axis in ('x', 'y'):
                    coordinate(p[axis] if isinstance(p[axis], bool) else p[axis]/1000)
                point = {'label': p['label'].strip(), 'x': p['x']/1000, 'y': p['y']/1000}
                if require_semantics or any(field in p for field in ('motion_role', 'body_part', 'reason')):
                    validate_semantics(p)
                    point.update({field:p[field].strip() for field in ('body_part', 'motion_role', 'reason')})
                if any(point['label'].casefold() == old['label'].casefold() or
                       (abs(point['x']-old['x']) < 1e-6 and abs(point['y']-old['y']) < 1e-6)
                       for old in result):
                    raise ValueError('Duplicate label or location')
                result.append(point)
            except (KeyError, TypeError, ValueError) as error:
                feedback.append(f'Skipped suggestion {index+1}: {error}')
        if not result:
            raise ValueError('No valid landmarks; place points manually or retry Prepare')
        missing = [name for name in requested if name.lower() != 'auto' and not any(
            name.lower() in p['label'].lower() or name.lower() in p.get('body_part','').lower() for p in result)]
        if missing:
            feedback.append('Missing requested landmarks: '+', '.join(missing)+'. Add visible points manually if needed.')
        omissions = response.get('omissions', [])
        if isinstance(omissions, list):
            feedback.extend('Omitted: '+note for note in omissions if isinstance(note, str) and note.strip())
        return result
    except (KeyError, TypeError, ZeroDivisionError, json.JSONDecodeError) as error:
        raise ValueError('Invalid vision response; place landmarks manually or retry Prepare') from error


def canvas_tracks(plan):
    validate_plan(plan)
    ox, oy, width, height = plan['transform']['content']
    tracks = []
    for point in plan['landmarks']:
        if not point['enabled']:
            continue
        path, segment, track = point['path'], 0, []
        for index in range(plan['frames']):
            t = index/(plan['frames']-1)
            while segment < len(path)-2 and t > path[segment+1]['t']:
                segment += 1
            a, b = path[segment:segment+2]
            u = (t-a['t'])/(b['t']-a['t'])
            values = {axis: point[axis]+((a[axis]+(b[axis]-a[axis])*u)-point[axis])*point['strength']
                      for axis in ('x','y')}
            track.append({'x': ox+values['x']*(width-1), 'y': oy+values['y']*(height-1)})
        tracks.append(track)
    return tracks
