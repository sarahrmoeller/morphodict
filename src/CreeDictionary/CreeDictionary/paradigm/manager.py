from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Collection, Iterable, Optional, Protocol

from CreeDictionary.CreeDictionary.paradigm.panes import Paradigm, ParadigmLayout

# I would *like* a singleton for this, but, currently, it interacts poorly with mypy :/
ONLY_SIZE = "<only-size>"

logger = logging.getLogger(__name__)


class ParadigmDoesNotExistError(Exception):
    """
    Raised when a paradigm is requested, but does not exist.
    """


class ParadigmManager:
    """
    Mediates access to paradigms layouts.

    Loads layouts from the filesystem and can fill the layout with results from a
    (normative/strict) generator FST.
    """

    # Mappings of paradigm name => sizes available => the layout
    _name_to_layout: dict[str, dict[str, ParadigmLayout]]

    def __init__(self, layout_directory: Path, generation_fst: Transducer):
        self._generator = generation_fst
        self._name_to_layout = defaultdict(dict)

        self._load_layouts_from(layout_directory / "static")
        self._load_layouts_from(layout_directory / "dynamic")

    def paradigm_for(
        self, paradigm_name: str, lemma: Optional[str] = None, size: str = ONLY_SIZE
    ) -> Paradigm:
        """
        Returns a paradigm for the given paradigm name. If a lemma is given, this is
        substituted into the dynamic paradigm.
        """
        if lemma is not None:
            paradigm = self.dynamic_paradigm_for(
                lemma=lemma, word_class=paradigm_name, size=size
            )
        else:
            paradigm = self.static_paradigm_for(paradigm_name, size=size)

        if paradigm is None:
            raise NotImplementedError(
                "not sure what should happen if a paradigm cannot be found"
            )

        return paradigm

    def static_paradigm_for(
        self, name: str, size: str = ONLY_SIZE
    ) -> Optional[Paradigm]:
        """
        Returns a static paradigm with the given name.
        Returns None if there is no paradigm with such a name.
        """
        if size_options := self._name_to_layout.get(name):
            return size_options[size].as_static_paradigm()
        return None

    def dynamic_paradigm_for(
        self, *, lemma: str, word_class: str, size: str = ONLY_SIZE
    ) -> Optional[Paradigm]:
        """
        Returns a dynamic paradigm for the given lemma and word class.
        Returns None if no such paradigm can be generated.
        """
        size_options = self._name_to_layout.get(word_class)
        if size_options is None:
            # No matching name means no paradigm:
            return None

        layout = size_options[size]
        return self._inflect(layout, lemma)

    def sizes_of(self, paradigm_name: str) -> Collection[str]:
        """
        Returns the size options of the given paradigm.
        """
        return self._sizes_or_error_of(paradigm_name).keys()

    def _sizes_or_error_of(self, paradigm_name) -> dict[str, ParadigmLayout]:
        """
        Returns the sizes the given paradigm name. Errors if the paradigm cannot be
        found.
        """
        # _name_to_layout is a defaultdict() so indexing it will ALWAYS return a
        # dictionary.
        if sizes_options := self._name_to_layout.get(paradigm_name, False):
            return sizes_options
        else:
            raise ParadigmDoesNotExistError(paradigm_name)

    def _load_layouts_from(self, path: Path):
        """
        Loads all .tsv files in the path as paradigm layouts.

        Does nothing if the directory does not exist.
        """
        if not path.exists():
            logger.debug("No layouts found in %s", path)
            return

        for paradigm_name, size, layout in _load_all_layouts_in_directory(path):
            self._name_to_layout[paradigm_name][size] = layout

    def _inflect(self, layout: ParadigmLayout, lemma: str) -> Paradigm:
        """
        Given a layout and a lemma, produce a paradigm with forms generated by the FST.
        """
        template2analysis = layout.generate_fst_analyses(lemma=lemma)
        analysis2forms = self._generator.bulk_lookup(list(template2analysis.values()))
        template2forms = {
            template: analysis2forms[analysis]
            for template, analysis in template2analysis.items()
        }
        return layout.fill(template2forms)


class ParadigmManagerWithExplicitSizes(ParadigmManager):
    """
    A ParadigmManager but its sizes are always returned, sorted according the explicit
    order specified.
    """

    def __init__(
        self,
        layout_directory: Path,
        generation_fst: Transducer,
        *,
        ordered_sizes: list[str],
    ):
        super().__init__(layout_directory, generation_fst)
        self._size_to_order = {
            element: index for index, element in enumerate(ordered_sizes)
        }

    def sizes_of(self, paradigm_name: str) -> Collection[str]:
        unsorted_results = super().sizes_of(paradigm_name)
        return sorted(unsorted_results, key=self._sort_by_explict_order)

    def _sort_by_explict_order(self, element: str) -> int:
        """
        Orders elements according to the given ordered sizes.
        Can be used as a key function for sort() or sorted().
        """
        return self._size_to_order[element]

    def all_sizes_fully_specified(self):
        """
        Returns True when all size options for all paradigms are specified in the
        explicit order given in the constructor.
        """
        valid_sizes = {ONLY_SIZE} | self._size_to_order.keys()
        all_paradigms = self._name_to_layout.keys()

        for paradigm in all_paradigms:
            # use super() to avoid any ordering stuff.
            sizes_available = super().sizes_of(paradigm)
            for size in sizes_available:
                if size not in valid_sizes:
                    logger.error(
                        "Paradigm %r has a layout in size %r, however that "
                        "size has not been declared",
                        paradigm,
                        size,
                    )
                    return False

        return True


def _load_all_layouts_in_directory(path: Path):
    """
    Yields (paradigm, size, layout) tuples from the given directory. Immediate
    subdirectories are assumed to be paradigms with multiple size options.
    """
    assert path.is_dir()

    for filename in path.iterdir():
        if filename.is_dir():
            yield from _load_all_sizes_for_paradigm(filename)
        elif filename.match("*.tsv"):
            yield filename.stem, ONLY_SIZE, _load_layout_file(filename)


def _load_all_sizes_for_paradigm(directory: Path):
    """
    Yields (paradigm, size, layout) tuples for ONE paradigm name. The paradigm name
    is inferred from the directory name.
    """
    paradigm_name = directory.name
    assert directory.is_dir()

    for layout_file in directory.glob("*.tsv"):
        size = layout_file.stem
        assert size != ONLY_SIZE, f"size name cannot clash with sentinel value: {size}"
        yield paradigm_name, size, _load_layout_file(layout_file)


def _load_layout_file(layout_file: Path):
    return ParadigmLayout.loads(layout_file.read_text(encoding="UTF-8"))


class Transducer(Protocol):
    """
    Interface for something that can lookup forms in bulk.

    This is basically the subset of the hfst_optimized_lookup.TransducerFile API that
    the paradigm manager actually uses.
    """

    def bulk_lookup(self, strings: Iterable[str]) -> dict[str, set[str]]:
        ...
