"""Per-vertex labelling on the mesh graph: multi-view voting, smoothing, island clean-up, hem bands."""

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components, dijkstra


def edges_from_tris(tris):
    e = np.vstack([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    e.sort(axis=1)
    return np.unique(e, axis=0)


def adjacency(tris, n, co=None):
    e = edges_from_tris(tris)
    w = np.ones(len(e)) if co is None else np.linalg.norm(co[e[:, 0]] - co[e[:, 1]], axis=1) + 1e-9
    A = sp.coo_matrix((np.r_[w, w], (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])), shape=(n, n)).tocsr()
    return A


def diffuse(values, A, iters, keep=0.5):
    """Repeated neighbour averaging: v <- keep*v + (1-keep)*mean_nbr(v). values (V,) or (V,C)."""
    deg = np.asarray(A.sum(1)).ravel()
    deg[deg == 0] = 1
    Dinv = sp.diags(1.0 / deg)
    M = Dinv @ A
    v = values.astype(np.float64)
    for _ in range(iters):
        v = keep * v + (1 - keep) * (M @ v)
    return v


def cavity(co, vn, A):
    """Signed concavity per vertex: (mean neighbour - vertex) . normal / mean edge length.
    Positive in grooves and folds, negative on ridges."""
    deg = np.asarray(A.sum(1)).ravel()
    deg[deg == 0] = 1
    mean_nb = (A @ co) / deg[:, None]
    d = mean_nb - co
    Al = A.copy().tocoo()
    el = np.linalg.norm(co[Al.row] - co[Al.col], axis=1)
    mel = np.bincount(Al.row, el, minlength=len(co)) / deg
    return (d * vn).sum(1) / np.maximum(mel, 1e-9)


def clean_islands(labels, A, min_size, protect=(), only=None):
    """Relabel connected components of a label smaller than min_size vertices to the most common
    label around them. Repeats until stable (max 5 passes). With `only`, just components of those
    labels are considered, and they are merged only into neighbours with those labels."""
    labels = labels.copy()
    A = A.tocoo()
    r, c = A.row, A.col
    for _ in range(5):
        same = labels[r] == labels[c]
        G = sp.coo_matrix((np.ones(same.sum()), (r[same], c[same])), shape=A.shape).tocsr()
        ncomp, comp = connected_components(G, directed=False)
        sizes = np.bincount(comp, minlength=ncomp)
        small = sizes[comp] < min_size
        for p in protect:
            small &= labels != p
        if only is not None:
            small &= np.isin(labels, list(only))
        if not small.any():
            break
        # for each small component, majority label of neighbours outside the component
        cross = (comp[r] != comp[c]) & small[r]
        if only is not None:
            cross &= np.isin(labels[c], list(only))
        cr, cc = comp[r[cross]], labels[c[cross]]
        if len(cr) == 0:
            break
        nl = labels.max() + 1
        votes = sp.coo_matrix((np.ones(len(cr)), (cr, cc)), shape=(ncomp, nl)).tocsr()
        best = np.asarray(votes.argmax(1)).ravel()
        has = np.asarray(votes.sum(1)).ravel() > 0
        changed = small & has[comp]
        if not changed.any():
            break
        labels[changed] = best[comp[changed]]
    return labels


def boundary_distance(labels, region_mask, A_len, limit, outside=None):
    """Geodesic distance (along mesh edges) from each vertex in region_mask to the nearest vertex
    of the region that touches a vertex of `outside` (default: anything not in the region).
    Inf beyond `limit`."""
    A = A_len.tocoo()
    r, c = A.row, A.col
    if outside is None:
        outside = ~region_mask
    edge_out = region_mask[r] & outside[c]
    src = np.unique(r[edge_out])
    out = np.full(len(labels), np.inf)
    if len(src) == 0:
        return out
    # restrict the graph to the region so distances do not cut through other regions
    keep = region_mask[r] & region_mask[c]
    G = sp.coo_matrix((A.data[keep], (r[keep], c[keep])), shape=A.shape).tocsr()
    d = dijkstra(G, directed=False, indices=src, min_only=True, limit=limit)
    out[region_mask] = d[region_mask]
    return out


def value_noise(co, scale, seed=0):
    """Smooth 3D value noise in [0,1] (trilinear on a hashed lattice), for wash variation."""
    rng = np.random.RandomState(seed)
    table = rng.rand(4096)
    p = co / scale
    i0 = np.floor(p).astype(np.int64)
    f = p - i0
    f = f * f * (3 - 2 * f)

    def h(ix, iy, iz):
        return table[(ix * 73856093 ^ iy * 19349663 ^ iz * 83492791) % 4096]

    out = np.zeros(len(co))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out += w * h(i0[:, 0] + dx, i0[:, 1] + dy, i0[:, 2] + dz)
    return out
