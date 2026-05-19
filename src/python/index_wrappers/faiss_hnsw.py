import time
from typing import Optional, Tuple, Union

import numpy as np
import faiss
import torch

from quake import SearchTimingInfo, SearchResult
from quake.index_wrappers.faiss_ivf import metric_str_to_faiss
from quake.index_wrappers.wrapper import IndexWrapper
from quake.utils import to_numpy, to_torch


class FaissHNSW(IndexWrapper):
    """
    Wrapper for Faiss IndexHNSWFlat with proper external-ID support.

    Faiss HNSW internally assigns 0-based sequential IDs.  We wrap it with
    faiss.IndexIDMap so that callers can supply arbitrary int64 vector IDs
    (matching the rest of the evaluation infrastructure) and get them back
    correctly from search results.

    Limitations (by design):
    - remove() raises RuntimeError.  Faiss HNSW has no true delete; use
      insert-only workloads for fair comparisons.
    - maintenance() is a no-op (returns None) — matches FaissIVF behaviour.
    """

    def __init__(self):
        # self.index  : faiss.IndexIDMap wrapping the HNSW base
        # self._hnsw  : direct reference to the underlying IndexHNSWFlat,
        #               kept so we can set efSearch without going through
        #               IndexIDMap's opaque .index attribute.
        self.index = None
        self._hnsw = None

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    def build(
        self,
        vectors: torch.Tensor,
        m: int = 32,
        ef_construction: int = 200,
        metric: str = "l2",
        ids: Optional[torch.Tensor] = None,
    ):
        """
        Build an HNSW index from *vectors*.

        Parameters
        ----------
        vectors : torch.Tensor, shape (n, d)
        m : int
            Number of bi-directional links per node (HNSW M parameter).
        ef_construction : int
            Size of the dynamic candidate list during graph construction.
            Default 200 (vs Faiss default of 40) for reasonable graph quality.
        metric : str
            "l2" or "ip".
        ids : torch.Tensor, optional
            External int64 IDs for each vector.  If None, sequential IDs
            0..n-1 are assigned automatically.
        """
        assert vectors.ndim == 2
        assert m > 0

        faiss_metric = metric_str_to_faiss(metric)
        vectors_np = to_numpy(vectors)
        d = vectors_np.shape[1]

        self._hnsw = faiss.IndexHNSWFlat(d, m, faiss_metric)
        self._hnsw.hnsw.efConstruction = ef_construction
        self.index = faiss.IndexIDMap(self._hnsw)

        n = vectors_np.shape[0]
        if ids is not None:
            ids_np = np.asarray(ids.cpu().numpy(), dtype=np.int64)
        else:
            ids_np = np.arange(n, dtype=np.int64)

        self.index.add_with_ids(vectors_np, ids_np)

    def add(
        self,
        vectors: torch.Tensor,
        ids: Optional[torch.Tensor] = None,
        num_threads: int = 0,
    ):
        """
        Add vectors to a built index.

        Parameters
        ----------
        vectors : torch.Tensor, shape (n, d)
        ids : torch.Tensor, optional
            External int64 IDs.  If None, sequential IDs continuing from
            the current ntotal are assigned.
        num_threads : int
            Ignored (HNSW insertion is sequential in Faiss).
        """
        assert vectors.ndim == 2

        vectors_np = to_numpy(vectors)
        n = vectors_np.shape[0]

        if ids is not None:
            ids_np = np.asarray(ids.cpu().numpy(), dtype=np.int64)
        else:
            start = self.index.ntotal
            ids_np = np.arange(start, start + n, dtype=np.int64)

        self.index.add_with_ids(vectors_np, ids_np)

    def search(
        self,
        query: torch.Tensor,
        k: int,
        ef_search: int = 16,
    ) -> SearchResult:
        """
        Find the k nearest neighbours of *query*.

        Parameters
        ----------
        query : torch.Tensor, shape (nq, d)
        k : int
        ef_search : int
            Dynamic candidate-list size during search.  Higher → better
            recall, higher latency.  Set this to tune the recall/latency
            tradeoff.
        """
        assert query.ndim == 2
        assert k > 0

        # Set efSearch on the underlying HNSW struct.
        # After load(), self._hnsw is None and self.index.index is a generic
        # faiss.Index object (no .hnsw attribute).  Downcast it once and cache.
        if self._hnsw is None:
            base = self.index.index if hasattr(self.index, "index") else self.index
            self._hnsw = faiss.downcast_index(base)
        self._hnsw.hnsw.efSearch = ef_search

        query_np = to_numpy(query)

        timing_info = SearchTimingInfo()
        start = time.time()
        distances, indices = self.index.search(query_np, k)
        end = time.time()

        timing_info.total_time_ns = int((end - start) * 1e9)

        result = SearchResult()
        result.ids = to_torch(indices)
        result.distances = to_torch(distances)
        result.timing_info = timing_info
        return result

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, filename: str):
        """Save to file.  faiss.write_index handles IndexIDMap transparently."""
        faiss.write_index(self.index, str(filename))

    def load(self, filename: str):
        """
        Load from file.  After loading self._hnsw is cleared; search()
        recovers the reference via self.index.index automatically.
        """
        self.index = faiss.read_index(str(filename))
        self._hnsw = None   # will be recovered lazily in search()

    # ------------------------------------------------------------------
    # Unsupported operation
    # ------------------------------------------------------------------

    def remove(self, ids: torch.Tensor):
        """Not supported.  Use insert-only workloads with FaissHNSW."""
        raise RuntimeError(
            "FaissHNSW does not support vector removal.  "
            "Use an insert-only workload (delete_ratio: 0.0) when benchmarking HNSW."
        )

    # ------------------------------------------------------------------
    # Maintenance (no-op — matches FaissIVF behaviour)
    # ------------------------------------------------------------------

    def maintenance(self):
        return None

    # ------------------------------------------------------------------
    # Metadata helpers required by IndexWrapper / WorkloadEvaluator
    # ------------------------------------------------------------------

    def n_total(self) -> int:
        return self.index.ntotal

    def d(self) -> int:
        return self.index.d

    def index_state(self) -> dict:
        """
        Return a dict of index metadata so WorkloadEvaluator can call
        row.update(index.index_state()) safely.
        n_list is set to 0 (HNSW has no IVF partition structure); n_total
        reflects the current vector count so plots that use n_list fall back
        gracefully rather than crashing on a missing column.
        """
        return {"n_total": int(self.index.ntotal), "n_list": 0}

    def centroids(self) -> Union[torch.Tensor, None]:
        """HNSW has no explicit centroids."""
        return None
