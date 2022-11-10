import copy
import threading
from typing import Dict
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple

from optuna.distributions import BaseDistribution
from optuna.trial import FrozenTrial


SearchSpaceSetT = Set[Tuple[str, BaseDistribution]]
SearchSpaceListT = List[Tuple[str, BaseDistribution]]

#  In-memory cache
cached_extra_study_property_cache_lock = threading.Lock()
cached_extra_study_property_cache: Dict[int, "_CachedExtraStudyProperty"] = {}


def get_cached_extra_study_property(
    study_id: int, trials: List[FrozenTrial]
) -> Tuple[SearchSpaceListT, SearchSpaceListT, List[str], bool]:
    with cached_extra_study_property_cache_lock:
        cached_extra_study_property = cached_extra_study_property_cache.get(study_id, None)
        if cached_extra_study_property is None:
            cached_extra_study_property = _CachedExtraStudyProperty()
        cached_extra_study_property.update(trials)
        cached_extra_study_property_cache[study_id] = cached_extra_study_property
        return (
            cached_extra_study_property.intersection,
            cached_extra_study_property.union,
            cached_extra_study_property.union_user_attrs,
            cached_extra_study_property.has_intermediate_values,
        )


class _CachedExtraStudyProperty:
    def __init__(self) -> None:
        self._cursor: int = -1
        # TODO: intersection_search_space and union_search_space look more clear since now we have
        # union_user_attrs.
        self._intersection: Optional[SearchSpaceSetT] = None
        self._union: SearchSpaceSetT = set()
        self._union_user_attrs: Set[str] = set()
        self.has_intermediate_values: bool = False

    @property
    def intersection(self) -> SearchSpaceListT:
        if self._intersection is None:
            return []
        intersection = list(self._intersection)
        intersection.sort(key=lambda x: x[0])
        return intersection

    @property
    def union(self) -> SearchSpaceListT:
        union = list(self._union)
        union.sort(key=lambda x: x[0])
        return union

    @property
    def union_user_attrs(self) -> List[str]:
        union = list(self._union_user_attrs)
        union.sort()
        return union

    def update(self, trials: List[FrozenTrial]) -> None:
        while self._cursor + 1 < len(trials):
            trial = trials[self._cursor + 1]
            if not trial.state.is_finished():
                break

            if not self.has_intermediate_values and len(trial.intermediate_values) > 0:
                self.has_intermediate_values = True

            current = set([(n, d) for n, d in trial.distributions.items()])
            self._union = self._union.union(current)

            if self._intersection is None:
                self._intersection = copy.copy(current)
            else:
                self._intersection = self._intersection.intersection(current)

            current_user_attrs = set(n for n in trial.user_attrs.keys())
            self._union_user_attrs = self._union_user_attrs.union(current_user_attrs)

            self._cursor += 1
