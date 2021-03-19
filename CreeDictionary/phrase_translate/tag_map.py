class UnknownTagError(KeyError):
    """Raised when TagMap encounters an unknown tag"""


# https://stackoverflow.com/a/52709319/14558
def is_subsequence(outer_list, target_subsequence):
    it = iter(outer_list)
    return all(x in it for x in target_subsequence)


# See the description of what a tag map is in crk_tag_map.py
class TagMap:
    DEFAULT = object()
    COPY_TAG_NAME = object()

    def __init__(self, *tag_definitions):
        """
        See the docs in crk_tag_map.py.
        """
        self._multi_mappings = []
        self._tag_mapping = {}
        self._precedences = {}
        self._defaults_by_precedence = {}

        for wordform_tag_spec, phrase_tag_spec, prec in tag_definitions:
            if isinstance(wordform_tag_spec, tuple):
                if phrase_tag_spec == TagMap.COPY_TAG_NAME:
                    raise Exception(
                        f"Error: cannot use copy with multi-tags: {wordform_tag_spec}"
                    )
                self._multi_mappings.append((wordform_tag_spec, phrase_tag_spec, prec))
            elif wordform_tag_spec == TagMap.DEFAULT:
                if prec in self._defaults_by_precedence:
                    raise Exception(
                        f"Error: multiple defaults supplied for precedence {prec}: {self._defaults_by_precedence[prec]}, {phrase_tag_spec}"
                    )
                self._defaults_by_precedence[prec] = phrase_tag_spec
            else:
                if phrase_tag_spec == TagMap.COPY_TAG_NAME:
                    assert wordform_tag_spec.startswith(
                        "+"
                    ), f"expected tag to start with + but did not: {wordform_tag_spec}"
                    phrase_tag_spec = wordform_tag_spec[1:] + "+"
                self._tag_mapping[wordform_tag_spec] = phrase_tag_spec

            if phrase_tag_spec is not None:
                if phrase_tag_spec in self._precedences:
                    if prec != self._precedences[phrase_tag_spec]:
                        raise Exception(
                            f"Error: conflicting precedences specified for {phrase_tag_spec!r}: {self._precedences[phrase_tag_spec]} and {prec}"
                        )
                else:
                    self._precedences[phrase_tag_spec] = prec

    def map_tags(self, input_tags):
        tags_for_phrase = []

        # copy input, because we may mutate it
        input_tags = input_tags[:]

        # first handle multi-mappings, which consume their matching input
        # tags so that they are not re-considered in the next steps
        for wordform_tag_spec, phrase_tag_spec, prec in self._multi_mappings:
            if is_subsequence(input_tags, wordform_tag_spec):
                if phrase_tag_spec is not None:
                    tags_for_phrase.append(phrase_tag_spec)
                input_tags = [x for x in input_tags if x not in wordform_tag_spec]

        # normal mapping
        for wordform_tag in input_tags:
            try:
                phrase_tag = self._tag_mapping[wordform_tag]
            except KeyError:
                raise UnknownTagError(wordform_tag)
            if phrase_tag is not None and phrase_tag not in tags_for_phrase:
                tags_for_phrase.append(phrase_tag)

        # if no mapping for a precedence, use default
        used_precedences = set(self._precedences[tag] for tag in tags_for_phrase)
        for prec, default in self._defaults_by_precedence.items():
            if prec not in used_precedences:
                tags_for_phrase.append(default)

        # Sort all the combined output tags generated by all previous steps
        # into precedence order
        tags_for_phrase.sort(key=self._precedences.__getitem__)

        return tags_for_phrase