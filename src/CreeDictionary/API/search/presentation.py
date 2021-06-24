from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional, TypedDict, Iterable, Any, cast, Dict, Literal

from django.forms import model_to_dict

from CreeDictionary.utils import get_modified_distance
from . import types, core, lookup
from CreeDictionary.utils.fst_analysis_parser import partition_analysis
from CreeDictionary.CreeDictionary.relabelling import LABELS
from CreeDictionary.utils.types import FSTTag, Label, ConcatAnalysis
from .types import Preverb, LinguisticTag, linguistic_tag_from_fst_tags
from ..models import Wordform
from ..schema import SerializedWordform, SerializedDefinition, SerializedLinguisticTag


@dataclass
class _ReduplicationResult:
    """Tiny class to mimic the format of preverbs"""

    text: str
    definitions: list


@dataclass
class _LexicalEntry:
    entry: _ReduplicationResult or SerializedWordform
    type: Literal["Preverb", "Reduplication", "InitialChange"]
    index: int
    original_tag: FSTTag


class SerializedPresentationResult(TypedDict):
    lemma_wordform: SerializedWordform
    wordform_text: str
    is_lemma: bool
    definitions: Iterable[SerializedDefinition]
    lexical_information: List[_LexicalEntry]
    preverbs: Iterable[SerializedWordform]
    friendly_linguistic_breakdown_head: Iterable[Label]
    friendly_linguistic_breakdown_tail: Iterable[Label]
    relevant_tags: Iterable[SerializedLinguisticTag]


class PresentationResult:
    """
    A result ready for user display, and serializable for templates

    The non-presentation Result class is used for gathering features and ranking
    results. When the results to show have been decided upon, this class adds
    presentation things like labels.
    """

    def __init__(self, result: types.Result, *, search_run: core.SearchRun):
        self._result = result
        self._search_run = search_run

        self.wordform = result.wordform
        self.lemma_wordform = result.lemma_wordform
        self.is_lemma = result.is_lemma
        self.source_language_match = result.source_language_match

        (
            self.linguistic_breakdown_head,
            self.linguistic_breakdown_tail,
        ) = safe_partition_analysis(result.wordform.analysis)

        self.lexical_info = get_lexical_information(result.wordform.analysis)

        self.preverbs = [entry for entry in self.lexical_info if entry.type == "Preverb"]
        self.reduplication = [entry for entry in self.lexical_info if entry.type == "Reduplication"]

        self.friendly_linguistic_breakdown_head = replace_user_friendly_tags(
            self.linguistic_breakdown_head
        )
        self.friendly_linguistic_breakdown_tail = replace_user_friendly_tags(
            self.linguistic_breakdown_tail
        )

    def serialize(self) -> SerializedPresentationResult:
        ret: SerializedPresentationResult = {
            "lemma_wordform": serialize_wordform(self.lemma_wordform),
            "wordform_text": self.wordform.text,
            "is_lemma": self.is_lemma,
            "definitions": serialize_definitions(
                self.wordform.definitions.all(),
                # This is the only place include_auto_definitions is used,
                # because we only auto-translate non-lemmas, and this is the
                # only place where a non-lemma search result appears.
                include_auto_definitions=self._search_run.include_auto_definitions,
            ),
            "lexical_information": self.lexical_info,
            "preverbs": [pv.entry for pv in self.preverbs],
            "friendly_linguistic_breakdown_head": self.friendly_linguistic_breakdown_head,
            "friendly_linguistic_breakdown_tail": self.friendly_linguistic_breakdown_tail,
            "relevant_tags": tuple(t.serialize() for t in self.relevant_tags),
        }
        if self._search_run.query.verbose:
            cast(Any, ret)["verbose_info"] = self._result
        return ret

    @property
    def relevant_tags(self) -> Tuple[LinguisticTag, ...]:
        """
        Tags and features to display in the linguistic breakdown pop-up.
        This omits preverbs and other features displayed elsewhere

        In itwêwina, these tags are derived from the suffix features exclusively.
        We chunk based on the English relabelleings!
        """
        return tuple(
            linguistic_tag_from_fst_tags(fst_tags)
            for fst_tags in LABELS.english.chunk(self.linguistic_breakdown_tail)
        )

    def __str__(self):
        return f"PresentationResult<{self.wordform}:{self.wordform.id}>"


def serialize_wordform(wordform) -> SerializedWordform:
    """
    Intended to be passed in a JSON API or into templates.

    :return: json parsable result
    """
    result = model_to_dict(wordform)
    result["definitions"] = serialize_definitions(wordform.definitions.all())
    result["lemma_url"] = wordform.get_absolute_url()

    # Displayed in the word class/inflection help:
    result["inflectional_category_plain_english"] = LABELS.english.get(
        wordform.inflectional_category
    )
    result["inflectional_category_linguistic"] = LABELS.linguistic_long.get(
        wordform.inflectional_category
    )
    result["wordclass_emoji"] = wordform.get_emoji_for_cree_wordclass()
    result["wordclass"] = wordform.wordclass_text

    return result


def serialize_definitions(definitions, include_auto_definitions=False):
    ret = []
    for definition in definitions:
        serialized = definition.serialize()
        if include_auto_definitions or "auto" not in serialized["source_ids"]:
            ret.append(serialized)
    return ret


def safe_partition_analysis(analysis: ConcatAnalysis):
    try:
        (
            linguistic_breakdown_head,
            _,
            linguistic_breakdown_tail,
        ) = partition_analysis(analysis)
    except ValueError:
        linguistic_breakdown_head = []
        linguistic_breakdown_tail = []
    return linguistic_breakdown_head, linguistic_breakdown_tail


def replace_user_friendly_tags(fst_tags: List[FSTTag]) -> List[Label]:
    """replace fst-tags to cute ones"""
    return LABELS.english.get_full_relabelling(fst_tags)


def get_lexical_information(result_analysis: str) -> List[_LexicalEntry]:
    result_analysis_tags = result_analysis.split("+")

    lexical_information: List[_LexicalEntry] = []

    for (i, tag) in enumerate(result_analysis_tags):
        preverb_result: Optional[Preverb] = None
        reduplication_string: Optional[str] = None
        _type = ""
        entry = None

        tag = FSTTag(tag)

        if tag in ["RdplW", "RdplS"]:
            reduplication_string = generate_reduplication_string(result_analysis_tags, tag, i)

        elif tag.startswith("PV/"):
            # use altlabel.tsv to figure out the preverb

            # ling_short looks like: "Preverb: âpihci-"
            ling_short = LABELS.linguistic_short.get(tag)
            if ling_short is not None and ling_short != "":
                # convert to "âpihci" by dropping prefix and last character
                normative_preverb_text = ling_short[len("Preverb: "): -1]
                preverb_results = lookup.fetch_preverbs(normative_preverb_text)

                # find the one that looks the most similar
                if preverb_results:
                    preverb_result = min(
                        preverb_results,
                        key=lambda pr: get_modified_distance(
                            normative_preverb_text,
                            pr.text.strip("-"),
                        ),
                    )

                else:
                    # Can't find a match for the preverb in the database.
                    # This happens when searching against the test database for
                    # ê-kî-nitawi-kâh-kîmôci-kotiskâwêyâhk, as the test database
                    # lacks lacks ê and kî.
                    preverb_result = Wordform(
                        text=normative_preverb_text, is_lemma=True
                    )

        if reduplication_string is not None:
            entry = _ReduplicationResult(
                text=reduplication_string,
                definitions=[
                    {
                        "text": "Strong reduplication"
                        if tag == "RdplS"
                        else "Weak Reduplication"
                    }
                ],
            )
            _type = Literal["Reduplication"]

        if preverb_result is not None:
            entry = serialize_wordform(preverb_result)
            _type = Literal["Preverb"]

        if entry and _type != "":
            result = _LexicalEntry(
                entry=entry,
                type=_type,
                index=i,
                original_tag=tag
            )
            lexical_information.append(result)

    # The list should be sorted, but I'd rather guarantee it is
    return sorted(lexical_information, key=lambda x: x.index)

def generate_reduplication_string(result_analysis_tags: List[str], tag: str, i: int) -> str:
    consonants = "chkmnpstwy"
    word = result_analysis_tags[i + 1]
    letter = word.split("/")[-1][0]
    reduplication_string = ""
    if tag == "RdplW":
        reduplication_string = letter + "a-" if letter.lower() in consonants else "ay-"
    else:
        reduplication_string = letter + "âh-" if letter.lower() in consonants else "âh-"

    return reduplication_string
