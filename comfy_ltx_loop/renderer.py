import time
import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates, distance_transform_edt

from .project import mask


def linear(rgb):
    return np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)


def srgb(rgb):
    rgb = np.clip(rgb, 0, 1)
    return np.where(rgb <= .0031308, rgb * 12.92, 1.055 * rgb ** (1 / 2.4) - .055)


def resize_float(array, size, resample=Image.Resampling.LANCZOS):
    if (array.shape[1], array.shape[0]) == size:
        return array.copy()
    if array.ndim == 2:
        return np.asarray(Image.fromarray(array.astype('float32')).resize(size, resample), dtype='float32')
    return np.stack([resize_float(array[..., c], size, resample) for c in range(array.shape[2])], -1)


def displacement(weight, amplitude, t, period):
    phase = 2 * np.pi * (t % period) / period
    field = np.zeros((*weight.shape, 2), dtype='float32')
    field[..., 0] = amplitude * weight * np.sin(phase)
    field[..., 1] = amplitude * weight * .25 * np.sin(2 * phase)
    return field


def rain_state(seed, count, width, height, t, period):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0, width, count)
    initial_y = rng.uniform(0, height, count)
    cycles = rng.integers(1, 4, count)
    y = (initial_y + height * cycles * ((t % period) / period)) % height
    # Wraps are invisible: both opacity and its derivative vanish at top/bottom.
    opacity = np.sin(np.pi * y / height) ** 2
    return np.stack([x, y, opacity], -1)


class Renderer:
    def __init__(self, project, working_size=None, output_size=None):
        self.project = project
        self.timings = {'deformation_overlay_seconds': 0., 'enlargement_seconds': 0., 'restoration_seconds': 0.}
        self.working_size = working_size or project.working_size
        self.output_size = output_size or project.output_size
        source = np.asarray(Image.open(project.path.parent / project.data['source']).convert('RGB'), dtype='float32') / 255
        self.base = resize_float(linear(source), self.working_size)
        self.reference = np.rint(srgb(resize_float(linear(source), self.output_size)) * 255).astype('uint8')
        self.regions = []
        self.allowed = np.zeros(self.output_size[::-1], bool)
        fixed_roots = np.zeros(self.output_size[::-1], bool)
        self.y, self.x = np.mgrid[:self.working_size[1], :self.working_size[0]].astype('float32')
        for r in sorted(project.data['regions'], key=lambda r: r['depth']):
            get = lambda k: mask(project.path.parent / r[k], project.source_size)
            support = resize_float(get('support'), self.working_size, Image.Resampling.NEAREST) > .5
            alpha = np.clip(resize_float(get('mask'), self.working_size), 0, 1) * support
            target_support = resize_float(get('support'), self.output_size, Image.Resampling.NEAREST) > .5
            self.allowed |= target_support
            weight = None
            if r['kind'] == 'foliage':
                weight = np.clip(resize_float(get('root_weight'), self.working_size), 0, 1)
                roots = resize_float(get('roots'), self.working_size, Image.Resampling.NEAREST) > 0
                weight[roots] = 0
                fixed_roots |= resize_float(get('roots'), self.output_size, Image.Resampling.NEAREST) > 0
                # Interior deformation leaves a fixed margin at every support edge.
                margin = distance_transform_edt(support)
                cap = r.get('amplitude', 2) * min(self.working_size) / 1080
                weight *= np.clip((margin - cap - 2) / max(cap + 2, 1), 0, 1)
                weight *= alpha
            self.regions.append((r, alpha, support, weight))
        guard = resize_float(mask(project.path.parent / project.data['guard'], project.source_size),
                             self.output_size, Image.Resampling.NEAREST) > 0
        self.allowed &= ~(guard | fixed_roots)

    def working_frame(self, index):
        t = index / 24
        period = self.project.data['duration']
        frame = self.base.copy()
        for number, (r, alpha, support, weight) in enumerate(self.regions):
            if r['kind'] == 'foliage':
                d = displacement(weight, r.get('amplitude', 2) * min(self.working_size) / 1080, t, period)
                dx_y, dx_x = np.gradient(d[..., 0])
                dy_y, dy_x = np.gradient(d[..., 1])
                determinant = (1 - dx_x) * (1 - dy_y) - dx_y * dy_x
                if np.any(determinant <= .1):
                    raise ValueError('Folded deformation rejected')
                sx, sy = self.x - d[..., 0], self.y - d[..., 1]
                sample_support = map_coordinates(support.astype('float32'), [sy, sx], order=1, mode='constant')
                moving = np.any(np.abs(d) > 1e-7, axis=-1)
                if np.any(moving & (sample_support < .999)):
                    raise ValueError('Deformation samples outside approved interior support')
                warped = np.stack([map_coordinates(frame[..., c], [sy, sx], order=1, mode='nearest')
                                   for c in range(3)], -1)
                a = (alpha * moving)[..., None]
                frame = warped * a + frame * (1 - a)
            elif r['kind'] == 'shimmer':
                amount = r.get('strength', .04) * (1 + np.sin(2 * np.pi * (t % period) / period)) / 2
                a = (alpha * amount)[..., None]
                frame = np.ones_like(frame) * a + frame * (1 - a)
            else:
                particles = rain_state(self.project.data['seed'] + number, r.get('particles', 80),
                                       *self.working_size, t, period)
                overlay = np.zeros(alpha.shape, 'float32')
                length = max(2, round(10 * min(self.working_size) / 1080))
                for px, py, opacity in particles:
                    # Continuous subpixel stamps avoid whole-pixel temporal jumps.
                    ix, iy = int(px), int(py)
                    for yy in range(max(0, iy - length), min(overlay.shape[0], iy + length + 2)):
                        for xx in range(max(0, ix), min(overlay.shape[1], ix + 2)):
                            value = opacity * max(0, 1 - abs(xx - px)) * max(0, 1 - abs(yy - py) / length)
                            overlay[yy, xx] = max(overlay[yy, xx], value)
                a = (overlay * alpha * r.get('strength', .15))[..., None]
                frame = np.ones_like(frame) * a + frame * (1 - a)
        return np.clip(frame, 0, 1)

    def frame(self, index):
        started = time.perf_counter()
        working = self.working_frame(index)
        self.timings['deformation_overlay_seconds'] += time.perf_counter() - started
        # Enlarge a premultiplied linear delta, retaining the output-resolution source.
        started = time.perf_counter()
        delta = working - self.base
        if self.working_size != self.output_size:
            delta = resize_float(delta, self.output_size)
            self.timings['enlargement_seconds'] += time.perf_counter() - started
        started = time.perf_counter()
        reference_linear = linear(self.reference.astype('float32') / 255)
        result = np.rint(srgb(reference_linear + delta) * 255).astype('uint8')
        result[~self.allowed] = self.reference[~self.allowed]
        self.timings['restoration_seconds'] += time.perf_counter() - started
        return result
