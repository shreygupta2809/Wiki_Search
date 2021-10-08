from collections import defaultdict
import re
import Stemmer
import string

from stopwords import STOPWORDS

STEMMER = Stemmer.Stemmer('english')
LINK_REGEX = re.compile(r"==External links==.*\n(.+\n)*?[^\n]*(?=\n\n|\[\[Category)")
INFOBOX_REGEX = re.compile(r"{{Infobox")
# HTML_REGEX = re.compile(r"<(?!ref)[^/>]*>[^<]*</(?!ref)[a-z0-9]*>|<[^>]*>")
HTML_REGEX = re.compile(r"<[^>]*>")
SELF_CLOSING = re.compile(r"<[^>]*/>")
# INFOBOX_REGEX = re.compile(r"{{Infobox.*\n(.*\n)*?.*(?=\n}}|\n }}|==)")
BACK_REGEX = re.compile(r"\n\n")
CLOSE_CURLY_REGEX = re.compile(r"\n}}|\n }}|\n==")
# REFERENCE_REGEX = re.compile(r"<ref[^>/]*>[^<]*<[^>/]*/(ref)>")
REFERENCE_REGEX = re.compile(r"==References==.*\n(.+\n)*?[^\n]*(?=(\n\n|\n==))")
REF_BEGIN_END_REGEX = re.compile(r"{{refbegin}}\n(.+\n)*?(?={{refend}})")
REF_REGEX = re.compile(r"<ref[^>]*>[^<]*</ref>")
CATEGORY_REGEX = re.compile(r"\[\[Category:[^]]*]]")
# URL_REGEX = re.compile(r"http[^ }|]*[ }|]")
URL_REGEX = re.compile(r"http[^ }|]*[ }|]|[a-z0-9]*\.(svg|png|jpeg|jpg|com|html|gif|pdf)")
EQUALITY_REGEX = re.compile(r"(\||!) ?[^=|\n}\]]*=")
GARBAGE_REGEX = re.compile(r"\d+[a-z]+\d|[a-z]+\d+[a-z]|([a-z])\1{2,}")
SPLIT_REGEX = re.compile(r"[^a-z0-9]+")
# TABLE = str.maketrans(string.punctuation, " " * len(string.punctuation))
DOC_ID = ""
PASSAGE_WEIGHTS = {"t": 6, "i": 3, "c": 2, "r": 1, "l": 1, "b": 1}


def remove_stopwords(text: list) -> list:
    reduced_words = [word for word in text if word not in STOPWORDS]
    return reduced_words


def stemming(text: list) -> list:
    stemmed_words = STEMMER.stemWords(text)
    stemmed_words_filtered = [word for word in stemmed_words if word[0:2] != "00" and len(word) <= 20 and (
            (not word.isdigit() and not GARBAGE_REGEX.match(word)) or (len(word) <= 4 and word.isdigit()))]
    return stemmed_words_filtered


def tokenize(text: str) -> list:
    text = HTML_REGEX.sub(r" ", text)
    text = URL_REGEX.sub(r" ", text)
    text = EQUALITY_REGEX.sub(r" ", text)
    # text = text.translate(TABLE)
    return SPLIT_REGEX.split(text)
    # return text.split()


def token_dict(tokens: list, pos: str, doc_dict: dict) -> dict:
    count = PASSAGE_WEIGHTS[pos]
    # doc_dict["DOC_COUNT"] += count * len(tokens)
    for token in tokens:
        if token not in doc_dict:
            doc_dict[token] = defaultdict(int)
            doc_dict[token].update({"count": 0, "doc_id": DOC_ID, "pos": set()})
        doc_dict[token]["count"] += count
        if pos != "b" or (pos == 'b' and len(doc_dict[token]["pos"]) > 0):
            doc_dict[token]["pos"].add(pos)

    return doc_dict


def parse_string(text: str) -> list:
    text = text.lower()
    tokenized_text = tokenize(text)
    tokenized_text = remove_stopwords(tokenized_text)
    tokenized_text = stemming(tokenized_text)
    return tokenized_text


def parse_title(text: str, doc_dict: dict) -> dict:
    tokens = parse_string(text)
    doc_dict = token_dict(tokens, "t", doc_dict)
    return doc_dict


def extract_body(text: str, doc_dict: dict) -> dict:
    tokens = parse_string(text)
    doc_dict = token_dict(tokens, "b", doc_dict)
    return doc_dict


def extract_links(text: str, doc_dict: dict) -> tuple:
    match = LINK_REGEX.search(text)
    if match:
        tokens = parse_string(text[match.start():match.end()])
        doc_dict = token_dict(tokens, "l", doc_dict)
        text = LINK_REGEX.sub(" ", text)

    return text, doc_dict


def extract_infobox(text: str, doc_dict: dict) -> tuple:
    new_text = text
    start_ind = -1
    end_ind = -1
    for match in INFOBOX_REGEX.finditer(text):
        start_ind = min(match.start(), start_ind) if start_ind != -1 else match.start()
        infobox_text = text[match.end():]
        close_match = CLOSE_CURLY_REGEX.search(infobox_text)
        if close_match:
            tokens = parse_string(infobox_text[:close_match.start()])
            doc_dict = token_dict(tokens, "i", doc_dict)
            end_ind = max(end_ind, close_match.end())

    if start_ind != -1 and end_ind != -1:
        new_text = text[:start_ind] + " " + text[end_ind:]

    return new_text, doc_dict


def extract_categories(text: str, doc_dict: dict) -> tuple:
    for match in CATEGORY_REGEX.finditer(text):
        tokens = parse_string(text[match.start():match.end()])
        doc_dict = token_dict(tokens, "c", doc_dict)

    text = CATEGORY_REGEX.sub(" ", text)
    return text, doc_dict


def extract_references(text: str, doc_dict: dict) -> tuple:
    for match in REF_REGEX.finditer(text):
        tokens = parse_string(text[match.start():match.end()])
        doc_dict = token_dict(tokens, "r", doc_dict)

    text = REF_REGEX.sub(" ", text)

    match = REFERENCE_REGEX.search(text)
    if match:
        tokens = parse_string(text[match.start():match.end()])
        doc_dict = token_dict(tokens, "r", doc_dict)
        text = REFERENCE_REGEX.sub(" ", text)

    match = REF_BEGIN_END_REGEX.search(text)
    if match:
        tokens = parse_string(text[match.start():match.end()])
        doc_dict = token_dict(tokens, "r", doc_dict)
        text = REF_BEGIN_END_REGEX.sub(" ", text)

    return text, doc_dict


def process_data(ID: int, title: str, text: str) -> dict:
    global DOC_ID
    DOC_ID = str(ID)
    doc_dict = {}
    # doc_dict = {"DOC_COUNT": 0}
    text = SELF_CLOSING.sub(" ", text)
    doc_dict = parse_title(title, doc_dict)
    text, doc_dict = extract_references(text, doc_dict)
    text, doc_dict = extract_categories(text, doc_dict)
    text, doc_dict = extract_links(text, doc_dict)
    text, doc_dict = extract_infobox(text, doc_dict)
    doc_dict = extract_body(text, doc_dict)
    return doc_dict
